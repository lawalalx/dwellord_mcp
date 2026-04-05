from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List
from datetime import datetime, date, timedelta, time
from enum import Enum


# ============================================================
# 🔹 BASE RESPONSE (All tools inherit from this)
# ============================================================

class MCPResponse(BaseModel):
    success: bool = Field(..., description="Whether the operation succeeded")
    message: str = Field(..., description="Human-readable explanation")
    error_code: Optional[str] = Field(
        None,
        description="Machine-readable error code for deterministic handling"
    )


# ============================================================
# 🔹 PROPERTY SCHEMAS
# ============================================================
class PropertyItem(BaseModel):
    id: Optional[str]  = Field(None, description="Unique identifier for the property")
    title: Optional[str]  = Field(None, description="Short title of the property")
    location: Optional[str]  = Field(None, description="Location or address of the property")
    price: float = Field(..., description="Price of the property in NGN")
    bedrooms: Optional[int] = Field(None, description="Number of bedrooms")
    property_type: Optional[str]  = Field(None, description="Type of property (flat, duplex, land, etc.)")
    image_url: Optional[str] = Field(None, description="URL of the main property image")
    # agent_id: Optional[str] = Field(None, description="Agent ID for this property")
    property_id: Optional[str]  = Field(None, description="Unique identifier for the property")


class PropertySearchResponse(MCPResponse):
    results: List[PropertyItem] = Field([], description="List of properties matching the search")


class PropertyDetailResponse(MCPResponse):
    id: Optional[str] = Field(None, description="Unique identifier for the property")
    title: Optional[str] = Field(None, description="Title of the property")
    description: Optional[str] = Field(None, description="Full description of the property")
    location: Optional[str] = Field(None, description="Address or location of the property")
    price: Optional[float] = Field(None, description="Price of the property in NGN")
    bedrooms: Optional[int] = Field(None, description="Number of bedrooms")
    bathrooms: Optional[int] = Field(None, description="Number of bathrooms")
    images: Optional[List[str]] = Field(None, description="List of image URLs for the property")
    agent_id: Optional[str] = Field(None, description="ID of the agent managing this property")

# ============================================================
# 🔹 AGENT SCHEMAS
# ============================================================
class AgentContactResponse(MCPResponse):
    agent_name: Optional[str] = Field(None, description="Full name of the agent")
    phone: Optional[str] = Field(None, description="Phone number of the agent")
    email: Optional[EmailStr] = Field(None, description="Email address of the agent")
    agency_name: Optional[str] = Field(None, description="Name of the real estate agency")



class ClientInfo(BaseModel):
    client_name: str = Field(..., description="Full name of the client")
    client_phone: str = Field(..., description="Client phone number")
    client_email: Optional[str] = Field(None, description="Client email address")
    
class CreatePropertyLeadRequest(ClientInfo):
    property_id: Optional[str]
    message: Optional[str] = Field(
        None,
        description="Optional message from the client to the agent"
    )

class ScheduleViewingRequest(ClientInfo):
    property_id: str
    preferred_date: date = Field(
        ...,
        description="Preferred viewing date"
    )

class ViewingResponse(MCPResponse):
    viewing_id: Optional[str] = None
    scheduled_date: Optional[date] = None

class ReservePropertyRequest(ClientInfo):
    property_id: str
    reservation_days: int = Field(
        3,
        ge=1,
        le=14,
        description="Number of days to hold the property"
    )

class ReservationResponse(MCPResponse):
    reservation_id: Optional[str] = None
    expires_at: Optional[datetime] = None

class PlacePropertyOrderRequest(ClientInfo):
    property_id: str
    offer_amount: float = Field(
        ...,
        gt=0,
        description="Client offer amount in Naira"
    )
    message: Optional[str] = Field(
        None,
        description="Optional negotiation or note"
    )


class OrderResponse(MCPResponse):
    order_id: Optional[str] = None
    offer_amount: Optional[float] = None
    status: Optional[str] = None

class PendingAction(BaseModel):
    tool_name: str
    args: dict
    property_id: str
    summary: str

class ConfirmationState(MCPResponse):
    awaiting_confirmation: bool = False
    pending_action: Optional[PendingAction] = None
    


class PaymentResponse(MCPResponse):
    payment_id: str
    payment_url: str
    
    

# ============================================================
# 🔹 AgentAvailability SCHEMAS
# ============================================================
class AgentAvailability(MCPResponse):
    agent_id: str
    date: date
    start_time: time
    end_time: time
    

class ViewingSlot(MCPResponse):
    slot_id: str
    date: date
    start_time: time
    end_time: time
    available: bool


class AgentLeadSummary(MCPResponse):
    lead_id: str
    property_title: str
    client_name: str
    client_phone: str
    status: str
    created_at: datetime
    


class AgentDashboardResponse(MCPResponse):
    leads: List = []
    viewings: List = []
    orders: List = []

class AvailabilityResponse(MCPResponse):
    slots: List = []

class AgentContactResponse(MCPResponse):
    agent_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    agency_name: Optional[str] = None

class ReservationResponse(MCPResponse):
    pass

class OrderResponse(MCPResponse):
    pass

class PaymentResponse(MCPResponse):
    payment_id: Optional[str] = None
    payment_url: Optional[str] = None
    
    
# ============================================================
# 🔹 LEAD SCHEMAS
# ============================================================
class LeadResponse(MCPResponse):
    lead_id: Optional[str] = None
