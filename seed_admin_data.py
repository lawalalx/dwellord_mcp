import asyncio
import argparse
import os
from datetime import date, datetime, timedelta

from sqlalchemy import delete
from sqlalchemy.future import select
from sqlmodel import SQLModel

from admin_server import AdminRole, AdminUser, hash_password
from models import (
    AuditLog,
    Agency,
    Agent,
    Lead,
    LeadStatus,
    ListingType,
    Payment,
    Property,
    PropertyImage,
    PropertyOrder,
    PropertyReservation,
    PropertyStatus,
    PropertyType,
    Reminder,
    Subscription,
    Viewing,
    async_session,
    engine,
    init_db,
)


async def empty_database() -> None:
    async with engine.begin() as conn:
        # Delete from all known tables in reverse dependency order.
        for table in reversed(SQLModel.metadata.sorted_tables):
            await conn.execute(delete(table))

    print("Database reset completed (all tables emptied).")


async def run_seed() -> None:

    async with async_session() as session:
        existing_admin = await session.scalar(
            select(AdminUser).where(AdminUser.email == "admin@primeestates.com")
        )
        if existing_admin:
            print("Seed already exists. Skipping.")
            return

        agency_prime = Agency(
            name="Prime Estates",
            email="contact@primeestates.com",
            phone="+2348012345678",
            address="Lagos, Nigeria",
            created_at=datetime.utcnow(),
        )
        agency_elite = Agency(
            name="Elite Properties",
            email="hello@eliteprops.com",
            phone="+2348098765432",
            address="Abuja, Nigeria",
            created_at=datetime.utcnow(),
        )
        session.add_all([agency_prime, agency_elite])
        await session.flush()

        agent_temi = Agent(
            agency_id=agency_prime.id,
            full_name="Temitola Adeyemi",
            email="temi@primeestates.com",
            phone="+2348123456789",
            created_at=datetime.utcnow(),
        )
        agent_chinonso = Agent(
            agency_id=agency_elite.id,
            full_name="Chinonso Okeke",
            email="chinonso@eliteprops.com",
            phone="+2348187654321",
            created_at=datetime.utcnow(),
        )
        session.add_all([agent_temi, agent_chinonso])
        await session.flush()

        admin = AdminUser(
            id=os.urandom(16).hex(),
            email="admin@primeestates.com",
            full_name="Platform Admin",
            password_hash=hash_password("Admin@12345"),
            role=AdminRole.ADMIN,
            agency_id=agency_prime.id,
            is_active=True,
        )

        agent_user = AdminUser(
            id=os.urandom(16).hex(),
            email="temi@primeestates.com",
            full_name="Temitola Adeyemi",
            password_hash=hash_password("Agent@12345"),
            role=AdminRole.AGENT,
            agency_id=agency_prime.id,
            agent_id=agent_temi.id,
            is_active=True,
        )
        session.add_all([admin, agent_user])
        await session.flush()

        property_rows = [
            {
                "agent_id": agent_temi.id,
                "title": "Luxury 3 Bedroom Apartment",
                "description": "Spacious 3-bedroom apartment with sea view.",
                "location": "Victoria Island, Lagos",
                "price": 45_000_000,
                "bedrooms": 3,
                "bathrooms": 2,
                "property_type": PropertyType.THREE_BEDROOM_FLAT,
                "listing_type": ListingType.SALE,
            },
            {
                "agent_id": agent_temi.id,
                "title": "2 Bedroom Flat in Lekki",
                "description": "Modern 2-bedroom flat in a gated community.",
                "location": "Lekki, Lagos",
                "price": 18_000_000,
                "bedrooms": 2,
                "bathrooms": 2,
                "property_type": PropertyType.TWO_BEDROOM_FLAT,
                "listing_type": ListingType.SALE,
            },
            {
                "agent_id": agent_chinonso.id,
                "title": "Duplex with Garden",
                "description": "Beautiful 4-bedroom duplex with large garden.",
                "location": "Asokoro, Abuja",
                "price": 120_000_000,
                "bedrooms": 4,
                "bathrooms": 3,
                "property_type": PropertyType.DUPLEX,
                "listing_type": ListingType.SALE,
            },
            {
                "agent_id": agent_temi.id,
                "title": "Executive 2 Bedroom Apartment",
                "description": "Luxury serviced 2-bedroom apartment close to the waterfront.",
                "location": "Victoria Island, Lagos",
                "price": 38_000_000,
                "bedrooms": 2,
                "bathrooms": 2,
                "property_type": PropertyType.TWO_BEDROOM_FLAT,
                "listing_type": ListingType.SALE,
            },
            {
                "agent_id": agent_temi.id,
                "title": "Penthouse Apartment",
                "description": "Luxury penthouse with panoramic ocean views.",
                "location": "Victoria Island, Lagos",
                "price": 150_000_000,
                "bedrooms": 4,
                "bathrooms": 4,
                "property_type": PropertyType.DUPLEX,
                "listing_type": ListingType.SALE,
            },
            {
                "agent_id": agent_temi.id,
                "title": "Serviced Studio Apartment",
                "description": "Modern studio apartment perfect for professionals.",
                "location": "Victoria Island, Lagos",
                "price": 22_000_000,
                "bedrooms": 1,
                "bathrooms": 1,
                "property_type": PropertyType.ONE_BEDROOM_FLAT,
                "listing_type": ListingType.SALE,
            },
            {
                "agent_id": agent_temi.id,
                "title": "Lekki Terrace Duplex",
                "description": "Modern terrace duplex in a secure estate.",
                "location": "Lekki, Lagos",
                "price": 55_000_000,
                "bedrooms": 3,
                "bathrooms": 3,
                "property_type": PropertyType.DUPLEX,
                "listing_type": ListingType.SALE,
            },
            {
                "agent_id": agent_temi.id,
                "title": "Lekki Mini Flat",
                "description": "Affordable mini flat ideal for young professionals.",
                "location": "Lekki, Lagos",
                "price": 12_000_000,
                "bedrooms": 1,
                "bathrooms": 1,
                "property_type": PropertyType.ONE_BEDROOM_FLAT,
                "listing_type": ListingType.SALE,
            },
            {
                "agent_id": agent_chinonso.id,
                "title": "Luxury Asokoro Mansion",
                "description": "Massive 5-bedroom luxury mansion with private pool.",
                "location": "Asokoro, Abuja",
                "price": 350_000_000,
                "bedrooms": 5,
                "bathrooms": 5,
                "property_type": PropertyType.DUPLEX,
                "listing_type": ListingType.SALE,
            },
            {
                "agent_id": agent_chinonso.id,
                "title": "Asokoro 3 Bedroom Flat",
                "description": "Well-finished 3-bedroom flat in a serene environment.",
                "location": "Asokoro, Abuja",
                "price": 65_000_000,
                "bedrooms": 3,
                "bathrooms": 3,
                "property_type": PropertyType.THREE_BEDROOM_FLAT,
                "listing_type": ListingType.SALE,
            },
        ]

        properties: list[Property] = []
        for row in property_rows:
            properties.append(
                Property(
                    **row,
                    status=PropertyStatus.AVAILABLE,
                    created_at=datetime.utcnow(),
                )
            )

        session.add_all(properties)
        await session.flush()

        image_pairs = [
            ("https://picsum.photos/id/1011/800/600", "https://picsum.photos/id/1012/800/600"),
            ("https://picsum.photos/id/1013/800/600", "https://picsum.photos/id/1014/800/600"),
            ("https://picsum.photos/id/1015/800/600", "https://picsum.photos/id/1025/800/600"),
            ("https://picsum.photos/id/1026/800/600", "https://picsum.photos/id/1027/800/600"),
            ("https://picsum.photos/id/1031/800/600", "https://picsum.photos/id/1033/800/600"),
            ("https://picsum.photos/id/1035/800/600", "https://picsum.photos/id/1037/800/600"),
            ("https://picsum.photos/id/1040/800/600", "https://picsum.photos/id/1041/800/600"),
            ("https://picsum.photos/id/1042/800/600", "https://picsum.photos/id/1043/800/600"),
            ("https://picsum.photos/id/1044/800/600", "https://picsum.photos/id/1045/800/600"),
            ("https://picsum.photos/id/1047/800/600", "https://picsum.photos/id/1048/800/600"),
        ]

        images: list[PropertyImage] = []
        for index, property_obj in enumerate(properties):
            primary_url, secondary_url = image_pairs[index % len(image_pairs)]
            images.append(PropertyImage(property_id=property_obj.id, image_url=primary_url, is_primary=True))
            images.append(PropertyImage(property_id=property_obj.id, image_url=secondary_url, is_primary=False))

        session.add_all(images)
        await session.flush()

        lead_1 = Lead(
            property_id=properties[0].id,
            agent_id=agent_temi.id,
            user_full_name="Fola Ade",
            user_phone="+2348021122334",
            user_email="fola.ade@example.com",
            budget=50_000_000,
            preferred_viewing_date=date.today() + timedelta(days=3),
            message="I am very interested in this property.",
            status=LeadStatus.NEW,
            created_at=datetime.utcnow(),
        )

        lead_2 = Lead(
            property_id=properties[2].id,
            agent_id=agent_chinonso.id,
            user_full_name="Ngozi Obi",
            user_phone="+2348034455667",
            budget=125_000_000,
            message="Please schedule a viewing for next week.",
            status=LeadStatus.NEW,
            created_at=datetime.utcnow(),
        )
        session.add_all([lead_1, lead_2])
        await session.flush()

        session.add_all(
            [
                Viewing(
                    lead_id=lead_1.id,
                    scheduled_date=date.today() + timedelta(days=3),
                    confirmed=False,
                    created_at=datetime.utcnow(),
                ),
                Viewing(
                    lead_id=lead_2.id,
                    scheduled_date=date.today() + timedelta(days=7),
                    confirmed=False,
                    created_at=datetime.utcnow(),
                ),
            ]
        )

        await session.commit()

    print("Admin seed completed.")
    print("Admin login: admin@primeestates.com / Admin@12345")
    print("Agent login: temi@primeestates.com / Agent@12345")
    print("Sample properties, leads, and viewings have been created.")


async def main(reset: bool, reset_only: bool) -> None:
    await init_db()

    if reset or reset_only:
        await empty_database()

    if not reset_only:
        await run_seed()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed admin data for house-agent MCP")
    parser.add_argument("--reset", action="store_true", help="Reset all database tables before seeding")
    parser.add_argument("--reset-only", action="store_true", help="Reset all database tables and exit")
    args = parser.parse_args()

    asyncio.run(main(reset=args.reset, reset_only=args.reset_only))
