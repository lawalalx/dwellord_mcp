from __future__ import annotations

import os
from datetime import date, datetime, timedelta
from enum import Enum
from typing import Optional
import logging

import cloudinary
import cloudinary.uploader
import redis.asyncio as aioredis
from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import delete, func
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.future import select
from sqlmodel import Field as SQLField
from sqlmodel import SQLModel
from dotenv import load_dotenv


load_dotenv()

from models import (
    Agency,
    Agent,
    Lead,
    LeadStatus,
    ListingType,
    Property,
    PropertyImage,
    PropertyStatus,
    PropertyType,
    Viewing,
    async_session,
    engine,
)


# setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AdminRole(str, Enum):
    ADMIN = "admin"
    AGENT = "agent"


class AdminUser(SQLModel, table=True):
    id: str = SQLField(primary_key=True)
    email: str = SQLField(index=True, unique=True)
    full_name: str
    password_hash: str
    role: AdminRole = SQLField(default=AdminRole.AGENT)
    agency_id: str = SQLField(foreign_key="agency.id")
    agent_id: Optional[str] = SQLField(default=None, foreign_key="agent.id")
    is_active: bool = SQLField(default=True)
    created_at: datetime = SQLField(default_factory=datetime.utcnow)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserResponse"


class AuthRegisterAgencyAdminRequest(BaseModel):
    agency_name: str = Field(min_length=2)
    agency_email: EmailStr
    agency_phone: str = Field(min_length=7)
    agency_address: Optional[str] = None
    full_name: str = Field(min_length=2)
    email: EmailStr
    password: str = Field(min_length=8)


class AuthLoginRequest(BaseModel):
    email: EmailStr
    password: str


class RegisterAgentRequest(BaseModel):
    full_name: str = Field(min_length=2)
    email: EmailStr
    phone: str = Field(min_length=7)
    password: str = Field(min_length=8)


class UserResponse(BaseModel):
    id: str
    email: EmailStr
    full_name: str
    role: AdminRole
    agency_id: str
    agent_id: Optional[str] = None


class PropertyCreateRequest(BaseModel):
    title: str
    description: str
    location: str
    price: float = Field(gt=0)
    bedrooms: int = Field(ge=0)
    bathrooms: int = Field(ge=0)
    property_type: PropertyType
    listing_type: ListingType
    status: PropertyStatus = PropertyStatus.AVAILABLE


class PropertyUpdateRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    location: Optional[str] = None
    price: Optional[float] = Field(default=None, gt=0)
    bedrooms: Optional[int] = Field(default=None, ge=0)
    bathrooms: Optional[int] = Field(default=None, ge=0)
    property_type: Optional[PropertyType] = None
    listing_type: Optional[ListingType] = None
    status: Optional[PropertyStatus] = None


class PropertyResponse(BaseModel):
    id: str
    title: str
    description: str
    location: str
    price: float
    bedrooms: int
    bathrooms: int
    property_type: PropertyType
    listing_type: ListingType
    status: PropertyStatus
    agent_id: str
    created_at: datetime
    images: list[str]


class AgentResponse(BaseModel):
    id: str
    full_name: str
    email: EmailStr
    phone: str
    is_active: bool
    agency_id: str


class LeadResponse(BaseModel):
    id: str
    property_id: str
    agent_id: str
    user_full_name: str
    user_phone: str
    user_email: Optional[str]
    budget: Optional[float]
    status: LeadStatus
    created_at: datetime


class LeadUpdateRequest(BaseModel):
    status: LeadStatus


class ViewingCreateRequest(BaseModel):
    lead_id: str
    scheduled_date: date


class ViewingResponse(BaseModel):
    id: str
    lead_id: str
    scheduled_date: date
    confirmed: bool
    created_at: datetime


class DashboardSummaryResponse(BaseModel):
    total_properties: int
    active_listings: int
    leads: int
    scheduled_viewings: int


class MediaUploadResponse(BaseModel):
    property_id: str
    media_urls: list[str]


JWT_SECRET = os.getenv("ADMIN_JWT_SECRET")
JWT_ALG = os.getenv("JWT_ALG")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ADMIN_TOKEN_EXPIRE_MIN"))


pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")



cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
)


app = FastAPI(
    title="House Agent Admin API",
    version="1.0.0",
    description="Admin API for agencies, agents, properties, leads, viewings, and media.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



REDIS_URL = os.getenv("REDIS_URL")
REDIS_HOST = os.getenv("REDIS_HOST")
REDIS_PORT = os.getenv("REDIS_PORT")
REDIS_USERNAME = os.getenv("REDIS_USERNAME")
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD")
REDIS_SSL = os.getenv("REDIS_SSL", "false").lower() == "true"


def build_redis_client() -> Optional[aioredis.Redis]:
    if REDIS_URL:
        return aioredis.from_url(REDIS_URL, decode_responses=True)

    if REDIS_HOST and REDIS_PORT and REDIS_PASSWORD:
        return aioredis.Redis(
            host=REDIS_HOST,
            port=int(REDIS_PORT),
            decode_responses=True,
            username=REDIS_USERNAME or "default",
            password=REDIS_PASSWORD,
            ssl=REDIS_SSL,
        )

    return None


redis_client = build_redis_client()


def disable_redis(reason: str, exc: Exception) -> None:
    global redis_client
    logger.warning("Redis disabled (%s): %s", reason, exc)
    redis_client = None


async def redis_get_safe(key: str) -> Optional[str]:
    if not redis_client:
        return None
    try:
        return await redis_client.get(key)
    except Exception as exc:
        disable_redis("get", exc)
        return None


async def redis_setex_safe(key: str, ttl_seconds: int, value: str) -> None:
    if not redis_client:
        return
    try:
        await redis_client.setex(key, ttl_seconds, value)
    except Exception as exc:
        disable_redis("setex", exc)


@app.on_event("startup")
async def startup_event() -> None:
    logger.info("Starting admin API")
    if redis_client:
        try:
            await redis_client.ping()
            logger.info("Redis connected")
        except Exception as exc:
            disable_redis("startup ping", exc)

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


@app.on_event("shutdown")
async def shutdown_event() -> None:
    if redis_client:
        await redis_client.close()



def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(subject: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {"sub": subject, "exp": expire}
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALG)


async def get_current_user(token: str = Depends(oauth2_scheme)) -> AdminUser:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
    )
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
        user_id: str | None = payload.get("sub")
        if not user_id:
            raise credentials_error
    except JWTError as exc:
        raise credentials_error from exc

    async with async_session() as session:
        user = await session.get(AdminUser, user_id)
        if not user or not user.is_active:
            raise credentials_error
        return user


def ensure_admin(user: AdminUser) -> None:
    if user.role != AdminRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")


def can_access_agency(user: AdminUser, agency_id: str) -> bool:
    return user.role == AdminRole.ADMIN or user.agency_id == agency_id


def agent_visible_to_user(agent: Optional[Agent], user: AdminUser) -> bool:
    return agent is not None and can_access_agency(user, agent.agency_id)


async def serialize_property(property_obj: Property) -> PropertyResponse:
    async with async_session() as session:
        images_result = await session.execute(
            select(PropertyImage.image_url).where(PropertyImage.property_id == property_obj.id)
        )
        images = list(images_result.scalars().all())

    return PropertyResponse(
        id=property_obj.id,
        title=property_obj.title,
        description=property_obj.description,
        location=property_obj.location,
        price=property_obj.price,
        bedrooms=property_obj.bedrooms,
        bathrooms=property_obj.bathrooms,
        property_type=property_obj.property_type,
        listing_type=property_obj.listing_type,
        status=property_obj.status,
        agent_id=property_obj.agent_id,
        created_at=property_obj.created_at,
        images=images,
    )


@app.post("/api/v1/auth/register-agency-admin", response_model=TokenResponse)
async def register_agency_admin(payload: AuthRegisterAgencyAdminRequest) -> TokenResponse:
    async with async_session() as session:
        existing = await session.scalar(select(AdminUser).where(AdminUser.email == payload.email))
        if existing:
            raise HTTPException(status_code=409, detail="User already exists")

        agency = Agency(
            name=payload.agency_name,
            email=payload.agency_email,
            phone=payload.agency_phone,
            address=payload.agency_address,
            created_at=datetime.utcnow(),
        )
        session.add(agency)
        await session.flush()

        user = AdminUser(
            id=os.urandom(16).hex(),
            email=payload.email,
            full_name=payload.full_name,
            password_hash=hash_password(payload.password),
            role=AdminRole.ADMIN,
            agency_id=agency.id,
            is_active=True,
        )
        session.add(user)
        await session.commit()

        token = create_access_token(user.id)
        return TokenResponse(
            access_token=token,
            user=UserResponse(
                id=user.id,
                email=user.email,
                full_name=user.full_name,
                role=user.role,
                agency_id=user.agency_id,
                agent_id=user.agent_id,
            ),
        )


@app.post("/api/v1/auth/login", response_model=TokenResponse)
async def login(payload: AuthLoginRequest) -> TokenResponse:
    async with async_session() as session:
        user = await session.scalar(select(AdminUser).where(AdminUser.email == payload.email))
        if not user or not verify_password(payload.password, user.password_hash):
            raise HTTPException(status_code=401, detail="Invalid credentials")

        token = create_access_token(user.id)
        return TokenResponse(
            access_token=token,
            user=UserResponse(
                id=user.id,
                email=user.email,
                full_name=user.full_name,
                role=user.role,
                agency_id=user.agency_id,
                agent_id=user.agent_id,
            ),
        )


@app.get("/api/v1/auth/me", response_model=UserResponse)
async def get_me(current_user: AdminUser = Depends(get_current_user)) -> UserResponse:
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        role=current_user.role,
        agency_id=current_user.agency_id,
        agent_id=current_user.agent_id,
    )


@app.post("/api/v1/agents", response_model=AgentResponse)
async def register_agent(
    payload: RegisterAgentRequest,
    current_user: AdminUser = Depends(get_current_user),
) -> AgentResponse:
    ensure_admin(current_user)

    async with async_session() as session:
        existing_agent = await session.scalar(select(Agent).where(Agent.email == payload.email))
        existing_user = await session.scalar(select(AdminUser).where(AdminUser.email == payload.email))
        if existing_agent or existing_user:
            raise HTTPException(status_code=409, detail="Agent already exists")

        agent = Agent(
            agency_id=current_user.agency_id,
            full_name=payload.full_name,
            email=payload.email,
            phone=payload.phone,
            created_at=datetime.utcnow(),
        )
        session.add(agent)
        await session.flush()

        agent_user = AdminUser(
            id=os.urandom(16).hex(),
            email=payload.email,
            full_name=payload.full_name,
            password_hash=hash_password(payload.password),
            role=AdminRole.AGENT,
            agency_id=current_user.agency_id,
            agent_id=agent.id,
            is_active=True,
        )
        session.add(agent_user)
        await session.commit()
        await session.refresh(agent)

        return AgentResponse(
            id=agent.id,
            full_name=agent.full_name,
            email=agent.email,
            phone=agent.phone,
            is_active=agent.is_active,
            agency_id=agent.agency_id,
        )


@app.get("/api/v1/agents", response_model=list[AgentResponse])
async def list_agents(current_user: AdminUser = Depends(get_current_user)) -> list[AgentResponse]:
    async with async_session() as session:
        result = await session.execute(select(Agent).where(Agent.agency_id == current_user.agency_id))
        agents = result.scalars().all()
        return [
            AgentResponse(
                id=agent.id,
                full_name=agent.full_name,
                email=agent.email,
                phone=agent.phone,
                is_active=agent.is_active,
                agency_id=agent.agency_id,
            )
            for agent in agents
        ]


@app.patch("/api/v1/agents/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: str,
    full_name: Optional[str] = Form(default=None),
    phone: Optional[str] = Form(default=None),
    is_active: Optional[bool] = Form(default=None),
    current_user: AdminUser = Depends(get_current_user),
) -> AgentResponse:
    ensure_admin(current_user)

    async with async_session() as session:
        agent = await session.get(Agent, agent_id)
        if not agent or agent.agency_id != current_user.agency_id:
            raise HTTPException(status_code=404, detail="Agent not found")

        if full_name is not None:
            agent.full_name = full_name
        if phone is not None:
            agent.phone = phone
        if is_active is not None:
            agent.is_active = is_active

        await session.commit()
        await session.refresh(agent)

        return AgentResponse(
            id=agent.id,
            full_name=agent.full_name,
            email=agent.email,
            phone=agent.phone,
            is_active=agent.is_active,
            agency_id=agent.agency_id,
        )


@app.post("/api/v1/properties", response_model=PropertyResponse)
async def create_property(
    payload: PropertyCreateRequest,
    current_user: AdminUser = Depends(get_current_user),
) -> PropertyResponse:
    async with async_session() as session:
        agent_id = current_user.agent_id
        if current_user.role == AdminRole.ADMIN:
            first_agent = await session.scalar(
                select(Agent).where(Agent.agency_id == current_user.agency_id).order_by(Agent.created_at.asc())
            )
            if not first_agent:
                raise HTTPException(status_code=400, detail="Create an agent first")
            agent_id = first_agent.id

        if not agent_id:
            raise HTTPException(status_code=400, detail="No agent profile linked")

        property_obj = Property(
            agent_id=agent_id,
            title=payload.title,
            description=payload.description,
            location=payload.location,
            price=payload.price,
            bedrooms=payload.bedrooms,
            bathrooms=payload.bathrooms,
            property_type=payload.property_type,
            listing_type=payload.listing_type,
            status=payload.status,
            created_at=datetime.utcnow(),
        )
        session.add(property_obj)
        await session.commit()
        await session.refresh(property_obj)
        return await serialize_property(property_obj)


@app.get("/api/v1/properties", response_model=list[PropertyResponse])
async def list_properties(
    location: Optional[str] = Query(default=None),
    min_price: Optional[float] = Query(default=None),
    max_price: Optional[float] = Query(default=None),
    bedrooms: Optional[int] = Query(default=None),
    status_filter: Optional[PropertyStatus] = Query(default=None),
    current_user: AdminUser = Depends(get_current_user),
) -> list[PropertyResponse]:
    async with async_session() as session:
        query = select(Property).join(Agent, Agent.id == Property.agent_id).order_by(Property.created_at.desc())

        if current_user.role != AdminRole.ADMIN:
            query = query.where(Agent.agency_id == current_user.agency_id)

        if location:
            query = query.where(Property.location.ilike(f"%{location.strip()}%"))
        if min_price is not None:
            query = query.where(Property.price >= min_price)
        if max_price is not None:
            query = query.where(Property.price <= max_price)
        if bedrooms is not None:
            query = query.where(Property.bedrooms == bedrooms)
        if status_filter is not None:
            query = query.where(Property.status == status_filter)

        result = await session.execute(query)
        properties = result.scalars().all()

        responses: list[PropertyResponse] = []
        for property_obj in properties:
            responses.append(await serialize_property(property_obj))

        return responses


@app.get("/api/v1/properties/{property_id}", response_model=PropertyResponse)
async def get_property(property_id: str, current_user: AdminUser = Depends(get_current_user)) -> PropertyResponse:
    async with async_session() as session:
        property_obj = await session.get(Property, property_id)
        if not property_obj:
            raise HTTPException(status_code=404, detail="Property not found")

        agent = await session.get(Agent, property_obj.agent_id)
        if not agent_visible_to_user(agent, current_user):
            raise HTTPException(status_code=404, detail="Property not found")

        return await serialize_property(property_obj)


@app.patch("/api/v1/properties/{property_id}", response_model=PropertyResponse)
async def update_property(
    property_id: str,
    payload: PropertyUpdateRequest,
    current_user: AdminUser = Depends(get_current_user),
) -> PropertyResponse:
    async with async_session() as session:
        property_obj = await session.get(Property, property_id)
        if not property_obj:
            raise HTTPException(status_code=404, detail="Property not found")

        agent = await session.get(Agent, property_obj.agent_id)
        if not agent_visible_to_user(agent, current_user):
            raise HTTPException(status_code=404, detail="Property not found")

        data = payload.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(property_obj, key, value)

        await session.commit()
        await session.refresh(property_obj)
        return await serialize_property(property_obj)


@app.delete("/api/v1/properties/{property_id}")
async def delete_property(property_id: str, current_user: AdminUser = Depends(get_current_user)) -> dict:
    ensure_admin(current_user)
    async with async_session() as session:
        property_obj = await session.get(Property, property_id)
        if not property_obj:
            raise HTTPException(status_code=404, detail="Property not found")

        agent = await session.get(Agent, property_obj.agent_id)
        if not agent_visible_to_user(agent, current_user):
            raise HTTPException(status_code=404, detail="Property not found")

        # Delete dependent rows first to avoid NOT NULL/FK integrity errors.
        lead_ids = list(
            (
                await session.execute(
                    select(Lead.id).where(Lead.property_id == property_id)
                )
            ).scalars().all()
        )

        try:
            if lead_ids:
                await session.execute(delete(Viewing).where(Viewing.lead_id.in_(lead_ids)))

            await session.execute(delete(Lead).where(Lead.property_id == property_id))
            await session.execute(delete(PropertyImage).where(PropertyImage.property_id == property_id))

            await session.delete(property_obj)
            await session.commit()
            return {"success": True}
        except IntegrityError as exc:
            await session.rollback()
            logger.exception("Integrity error deleting property %s", property_id)
            raise HTTPException(status_code=409, detail="Cannot delete property due to related records") from exc
        except SQLAlchemyError as exc:
            await session.rollback()
            logger.exception("Database error deleting property %s", property_id)
            raise HTTPException(status_code=500, detail="Database error while deleting property") from exc


@app.post("/api/v1/properties/{property_id}/deactivate", response_model=PropertyResponse)
async def deactivate_property(property_id: str, current_user: AdminUser = Depends(get_current_user)) -> PropertyResponse:
    async with async_session() as session:
        property_obj = await session.get(Property, property_id)
        if not property_obj:
            raise HTTPException(status_code=404, detail="Property not found")

        agent = await session.get(Agent, property_obj.agent_id)
        if not agent_visible_to_user(agent, current_user):
            raise HTTPException(status_code=404, detail="Property not found")

        property_obj.status = PropertyStatus.PENDING
        await session.commit()
        await session.refresh(property_obj)
        return await serialize_property(property_obj)


@app.post("/api/v1/properties/{property_id}/media", response_model=MediaUploadResponse)
async def upload_property_media(
    property_id: str,
    files: list[UploadFile] = File(...),
    primary_index: int = Form(default=0),
    current_user: AdminUser = Depends(get_current_user),
) -> MediaUploadResponse:
    async with async_session() as session:
        property_obj = await session.get(Property, property_id)
        if not property_obj:
            raise HTTPException(status_code=404, detail="Property not found")

        agent = await session.get(Agent, property_obj.agent_id)
        if not agent_visible_to_user(agent, current_user):
            raise HTTPException(status_code=404, detail="Property not found")

        urls: list[str] = []
        for idx, upload in enumerate(files):
            file_bytes = await upload.read()
            result = cloudinary.uploader.upload(
                file_bytes,
                folder=f"house-agent/properties/{property_id}",
                resource_type="auto",
                public_id=f"{property_id}_{int(datetime.utcnow().timestamp())}_{idx}",
                overwrite=True,
            )
            secure_url = result.get("secure_url")
            if not secure_url:
                raise HTTPException(status_code=500, detail="Cloudinary upload failed")

            image = PropertyImage(
                property_id=property_id,
                image_url=secure_url,
                is_primary=idx == primary_index,
            )
            session.add(image)
            urls.append(secure_url)

        await session.commit()

        await redis_setex_safe(f"property:{property_id}:media", 600, "||".join(urls))

        return MediaUploadResponse(property_id=property_id, media_urls=urls)


@app.get("/api/v1/properties/{property_id}/media", response_model=MediaUploadResponse)
async def get_property_media(property_id: str, current_user: AdminUser = Depends(get_current_user)) -> MediaUploadResponse:
    async with async_session() as session:
        property_obj = await session.get(Property, property_id)
        if not property_obj:
            raise HTTPException(status_code=404, detail="Property not found")

        agent = await session.get(Agent, property_obj.agent_id)
        if not agent_visible_to_user(agent, current_user):
            raise HTTPException(status_code=404, detail="Property not found")

        cached = await redis_get_safe(f"property:{property_id}:media")
        if cached:
            return MediaUploadResponse(property_id=property_id, media_urls=[u for u in cached.split("||") if u])

        result = await session.execute(select(PropertyImage.image_url).where(PropertyImage.property_id == property_id))
        urls = list(result.scalars().all())

        await redis_setex_safe(f"property:{property_id}:media", 600, "||".join(urls))

        return MediaUploadResponse(property_id=property_id, media_urls=urls)


@app.get("/api/v1/leads", response_model=list[LeadResponse])
async def list_leads(
    status_filter: Optional[LeadStatus] = Query(default=None),
    property_id: Optional[str] = Query(default=None),
    current_user: AdminUser = Depends(get_current_user),
) -> list[LeadResponse]:
    async with async_session() as session:
        query = (
            select(Lead)
            .join(Property, Property.id == Lead.property_id)
            .join(Agent, Agent.id == Property.agent_id)
            .order_by(Lead.created_at.desc())
        )

        if current_user.role != AdminRole.ADMIN:
            query = query.where(Agent.agency_id == current_user.agency_id)

        if status_filter:
            query = query.where(Lead.status == status_filter)
        if property_id:
            query = query.where(Lead.property_id == property_id)

        result = await session.execute(query)
        leads = result.scalars().all()

        return [
            LeadResponse(
                id=lead.id,
                property_id=lead.property_id,
                agent_id=lead.agent_id,
                user_full_name=lead.user_full_name,
                user_phone=lead.user_phone,
                user_email=lead.user_email,
                budget=lead.budget,
                status=lead.status,
                created_at=lead.created_at,
            )
            for lead in leads
        ]


@app.patch("/api/v1/leads/{lead_id}", response_model=LeadResponse)
async def update_lead(
    lead_id: str,
    payload: LeadUpdateRequest,
    current_user: AdminUser = Depends(get_current_user),
) -> LeadResponse:
    async with async_session() as session:
        lead = await session.get(Lead, lead_id)
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")

        property_obj = await session.get(Property, lead.property_id)
        if not property_obj:
            raise HTTPException(status_code=404, detail="Lead property not found")

        agent = await session.get(Agent, property_obj.agent_id)
        if not agent_visible_to_user(agent, current_user):
            raise HTTPException(status_code=404, detail="Lead not found")

        lead.status = payload.status
        await session.commit()
        await session.refresh(lead)

        return LeadResponse(
            id=lead.id,
            property_id=lead.property_id,
            agent_id=lead.agent_id,
            user_full_name=lead.user_full_name,
            user_phone=lead.user_phone,
            user_email=lead.user_email,
            budget=lead.budget,
            status=lead.status,
            created_at=lead.created_at,
        )


@app.post("/api/v1/leads/{lead_id}/convert-to-viewing", response_model=ViewingResponse)
async def convert_lead_to_viewing(
    lead_id: str,
    scheduled_date: date = Form(...),
    current_user: AdminUser = Depends(get_current_user),
) -> ViewingResponse:
    async with async_session() as session:
        lead = await session.get(Lead, lead_id)
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")

        property_obj = await session.get(Property, lead.property_id)
        if not property_obj:
            raise HTTPException(status_code=404, detail="Lead property not found")

        agent = await session.get(Agent, property_obj.agent_id)
        if not agent_visible_to_user(agent, current_user):
            raise HTTPException(status_code=404, detail="Lead not found")

        viewing = Viewing(lead_id=lead.id, scheduled_date=scheduled_date, confirmed=False, created_at=datetime.utcnow())
        lead.status = LeadStatus.VIEWING_SCHEDULED
        session.add(viewing)
        await session.commit()
        await session.refresh(viewing)

        return ViewingResponse(
            id=viewing.id,
            lead_id=viewing.lead_id,
            scheduled_date=viewing.scheduled_date,
            confirmed=viewing.confirmed,
            created_at=viewing.created_at,
        )


@app.post("/api/v1/viewings", response_model=ViewingResponse)
async def create_viewing(
    payload: ViewingCreateRequest,
    current_user: AdminUser = Depends(get_current_user),
) -> ViewingResponse:
    async with async_session() as session:
        lead = await session.get(Lead, payload.lead_id)
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")

        property_obj = await session.get(Property, lead.property_id)
        if not property_obj:
            raise HTTPException(status_code=404, detail="Lead property not found")

        agent = await session.get(Agent, property_obj.agent_id)
        if not agent_visible_to_user(agent, current_user):
            raise HTTPException(status_code=404, detail="Lead not found")

        viewing = Viewing(lead_id=payload.lead_id, scheduled_date=payload.scheduled_date, confirmed=False, created_at=datetime.utcnow())
        lead.status = LeadStatus.VIEWING_SCHEDULED
        session.add(viewing)
        await session.commit()
        await session.refresh(viewing)

        return ViewingResponse(
            id=viewing.id,
            lead_id=viewing.lead_id,
            scheduled_date=viewing.scheduled_date,
            confirmed=viewing.confirmed,
            created_at=viewing.created_at,
        )


@app.get("/api/v1/viewings", response_model=list[ViewingResponse])
async def list_viewings(current_user: AdminUser = Depends(get_current_user)) -> list[ViewingResponse]:
    async with async_session() as session:
        query = (
            select(Viewing)
            .join(Lead, Lead.id == Viewing.lead_id)
            .join(Property, Property.id == Lead.property_id)
            .join(Agent, Agent.id == Property.agent_id)
            .order_by(Viewing.scheduled_date.asc())
        )

        if current_user.role != AdminRole.ADMIN:
            query = query.where(Agent.agency_id == current_user.agency_id)

        result = await session.execute(query)
        viewings = result.scalars().all()

        return [
            ViewingResponse(
                id=viewing.id,
                lead_id=viewing.lead_id,
                scheduled_date=viewing.scheduled_date,
                confirmed=viewing.confirmed,
                created_at=viewing.created_at,
            )
            for viewing in viewings
        ]


@app.patch("/api/v1/viewings/{viewing_id}/confirm", response_model=ViewingResponse)
async def confirm_viewing(viewing_id: str, current_user: AdminUser = Depends(get_current_user)) -> ViewingResponse:
    async with async_session() as session:
        viewing = await session.get(Viewing, viewing_id)
        if not viewing:
            raise HTTPException(status_code=404, detail="Viewing not found")

        lead = await session.get(Lead, viewing.lead_id)
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")

        property_obj = await session.get(Property, lead.property_id)
        if not property_obj:
            raise HTTPException(status_code=404, detail="Property not found")

        agent = await session.get(Agent, property_obj.agent_id)
        if not agent_visible_to_user(agent, current_user):
            raise HTTPException(status_code=404, detail="Viewing not found")

        viewing.confirmed = True
        await session.commit()
        await session.refresh(viewing)

        return ViewingResponse(
            id=viewing.id,
            lead_id=viewing.lead_id,
            scheduled_date=viewing.scheduled_date,
            confirmed=viewing.confirmed,
            created_at=viewing.created_at,
        )


@app.get("/api/v1/dashboard/summary", response_model=DashboardSummaryResponse)
async def dashboard_summary(current_user: AdminUser = Depends(get_current_user)) -> DashboardSummaryResponse:
    async with async_session() as session:
        total_properties_query = select(func.count(Property.id)).select_from(Property).join(Agent, Agent.id == Property.agent_id)
        active_listings_query = (
            select(func.count(Property.id))
            .select_from(Property)
            .join(Agent, Agent.id == Property.agent_id)
            .where(Property.status == PropertyStatus.AVAILABLE)
        )
        leads_count_query = (
            select(func.count(Lead.id))
            .select_from(Lead)
            .join(Property, Property.id == Lead.property_id)
            .join(Agent, Agent.id == Property.agent_id)
        )
        viewing_count_query = (
            select(func.count(Viewing.id))
            .select_from(Viewing)
            .join(Lead, Lead.id == Viewing.lead_id)
            .join(Property, Property.id == Lead.property_id)
            .join(Agent, Agent.id == Property.agent_id)
        )

        if current_user.role != AdminRole.ADMIN:
            total_properties_query = total_properties_query.where(Agent.agency_id == current_user.agency_id)
            active_listings_query = active_listings_query.where(Agent.agency_id == current_user.agency_id)
            leads_count_query = leads_count_query.where(Agent.agency_id == current_user.agency_id)
            viewing_count_query = viewing_count_query.where(Agent.agency_id == current_user.agency_id)

        total_properties = await session.scalar(total_properties_query)
        active_listings = await session.scalar(active_listings_query)
        leads_count = await session.scalar(leads_count_query)
        viewing_count = await session.scalar(viewing_count_query)

        return DashboardSummaryResponse(
            total_properties=total_properties or 0,
            active_listings=active_listings or 0,
            leads=leads_count or 0,
            scheduled_viewings=viewing_count or 0,
        )


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
