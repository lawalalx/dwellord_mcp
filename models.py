# db_models_async_realestate.py

from sqlmodel import SQLModel, Field, Relationship
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.orm import sessionmaker
from typing import List, Optional
from datetime import datetime, date
from enum import Enum
import os

from datetime import datetime, date, timedelta, time
from sqlalchemy import Column, JSON
from pathlib import Path


from dotenv import load_dotenv

load_dotenv()


# DB_FILE = Path(__file__).resolve().with_name("realestate.db")
# DATABASE_URL = f"sqlite+aiosqlite:///{DB_FILE.as_posix()}"

DATABASE_URL = os.getenv("DATABASE_URL")

# ---------------------------------------------------
# ENUMS
# ---------------------------------------------------

class ListingType(str, Enum):
    SALE = "sale"
    RENT = "rent"
    SHORTLET = "shortlet"


class PropertyStatus(str, Enum):
    AVAILABLE = "available"
    SOLD = "sold"
    RENTED = "rented"
    PENDING = "pending"


class LeadStatus(str, Enum):
    NEW = "new"
    CONTACTED = "contacted"
    VIEWING_SCHEDULED = "viewing_scheduled"
    CLOSED = "closed"
    LOST = "lost"


class SubscriptionPlan(str, Enum):
    STARTER = "starter"
    PRO = "pro"
    ENTERPRISE = "enterprise"


# ============================================================
# 🔹 AuditAction SCHEMAS
# ============================================================
class AuditAction(str, Enum):
    CREATED = "created"
    UPDATED = "updated"
    DELETED = "deleted"
    STATUS_CHANGED = "status_changed"
    ASSIGNED = "assigned"
    
    SEARCH = "search"
    VIEW_DETAILS = "view_details"
    LEAD_CREATED = "lead_created"
    VIEWING_SCHEDULED = "viewing_scheduled"
    RESERVED = "reserved"
    ORDER_PLACED = "order_placed"
    PAYMENT_INITIATED = "payment_initiated"
    PAYMENT_CONFIRMED = "payment_confirmed"
    CANCELLED = "cancelled"
    


# ============================================================
# 🔹 Payment SCHEMAS
# ============================================================
class PaymentPurpose(str, Enum):
    DEPOSIT = "deposit"
    RENT = "rent"
    PURCHASE = "purchase"

class PaymentStatus(str, Enum):
    INITIATED = "initiated"
    PAID = "paid"
    FAILED = "failed"

    

class PropertyType(str, Enum):
    # Residential
    SELF_CONTAIN = "self_contain"           # self-contained unit / studio
    MINI_FLAT = "mini_flat"                 # 1 bedroom flat with hall and pantry
    ONE_BEDROOM_FLAT = "1_bedroom_flat"
    TWO_BEDROOM_FLAT = "2_bedroom_flat"
    THREE_BEDROOM_FLAT = "3_bedroom_flat"
    FOUR_PLUS_BEDROOM_FLAT = "4_plus_bedroom_flat"
    
    # Houses & Larger Units
    DUPLEX = "duplex"                       # 2-storey family house
    TERRACE_HOUSE = "terrace_house"         # row houses sharing walls
    SEMI_DETACHED = "semi_detached"         # house sharing one wall
    BUNGALOW = "bungalow"                   # single-storey standalone
    MANSION = "mansion"                     # large luxury house
    
    # Other Residential & Specialty
    MAISONETTE = "maisonette"               # 2-level unit within structure
    BLOCK_OF_FLATS = "block_of_flats"       # building with multiple units
    FACE_ME_I_FACE_YOU = "face_me_i_face_you"
    HOSTEL_ROOM = "hostel_room"
    BED_SPACE = "bed_space"
    
    # Commercial / Mixed
    COMMERCIAL_SHOP = "commercial_shop"
    OFFICE_SPACE = "office_space"
    INDUSTRIAL = "industrial_space"
    LAND = "land"



class EntityType(str, Enum):
    PROPERTY = "property"
    LEAD = "lead"
    AGENT = "agent"
    AGENCY = "agency"
    VIEWING = "viewing"
    SUBSCRIPTION = "subscription"



class ReminderType(str, Enum):
    VIEWING_REMINDER = "viewing_reminder"
    PAYMENT_REMINDER = "payment_reminder"
    AGENT_FOLLOWUP = "agent_followup"
    
    
import uuid

def generate_uuid() -> str:
    return str(uuid.uuid4())

# ---------------------------------------------------
# AGENCY MODEL
# ---------------------------------------------------

class Agency(SQLModel, table=True):
    id: str = Field(default_factory=generate_uuid, primary_key=True)
    name: str
    email: str
    phone: str
    address: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    agents: List["Agent"] = Relationship(back_populates="agency")
    subscriptions: List["Subscription"] = Relationship(back_populates="agency")


# ---------------------------------------------------
# AGENT MODEL
# ---------------------------------------------------

class Agent(SQLModel, table=True):
    id: str = Field(default_factory=generate_uuid, primary_key=True)
    agency_id: str = Field(foreign_key="agency.id")

    full_name: str
    email: str
    phone: str
    profile_image_url: Optional[str] = None
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)

    agency: Agency = Relationship(back_populates="agents")
    properties: List["Property"] = Relationship(back_populates="agent")
    leads: List["Lead"] = Relationship(back_populates="agent")


# ---------------------------------------------------
# PROPERTY MODEL
# ---------------------------------------------------

class Property(SQLModel, table=True):
    id: str = Field(default_factory=generate_uuid, primary_key=True)

    agent_id: str = Field(foreign_key="agent.id")

    title: str
    description: str
    location: str
    price: float
    bedrooms: int
    bathrooms: int
    property_type: PropertyType 
    listing_type: ListingType
    status: PropertyStatus = PropertyStatus.AVAILABLE

    size_sqm: Optional[float] = None
    is_featured: bool = False

    created_at: datetime = Field(default_factory=datetime.utcnow)

    agent: Agent = Relationship(back_populates="properties")
    images: List["PropertyImage"] = Relationship(back_populates="property")
    leads: List["Lead"] = Relationship(back_populates="property")


# ---------------------------------------------------
# PROPERTY IMAGES
# ---------------------------------------------------

class PropertyImage(SQLModel, table=True):
    id: str = Field(default_factory=generate_uuid, primary_key=True)
    property_id: str = Field(foreign_key="property.id")

    image_url: str
    is_primary: bool = False

    property: Property = Relationship(back_populates="images")


# ---------------------------------------------------
# LEADS (YOUR MONEY TABLE 💰)
# ---------------------------------------------------

class Lead(SQLModel, table=True):
    id: str = Field(default_factory=generate_uuid, primary_key=True)

    property_id: str = Field(foreign_key="property.id")
    agent_id: str = Field(foreign_key="agent.id")

    user_full_name: str
    user_phone: str
    user_email: Optional[str] = None

    budget: Optional[float] = None
    preferred_viewing_date: Optional[date] = None
    message: Optional[str] = None

    status: LeadStatus = LeadStatus.NEW
    created_at: datetime = Field(default_factory=datetime.utcnow)

    property: Property = Relationship(back_populates="leads")
    agent: Agent = Relationship(back_populates="leads")


# ---------------------------------------------------
# VIEWING SCHEDULE
# ---------------------------------------------------

class Viewing(SQLModel, table=True):
    id: str = Field(default_factory=generate_uuid, primary_key=True)

    lead_id: str = Field(foreign_key="lead.id")
    scheduled_date: date
    confirmed: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)



class Reminder(SQLModel, table=True):
    id: str = Field(default_factory=generate_uuid, primary_key=True)

    user_phone: str
    property_id: str
    reminder_type: ReminderType
    scheduled_at: datetime
    sent: bool = False
    
    
# ---------------------------------------------------
# SUBSCRIPTIONS (HOW YOU MAKE MONEY)
# ---------------------------------------------------

class Subscription(SQLModel, table=True):
    id: str = Field(default_factory=generate_uuid, primary_key=True)

    agency_id: str = Field(foreign_key="agency.id")
    plan: SubscriptionPlan
    price: float
    active: bool = True
    start_date: date
    end_date: date

    agency: Agency = Relationship(back_populates="subscriptions")




# ---------------------------------------------------
# AUDIT LOG (Keep From Banking - Very Useful)
# ---------------------------------------------------
class AuditLog(SQLModel, table=True):
    id: str = Field(default_factory=generate_uuid, primary_key=True)

    entity_type: EntityType
    entity_id: str | None = None

    action: AuditAction
    performed_by: Optional[str] = None   # agent_id / admin_id
    user_phone: Optional[str] = None

    meta_data: dict | None = Field(default=None, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    




# ---------------------------
# PropertyReservation
# ---------------------------
class PropertyReservation(SQLModel, table=True):
    id: str = Field(default_factory=generate_uuid, primary_key=True)
    property_id: str
    user_name: str
    user_phone: str
    expires_at: datetime
    status: str = Field(default=PropertyStatus.PENDING.value)
    created_at: datetime = Field(default_factory=datetime.utcnow)

# ---------------------------
# PropertyOrder
# ---------------------------
class PropertyOrder(SQLModel, table=True):
    id: str = Field(default_factory=generate_uuid, primary_key=True)
    property_id: str
    user_name: str
    user_phone: str
    offer_amount: float
    message: Optional[str] = None
    status: str = Field(default="submitted")
    created_at: datetime = Field(default_factory=datetime.utcnow)

# ---------------------------
# Payment
# ---------------------------
class Payment(SQLModel, table=True):
    id: str = Field(default_factory=generate_uuid, primary_key=True)
    property_id: str
    user_phone: str
    amount: float
    purpose: str
    status: str = Field(default=PaymentStatus.INITIATED.value)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    
# ---------------------------------------------------
# ASYNC ENGINE
# ---------------------------------------------------

engine: AsyncEngine = create_async_engine(DATABASE_URL, echo=True, future=True)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
