import asyncio
import os
from datetime import datetime, timedelta

from sqlalchemy.future import select

from admin_server import AdminRole, AdminUser, hash_password
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
    init_db,
)


async def run_seed() -> None:
    await init_db()

    async with async_session() as session:
        existing_admin = await session.scalar(
            select(AdminUser).where(AdminUser.email == "admin@electrahomes.com")
        )
        if existing_admin:
            print("Seed already exists. Skipping.")
            return

        agency = Agency(
            name="Electra Homes",
            email="hello@electrahomes.com",
            phone="+2348011122233",
            address="Victoria Island, Lagos",
            created_at=datetime.utcnow(),
        )
        session.add(agency)
        await session.flush()

        agent_a = Agent(
            agency_id=agency.id,
            full_name="Adaora Nnaji",
            email="adaora@electrahomes.com",
            phone="+2348110000001",
            created_at=datetime.utcnow(),
        )
        agent_b = Agent(
            agency_id=agency.id,
            full_name="Tunde Balogun",
            email="tunde@electrahomes.com",
            phone="+2348110000002",
            created_at=datetime.utcnow(),
        )
        session.add_all([agent_a, agent_b])
        await session.flush()

        admin = AdminUser(
            id=os.urandom(16).hex(),
            email="admin@electrahomes.com",
            full_name="Platform Admin",
            password_hash=hash_password("Admin@12345"),
            role=AdminRole.ADMIN,
            agency_id=agency.id,
            is_active=True,
        )

        agent_user = AdminUser(
            id=os.urandom(16).hex(),
            email="adaora@electrahomes.com",
            full_name="Adaora Nnaji",
            password_hash=hash_password("Agent@12345"),
            role=AdminRole.AGENT,
            agency_id=agency.id,
            agent_id=agent_a.id,
            is_active=True,
        )
        session.add_all([admin, agent_user])
        await session.flush()

        property_a = Property(
            agent_id=agent_a.id,
            title="Azure Crest 3BR Waterfront",
            description="Premium 3-bedroom apartment with skyline and lagoon views.",
            location="Victoria Island, Lagos",
            price=185000000,
            bedrooms=3,
            bathrooms=3,
            property_type=PropertyType.THREE_BEDROOM_FLAT,
            listing_type=ListingType.SALE,
            status=PropertyStatus.AVAILABLE,
            created_at=datetime.utcnow(),
        )
        property_b = Property(
            agent_id=agent_b.id,
            title="Luxe Purple 2BR Loft",
            description="Designer loft in a secure serviced estate.",
            location="Lekki Phase 1, Lagos",
            price=7500000,
            bedrooms=2,
            bathrooms=2,
            property_type=PropertyType.TWO_BEDROOM_FLAT,
            listing_type=ListingType.RENT,
            status=PropertyStatus.AVAILABLE,
            created_at=datetime.utcnow(),
        )
        session.add_all([property_a, property_b])
        await session.flush()

        images = [
            PropertyImage(property_id=property_a.id, image_url="https://images.unsplash.com/photo-1560185007-cde436f6a4d0", is_primary=True),
            PropertyImage(property_id=property_b.id, image_url="https://images.unsplash.com/photo-1613977257368-707ba9348227", is_primary=True),
        ]
        session.add_all(images)
        await session.flush()

        lead = Lead(
            property_id=property_a.id,
            agent_id=agent_a.id,
            user_full_name="Femi Adewale",
            user_phone="+2348012349901",
            user_email="femi@example.com",
            budget=170000000,
            message="I need this for my family, can I inspect this Saturday?",
            status=LeadStatus.NEW,
            created_at=datetime.utcnow(),
        )
        session.add(lead)
        await session.flush()

        viewing = Viewing(
            lead_id=lead.id,
            scheduled_date=(datetime.utcnow() + timedelta(days=2)).date(),
            confirmed=False,
            created_at=datetime.utcnow(),
        )
        session.add(viewing)

        await session.commit()

    print("Admin seed completed.")
    print("Admin login: admin@electrahomes.com / Admin@12345")
    print("Agent login: adaora@electrahomes.com / Agent@12345")


if __name__ == "__main__":
    asyncio.run(run_seed())
