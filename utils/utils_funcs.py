from sqlmodel import select
from typing import List
from datetime import datetime, date, timedelta, time

from sqlmodel.ext.asyncio.session import AsyncSession

from models import (
    async_session,
    Lead,
    Viewing,
    PropertyOrder,
    Property,
)

async def fetch_agent_leads(agent_id: str) -> List[Lead]:
    """Fetch active leads for a specific agent, ordered by creation date descending."""
    async with async_session() as session:
        result = await session.exec(
            select(Lead)
            .where(Lead.agent_id == agent_id)
            .order_by(Lead.created_at.desc())
        )
        return result.all()


async def fetch_agent_viewings(agent_id: str) -> List[Viewing]:
    """Fetch upcoming viewings for an agent's leads."""
    async with async_session() as session:
        # Join lead -> viewing
        result = await session.exec(
            select(Viewing)
            .join(Lead, Viewing.lead_id == Lead.id)
            .where(Lead.agent_id == agent_id)
            .order_by(Viewing.scheduled_date.asc())
        )
        return result.all()


async def fetch_agent_orders(agent_id: str) -> List[PropertyOrder]:
    """Fetch submitted orders for an agent, newest first."""
    async with async_session() as session:
        result = await session.exec(
            select(PropertyOrder)
            .join(Property, PropertyOrder.property_id == Property.id)
            .where(Property.agent_id == agent_id)
            .order_by(PropertyOrder.created_at.desc())
        )
        return result.all()



async def resolve_agent(session: AsyncSession, property_id: str) -> str:
    """
    Resolves the agent responsible for a property.
    Raises ValueError if property or agent is not found.
    """
    property_obj = await session.get(Property, property_id)
    if not property_obj:
        raise ValueError(f"Property with id {property_id} not found")

    if not property_obj.agent_id:
        # Optional: implement logic to auto-assign or pick a default agent
        raise ValueError(f"No agent assigned to property {property_id}")

    return property_obj.agent_id



async def resolve_agent(session: AsyncSession, property_id: str) -> str:
    """
    Resolves the agent responsible for a property.
    Raises ValueError if property or agent is not found.
    """
    property_obj = await session.get(Property, property_id)
    if not property_obj:
        raise ValueError(f"Property with id {property_id} not found")

    if not property_obj.agent_id:
        # Optionally: assign default agent logic here
        raise ValueError(f"No agent assigned to property {property_id}")

    return property_obj.agent_id




async def query_available_slots(agent_id: str, from_date: date, to_date: date) -> list[dict]:
    """
    Returns available viewing slots for an agent between `from_date` and `to_date`.
    Only slots that are not booked (confirmed=False) are returned.
    """
    async with async_session() as session:
        # Join Viewing -> Lead -> Property -> Agent to ensure correct agent
        result = await session.execute(
            select(Viewing)
            .join(Lead, Viewing.lead_id == Lead.id)
            .join(Property, Lead.property_id == Property.id)
            .where(
                Property.agent_id == agent_id,
                Viewing.confirmed == False,
                Viewing.scheduled_date >= from_date,
                Viewing.scheduled_date <= to_date
            )
        )
        slots = result.scalars().all()

        # Return as dicts for MCP-friendly responses
        return [
            {
                "slot_id": slot.id,
                "lead_id": slot.lead_id,
                "scheduled_date": slot.scheduled_date,
                "confirmed": slot.confirmed
            }
            for slot in slots
        ]
