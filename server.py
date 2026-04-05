# estate_mcp_tools.py
from mcp.server.fastmcp import FastMCP
from sqlalchemy.future import select
from starlette.applications import Starlette
from starlette.routing import Route, Mount
from sqlalchemy.orm import selectinload
from mcp.server.fastmcp.prompts import base
from typing import Optional
from datetime import datetime, date, timedelta, time
import sys, asyncio, uvicorn, os
from dotenv import load_dotenv

from models import async_session
from config import settings
from models import *
from schemas_mcp import *

from utils.utils_funcs import (
    fetch_agent_leads,
    fetch_agent_orders,
    fetch_agent_viewings,
    query_available_slots,
    resolve_agent
)

load_dotenv()

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    
mcp = FastMCP("estate-async-mcp")


# --- Decorators ---
def get_tool(**kwargs):
    kwargs["description"] = "GET: " + kwargs.get("description", "")
    return mcp.tool(**kwargs)

def post_tool(**kwargs):
    kwargs["description"] = "POST: " + kwargs.get("description", "")
    return mcp.tool(**kwargs)


# ==========================
# 🔹 PROPERTY TOOLS
# ==========================
async def run_property_query(
    session,
    location: Optional[str] = None,
    property_type: Optional[PropertyType] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    bedrooms: Optional[int] = None,
    limit: int = 20
):
    query = (
        select(Property)
        .options(selectinload(Property.images))
        .where(Property.status == PropertyStatus.AVAILABLE)
    )

    # -----------------------------
    # SAFE FILTERS
    # -----------------------------
    if location and location.strip():
        query = query.where(Property.location.ilike(f"%{location.strip()}%"))

    if property_type is not None:
        query = query.where(Property.property_type == property_type)

    if bedrooms is not None:
        query = query.where(Property.bedrooms == bedrooms)

    if min_price is not None:
        query = query.where(Property.price >= min_price)

    if max_price is not None:
        query = query.where(Property.price <= max_price)

    # -----------------------------
    # DEFAULT ORDERING (IMPORTANT)
    # -----------------------------
    query = query.order_by(Property.created_at.desc())

    result = await session.execute(query.limit(limit))
    return result.scalars().all()



@get_tool(description="""
    Search available properties.
    Optional filters: location, property_type, min_price, max_price, bedrooms.
    Returns list of properties with basic info (title, location, price, bedrooms, type, image_url)
""")
async def search_properties(
    location: Optional[str] = None,
    property_type: Optional[PropertyType] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    bedrooms: Optional[int] = None
) -> PropertySearchResponse:

    async with async_session() as session:

        # -----------------------------
        # 1. STRICT SEARCH
        # -----------------------------
        properties = await run_property_query(
            session,
            location=location,
            property_type=property_type,
            min_price=min_price,
            max_price=max_price,
            bedrooms=bedrooms
        )

        fallback_reason = None

        # -----------------------------
        # 2. RELAX PROPERTY TYPE
        # -----------------------------
        if not properties and property_type is not None:
            properties = await run_property_query(
                session,
                location=location,
                min_price=min_price,
                max_price=max_price,
                bedrooms=bedrooms
            )
            fallback_reason = "property type"

        # -----------------------------
        # 3. RELAX BEDROOMS
        # -----------------------------
        if not properties and bedrooms is not None:
            properties = await run_property_query(
                session,
                location=location,
                min_price=min_price,
                max_price=max_price
            )
            fallback_reason = "number of bedrooms"

        # -----------------------------
        # 4. RELAX LOCATION
        # -----------------------------
        if not properties and location and "," in location:
            broader_location = location.split(",")[-1].strip()

            if broader_location:
                properties = await run_property_query(
                    session,
                    location=broader_location,
                    min_price=min_price,
                    max_price=max_price
                )
                fallback_reason = "location"

        # -----------------------------
        # 5. FINAL FALLBACK → FETCH ALL
        # -----------------------------
        if not properties:
            properties = await run_property_query(session)
            fallback_reason = "all filters"

        # -----------------------------
        # BUILD RESPONSE
        # -----------------------------
        property_items = []
        for p in properties:
            cover_image = next(
                (img.image_url for img in p.images if img.is_primary),
                None
            )
            if not cover_image and p.images:
                cover_image = p.images[0].image_url

            property_items.append(
                PropertyItem(
                    id=str(p.id),
                    title=p.title,
                    location=p.location,
                    price=p.price,
                    bedrooms=p.bedrooms,
                    property_type=p.property_type,
                    image_url=cover_image,
                    property_id=str(p.id),
                )
            )

        # -----------------------------
        # MESSAGE
        # -----------------------------
        if fallback_reason == "all filters":
            message = "No exact match found. Showing available properties instead."
        elif fallback_reason:
            message = (
                f"No exact match found, but here are similar properties "
                f"after relaxing the {fallback_reason} filter."
            )
        else:
            message = "Properties fetched successfully."

        return PropertySearchResponse(
            success=True,
            message=message,
            results=property_items
        )     

@get_tool(description="""
    Get detailed information about a property using property_id.
    Returns full description, images, location, price, bedrooms, bathrooms, agent_id.
""")
async def get_property_details(
    property_id: str
) -> PropertyDetailResponse:
    async with async_session() as session:
        property_obj = await session.get(Property, property_id, options=[selectinload(Property.images)])

        if not property_obj:
            return PropertyDetailResponse(success=False, message="Property not found.")

        images = [img.image_url for img in property_obj.images]

        return PropertyDetailResponse(
            success=True,
            message="Data fetched successfully",
            id=property_obj.id,
            title=property_obj.title,
            description=property_obj.description,
            location=property_obj.location,
            price=property_obj.price,
            bedrooms=property_obj.bedrooms,
            bathrooms=property_obj.bathrooms,
            images=images,
            agent_id=property_obj.agent_id
        )


# ==========================
# 🔹 AGENT TOOLS
# ==========================
@get_tool(description="""
    Get agent contact info for a specific lead.
    Only returns contact info if the user has an active lead.
""")
async def get_agent_contact(agent_id: str, requester_phone: Optional[str] = None) -> AgentContactResponse:
    async with async_session() as session:
        agent = await session.get(Agent, agent_id, options=[selectinload(Agent.agency)])
        if not agent:
            return AgentContactResponse(success=False, message="Agent not found.")
        
        # Optional access control: requester must have a lead with this agent
        if requester_phone:
            lead_exists = await session.scalar(
                select(Lead.id).where(Lead.agent_id == agent_id, Lead.user_phone == requester_phone)
            )
            if not lead_exists:
                return AgentContactResponse(success=False, message="Access denied: no active lead with this agent.")

        return AgentContactResponse(
            success=True,
            message="Data fetched successfully",
            agent_name=agent.full_name,
            phone=agent.phone,
            email=agent.email,
            agency_name=agent.agency.name if agent.agency else None
        )
             

def require_confirmation(confirmed: bool):
    if not confirmed:
        return MCPResponse(
            success=False,
            message="User confirmation required"
        )
    
    

@post_tool(description="""
Reserve (hold) a property for a client.
Requires explicit confirmation. Does NOT complete payment.
""")
async def reserve_property(
    property_id: str,
    client_name: str,
    client_phone: str,
    confirmed: bool = False,
    reservation_days: int = 3
) -> ReservationResponse | MCPResponse:

    # 1️⃣ Require explicit confirmation
    resp = require_confirmation(confirmed)
    if resp:
        return resp

    async with async_session() as session:

        # 2️⃣ Fetch property
        property_obj = await session.get(Property, property_id)

        if not property_obj:
            return ReservationResponse(success=False, message="Property not found")

        # 3️⃣ Mark as pending
        property_obj.status = PropertyStatus.PENDING

        # 4️⃣ Create reservation
        reservation = PropertyReservation(
            property_id=property_id,
            user_name=client_name,
            user_phone=client_phone,
            expires_at=datetime.utcnow() + timedelta(days=reservation_days),
            status=PropertyStatus.PENDING.value,
        )

        # 5️⃣ Audit log
        audit = AuditLog(
            entity_type=EntityType.PROPERTY,
            entity_id=property_id,
            action=AuditAction.RESERVED,
            description=f"Property reserved for {client_name} ({client_phone}) until {reservation.expires_at}"
        )

        session.add_all([property_obj, reservation, audit])

        await session.commit()

        return ReservationResponse(
            success=True,
            message="Property reserved"
        )
        



@post_tool(description="""
Place an official order / intent-to-buy or rent.
This is a serious commitment.
""")
async def place_property_order(
    property_id: str,
    client_name: str,
    client_phone: str,
    offer_amount: float,
    message: Optional[str] = None
) -> OrderResponse:

    async with async_session() as session:

        # 1️⃣ Create order
        order = PropertyOrder(
            property_id=property_id,
            user_name=client_name,
            user_phone=client_phone,
            offer_amount=offer_amount,
            message=message,
            status="submitted",
            created_at=datetime.utcnow()
        )
        session.add(order)
        await session.commit()
        await session.refresh(order)  # optional, ensures order.id is populated

        # 2️⃣ Create audit log
        audit = AuditLog(
            entity_type=EntityType.ORDER,
            entity_id=order.id,
            action=AuditAction.CREATED,
            description=f"Order placed by {client_name} ({client_phone}) for amount {offer_amount}"
        )
        session.add(audit)
        await session.commit()

        return OrderResponse(
            success=True,
            message="Your order has been submitted to the agent."
        )
        
        

# ==========================
# 🔹 LEAD TOOLS
# ==========================
@get_tool(description="Agent CRM dashboard overview")
async def get_agent_dashboard(
    requester_agent_id: str,
    agent_id: str
) -> AgentDashboardResponse:

    if requester_agent_id != agent_id:
        raise PermissionError("Access denied")

    # Fetch data asynchronously
    leads, viewings, orders = await asyncio.gather(
        fetch_agent_leads(agent_id),
        fetch_agent_viewings(agent_id),
        fetch_agent_orders(agent_id),
    )

    return AgentDashboardResponse(
        success=True,
        message="Successfully retrieved agent dashboard",
        leads=leads,
        viewings=viewings,
        orders=orders,
    )
    

# ==========================
# 🔹 LEAD TOOLS
# ==========================
@post_tool(description="""
    Capture a user's interest in a property and create a lead.
    This notifies the agent for follow-up.
""")
async def create_property_lead(
    property_id: str,
    client_name: str,
    client_phone: str,
    client_email: Optional[str] = None,
    message: Optional[str] = None
) -> LeadResponse:

    async with async_session() as session:
        property_obj = await session.get(Property, property_id)
        if not property_obj:
            return LeadResponse(success=False, message="Property not found.")

        new_lead = Lead(
            property_id=property_id,
            agent_id=property_obj.agent_id,
            user_full_name=client_name,
            user_phone=client_phone,
            user_email=client_email,
            message=message,
            created_at=datetime.utcnow()
        )
        session.add(new_lead)
        await session.commit()

        return LeadResponse(
            success=True,
            message="Your interest has been sent to the agent. They will contact you shortly.",        
            lead_id=str(new_lead.id)  
        )



# ==========================
# 🔹 Payment TOOLS
# ==========================
@post_tool(description="Initiate a secure payment for a property")
async def initiate_payment(
    property_id: str,
    client_name: str,
    client_phone: str,
    amount: float,
    purpose: PaymentPurpose
) -> PaymentResponse:

    async with async_session() as session:
        payment = Payment(
            property_id=property_id,
            user_phone=client_phone,
            amount=amount,
            purpose=purpose,
            status=PaymentStatus.INITIATED.value,
            created_at=datetime.utcnow()
        )

        session.add(payment)
        await session.commit()

        return PaymentResponse(
            success=True,
            message="Payment initiated successfully",
            payment_id=payment.id,
            payment_url=f"https://pay.example.com/{payment.id}"
        )



@get_tool(description="Get available viewing slots for an agent")
async def get_agent_availability(
    agent_id: str,
    from_date: date,
    to_date: date
) -> AvailabilityResponse:
    slots = await query_available_slots(agent_id, from_date, to_date)

    return AvailabilityResponse(
        success=True,
        slots=slots
    )


@post_tool(description="Book a confirmed viewing slot")
async def lock_and_book(slot_id: str, lead_id: str) -> Viewing | MCPResponse:
    """
    Locks a viewing slot and assigns it to a lead.
    Ensures slot is not double-booked.
    """
    async with async_session() as session:
        slot = await session.get(Viewing, slot_id)
        if not slot:
            return MCPResponse(success=False, message=f"Viewing slot {slot_id} not found")

        if slot.confirmed:
            return MCPResponse(success=False, message=f"Slot {slot_id} is already booked")

        # Assign to lead and mark as booked
        slot.lead_id = lead_id
        slot.confirmed = True
        await session.commit()
        await session.refresh(slot)

        audit = AuditLog(
            entity_type=EntityType.VIEWING,
            entity_id=slot.id,
            action=AuditAction.STATUS_CHANGED,
            description=f"Slot booked for lead {lead_id}"
        )
        session.add(audit)
        await session.commit()

        return slot
    

    
# ==========================
# 🔹 VIEWING TOOLS
# ==========================
@post_tool(description="""
Schedule a viewing for a property with a preferred date.
Creates a lead if none exists, then schedules viewing.
""")
async def schedule_viewing(
    property_id: str,
    client_name: str,
    client_phone: str,
    preferred_date: date,
    confirmed: bool = False
) -> ViewingResponse:

    require_confirmation(confirmed)

    async with async_session() as session:

        agent_id = await resolve_agent(session, property_id)

        # Create Lead
        lead = Lead(
            property_id=property_id,
            agent_id=agent_id,
            user_full_name=client_name,
            user_phone=client_phone,
            status=LeadStatus.VIEWING_SCHEDULED
        )

        session.add(lead)
        await session.commit()
        await session.refresh(lead)

        # Create Viewing
        viewing = Viewing(
            lead_id=lead.id,
            scheduled_date=preferred_date
        )

        session.add(viewing)
        await session.commit()
        await session.refresh(viewing)

        # Audit log
        audit = AuditLog(
            entity_type=EntityType.VIEWING,
            entity_id=viewing.id,
            action=AuditAction.CREATED,
            user_phone=client_phone
        )

        session.add(audit)   # ← no await
        await session.commit()

        return ViewingResponse(
            success=True,
            message="Viewing scheduled successfully",
            viewing_id=str(viewing.id),
            scheduled_date=viewing.scheduled_date
        )


@post_tool(description="Book a confirmed viewing slot")
async def book_viewing_slot(
    slot_id: str,
    lead_id: str
) -> MCPResponse:
    try:
        slot = await lock_and_book(slot_id, lead_id)
    except ValueError as e:
        return MCPResponse(success=False, message=str(e))

    return MCPResponse(
        success=True,
        message=f"Viewing slot {slot.id} booked successfully"
    )
    


# --- Prompts for LLM ---
@mcp.prompt(
    name="estateagent_initial_prompt",
    description="Strict system prompt for FirstBank virtual assistant. Prevents hallucination, enforces tool-only data usage."
)
def get_initial_prompts():
    return [
        base.UserMessage(
        """
           You are "EstateAgent AI", an intelligent, empathetic, and highly capable assistant specializing in real estate rentals and sales. Your primary goal is to help users find properties that match their criteria by leveraging the available internal tools to provide accurate, actionable, and structured responses.

            1️⃣ Role & Persona
            Identity: HomeFinder AI, a knowledgeable, patient, and helpful real estate assistant.
            Objective: Simplify the property search process, and guide users through their real estate journey.
            Tone: Professional, friendly, empathetic, and always clear in instructions.

            2️⃣ Core Capabilities
            Property Search: Find rental or for-sale properties using internal tools (filters include location, property type, budget, bedrooms, amenities, etc.).
            Property Details Retrieval: Present comprehensive information including price, address, property description, images, and agent contact if permitted.
            Lead & Viewing Management: Assist users in expressing interest in properties, creating leads, and scheduling viewings via internal tools.
            Clarification: Ask precise, polite questions when user requests are ambiguous, incomplete, or unrealistic.
            Guidance: Suggest next steps or alternative options if initial search fails or user criteria are unrealistic.
            Structured Tool Usage: Always use the available tools to obtain reliable information instead of guessing.

            3️⃣ Interaction Guidelines
            Start with Clarification: Confirm essential details first (e.g., "Are you looking to rent or buy?", "Desired location?", "Budget?").
            Acknowledge & Confirm: Repeat key details to confirm understanding (e.g., "Got it — you want a 2-bedroom flat in Yaba with a budget of 1.2 million Naira.").
            Handle Ambiguity Gracefully: Politely address vague requests or unrealistic budgets and suggest practical alternatives.
            Manage Expectations: Clearly communicate system limitations (e.g., "I can provide available properties and agent contacts, but I cannot book the property directly.").
            Offer Actionable Options: End responses with clear next steps (e.g., "Would you like me to schedule a viewing, contact the agent, or refine your search?").

            4️⃣ Tool Usage
            You must always use tools to retrieve data. Do NOT hallucinate property details or agent information.
            
            Available Tools:
            - search_properties(location, property_type, min_price, max_price, bedrooms) → PropertySearchResponse
            Purpose: Search for available properties matching user criteria.
            Instructions: Apply all relevant filters provided by the user. Return structured results.
            🏠 Property Type (MUST use exact enum values)
                When specifying property_type, ONLY use one of the following exact values.
                ⚠️ Do NOT spell out numbers in words (e.g. ❌ two_bedroom_flat).
                Always use the numeric enum form shown below.
                Residential (Flats & Apartments)
                self_contain: self-contained unit, studio apartment
                mini_flat: 1 bedroom flat with hall and pantry
                1_bedroom_flat: 1 bedroom flat, 1-bed apartment
                2_bedroom_flat: 2 bedroom flat, 2-bed apartment
                3_bedroom_flat: 3 bedroom flat, 3-bed apartment
                4_plus_bedroom_flat: 4+ bedroom flat, large apartment
                Houses & Larger Units
                duplex: 2-storey family house
                terrace_house: row house, terraced house (shared side walls)
                semi_detached: semi-detached house (shares one wall)
                bungalow: single-storey standalone house
                mansion: large luxury house

                Other Residential & Specialty
                maisonette: 2-level unit within a larger structure
                block_of_flats: building containing multiple flat units
                face_me_i_face_you: shared-compound housing with facing rooms
                hostel_room: single room in a hostel
                bed_space: shared sleeping space within a room

                Commercial / Mixed Use
                commercial_shop: shop, retail space
                office_space: office, commercial office space
                industrial_space: industrial space, factory, warehouse
                land: plot of land
                When the user mentions "apartment" or "flat" without specifying bedrooms, you can infer 'one_bedroom_flat', 'two_bedroom_flat', or 'three_bedroom_flat' based on context, or ask for clarification. If they say "house," consider 'duplex', 'semi_detached', 'bungalow', or 'mansion'. If the user provides a number of bedrooms (e.g., "2 bedrooms"), prioritize mapping to 'two_bedroom_flat' if no other specific type is given.
            Waiting Message: "Searching our property listings for matches..."

            - get_property_details(property_id) → PropertyDetailResponse
            Purpose: Retrieve detailed information for a specific property.
            Instructions: Only call when a property ID is known or selected from search results.
            Waiting Message: "Retrieving full property details..."

            - get_agent_contact(agent_id) → AgentContactResponse
            Purpose: Get agent contact information.
            Instructions: Only use if permitted by platform rules or after user expresses interest.
            Before calling get_agent_contact, ensure you have the correct agent_id from the get_property_details or search_properties
            Waiting Message: "Fetching agent contact information..."

            - create_property_lead(property_id, client_name, client_phone, client_email, message) → LeadResponse
            Purpose: Register user interest in a property.
            Instructions: Use to generate leads for agents. Confirm to user after creation.
            Waiting Message: "Submitting your interest to the agent..."

            - schedule_viewing(property_id, client_name, client_phone, preferred_date) → ViewingResponse
            Purpose: Schedule a property viewing with the agent.
            Instructions: Use preferred date and client info from user input.
            Waiting Message: "Scheduling the viewing with the agent..."
            
            - reserve_property(property_id, client_name, client_phone, confirmed) → ReservationResponse
            Purpose: Temporarily hold a property for the user. Highlight that reservations expire automatically.
            Instructions: Require explicit confirmation before reserving.

            - place_property_order(property_id, client_name, client_phone, offer_amount, message) → OrderResponse
            Purpose: Place an official order (intent-to-buy/rent). Ensure user understands commitment.

            - lock_and_book(slot_id, lead_id) → Viewing
            Purpose: Lock a viewing slot for a lead. Prevent double-booking.

            5️⃣ Handling Results
            - UI Delegation:
                The UI layer will render all property details.
                You MUST NOT format or list property data.
                Only provide a short conversational sentence introducing the result.

                - DO NOT:
                - List property attributes
                - Use bullet points
                - Show images or links
             - Highlight Key Options: Present actionable choices ("View details," "Contact agent," "Schedule viewing").
             - Address Limitations: If no results found, clearly explain why and suggest alternatives.
             - Fallback Explanation: If filters are relaxed, explain exactly which filter caused the fallback (property type, bedrooms, location).
             - Result Limits: Show only the top 5–10 properties per response to avoid overwhelming the user.

            6️⃣ Principles
             - Never guess property or agent data. Always retrieve from tools.
             - Maintain empathy, clarity, and professionalism.
             - Always use consistent IDs (agent_id for agents, lead_id for leads).
             - Clarify ambiguous or inconsistent filter inputs before performing search.
            - Remind users about reservation expiry or pending actions when relevant.
        """
        
        )
    ]




#   1️⃣ Role & Persona
#     Identity: HomeFinder AI, a knowledgeable, patient, and helpful real estate assistant.
#     Objective: Simplify the property search process, provide relevant property listings, and guide users through their real estate journey.
#     Tone: Professional, friendly, empathetic, and always clear in instructions.
            
            
#  5️⃣ Handling Results
#              - Structured Summaries: Always respond using structured summaries from tool results. Include title, price, location, bedrooms, property type, agent info, and availability.
#              - Highlight Key Options: Present actionable choices ("View details," "Contact agent," "Schedule viewing").
#              - Address Limitations: If no results found, clearly explain why and suggest alternatives.
#              - Fallback Explanation: If filters are relaxed, explain exactly which filter caused the fallback (property type, bedrooms, location).
#              - Result Limits: Show only the top 5–10 properties per response to avoid overwhelming the user.
# --- Resources ---

@mcp.resource(
    "banking://branches",
    name="firstbank_branch_locations",
    description="Provides a list of FirstBank branches including address, city, state, and contact information. Useful for users asking about nearest branches."
)
def get_branch_locations() -> str:
    """
    List of FirstBank branches with address, city, state, and contact info.
    Useful when a customer asks 'Where is the nearest branch?'.
    """
    branches = [
        {"branch": "Lagos Main", "address": "123 Marina, Lagos", "phone": "+2348012345678"},
        {"branch": "Ikeja", "address": "45 Allen Ave, Ikeja", "phone": "+2348012345679"},
        {"branch": "Abuja", "address": "12 Central St, Abuja", "phone": "+2348012345680"},
    ]
    # We return a formatted string so the LLM can read it easily
    return "\n".join([f"{b['branch']}: {b['address']} (Tel: {b['phone']})" for b in branches])


@mcp.resource(
    "banking://rates",
    name="firstbank_loan_rates",
    description="Provides current FirstBank loan interest rates for different loan products like Personal, Car, and Home loans."
)
def get_loan_rates() -> str:
    """Current FirstBank loan rates for different products."""
    rates = [
        {"type": "Personal Loan", "rate": "21% APR"},
        {"type": "Car Loan", "rate": "17% APR"},
        {"type": "Home Loan", "rate": "12% APR"},
    ]
    return "\n".join([f"{r['type']}: {r['rate']}" for r in rates])


@mcp.resource(
    "banking://account-types",
    name="firstbank_account_types",
    description="Lists available FirstBank account types with minimum balance requirements and interest rates."
)
def get_account_types() -> str:
    """Available account types and basic requirements."""
    types = [
        {"type": "Savings", "min_balance": "₦1000", "interest": "5%"},
        {"type": "Current", "min_balance": "₦0", "interest": "0%"},
        {"type": "Fixed Deposit", "min_balance": "₦50000", "interest": "8%"},
    ]
    return "\n".join([f"{t['type']} - Min Balance: {t['min_balance']}, Interest: {t['interest']}" for t in types])


@mcp.resource(
    "banking://faq",
    name="firstbank_faq",
    description="Frequently asked questions by banking customers with answers and guidance on common requests like opening accounts, password reset, and transfer limits."
)
def get_faq() -> str:
    """Frequently asked questions for banking customers."""
    faqs = [
        {"q": "How do I open an account?", "a": "Provide your info and I will use the open_account tool."},
        {"q": "How to reset my password?", "a": "Use the secure reset_password tool after authentication."},
        {"q": "What is the daily transfer limit?", "a": "The daily limit is ₦500,000 for individual accounts."},
    ]
    return "\n".join([f"Q: {f['q']}\nA: {f['a']}\n---" for f in faqs])
    





# ==========================
# 🔹 SSE SERVER
# ==========================
# --- SSE Server ---
def create_starlette_app(mcp_server):
    from mcp.server.sse import SseServerTransport
    from starlette.responses import Response # Add this

    sse = SseServerTransport("/messages/")

    async def handle_sse(request):
        # Use request.scope, receive, and send from the request object
        async with sse.connect_sse(
            request.scope, 
            request.receive, 
            request._send # Note: Starlette requests have _send internally
        ) as (read_stream, write_stream):
            await mcp_server.run(
                read_stream,
                write_stream,
                mcp_server.create_initialization_options(),
            )
        # Return an empty response to satisfy Starlette's requirement for a Response object
        return Response() 

    return Starlette(
        routes=[
            Route("/sse", endpoint=handle_sse),
            Mount("/messages/", app=sse.handle_post_message),
        ]
    )
    
    
# Create ASGI app at module level so uvicorn can import it
app = create_starlette_app(mcp._mcp_server)


port = os.getenv("PORT", "NOT SET")

if __name__ == "__main__":
    uvicorn.run(
        "mcp.server:app",
        host="0.0.0.0",
        port=int(port)
    )
