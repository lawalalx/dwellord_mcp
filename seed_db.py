# seed.py
import asyncio
from datetime import datetime, date, timedelta
from models import (
    engine,
    async_session,
    init_db,
    Agency,
    Agent,
    Property,
    PropertyImage,
    Lead,
    Viewing,
    ListingType,
    PropertyStatus,
    PropertyType,
    LeadStatus,
)

# ----------------------------------------------------
# 🔹 Seed Data
# ----------------------------------------------------

async def seed_data():
    # Initialize DB
    await init_db()

    async with async_session() as session:

        # ---------------------------
        # 1️⃣ Agencies
        # ---------------------------
        agency1 = Agency(
            name="Prime Estates",
            email="contact@primeestates.com",
            phone="+2348012345678",
            address="Lagos, Nigeria",
            created_at=datetime.utcnow()
        )

        agency2 = Agency(
            name="Elite Properties",
            email="hello@eliteprops.com",
            phone="+2348098765432",
            address="Abuja, Nigeria",
            created_at=datetime.utcnow()
        )

        session.add_all([agency1, agency2])
        await session.commit()

        # ---------------------------
        # 2️⃣ Agents
        # ---------------------------
        agent1 = Agent(
            full_name="Temitola Adeyemi",
            email="temi@primeestates.com",
            phone="+2348123456789",
            agency_id=agency1.id,
            created_at=datetime.utcnow()
        )

        agent2 = Agent(
            full_name="Chinonso Okeke",
            email="chinonso@eliteprops.com",
            phone="+2348187654321",
            agency_id=agency2.id,
            created_at=datetime.utcnow()
        )

        session.add_all([agent1, agent2])
        await session.commit()

        # ---------------------------
        # 3️⃣ Properties
        # ---------------------------
        prop1 = Property(
            title="Luxury 3 Bedroom Apartment",
            description="Spacious 3-bedroom apartment with sea view.",
            location="Victoria Island, Lagos",
            price=45_000_000,
            bedrooms=3,
            bathrooms=2,
            property_type=PropertyType.THREE_BEDROOM_FLAT,
            listing_type=ListingType.SALE,
            status=PropertyStatus.AVAILABLE,
            agent_id=agent1.id,
            created_at=datetime.utcnow()
        )

        prop2 = Property(
            title="2 Bedroom Flat in Lekki",
            description="Modern 2-bedroom flat in a gated community.",
            location="Lekki, Lagos",
            price=18_000_000,
            bedrooms=2,
            bathrooms=2,
            property_type=PropertyType.TWO_BEDROOM_FLAT,
            listing_type=ListingType.SALE,
            status=PropertyStatus.AVAILABLE,
            agent_id=agent1.id,
            created_at=datetime.utcnow()
        )

        prop3 = Property(
            title="Duplex with Garden",
            description="Beautiful 4-bedroom duplex with large garden.",
            location="Asokoro, Abuja",
            price=120_000_000,
            bedrooms=4,
            bathrooms=3,
            property_type=PropertyType.DUPLEX,
            listing_type=ListingType.SALE,
            status=PropertyStatus.AVAILABLE,
            agent_id=agent2.id,
            created_at=datetime.utcnow()
        )
        
        
        # Victoria Island additional properties
        prop4 = Property(
            title="Executive 2 Bedroom Apartment",
            description="Luxury serviced 2-bedroom apartment close to the waterfront.",
            location="Victoria Island, Lagos",
            price=38_000_000,
            bedrooms=2,
            bathrooms=2,
            property_type=PropertyType.TWO_BEDROOM_FLAT,
            listing_type=ListingType.SALE,
            status=PropertyStatus.AVAILABLE,
            agent_id=agent1.id,
            created_at=datetime.utcnow()
        )

        prop5 = Property(
            title="Penthouse Apartment",
            description="Luxury penthouse with panoramic ocean views.",
            location="Victoria Island, Lagos",
            price=150_000_000,
            bedrooms=4,
            bathrooms=4,
            property_type=PropertyType.DUPLEX,
            listing_type=ListingType.SALE,
            status=PropertyStatus.AVAILABLE,
            agent_id=agent1.id,
            created_at=datetime.utcnow()
        )

        prop6 = Property(
            title="Serviced Studio Apartment",
            description="Modern studio apartment perfect for professionals.",
            location="Victoria Island, Lagos",
            price=22_000_000,
            bedrooms=1,
            bathrooms=1,
            property_type=PropertyType.ONE_BEDROOM_FLAT,
            listing_type=ListingType.SALE,
            status=PropertyStatus.AVAILABLE,
            agent_id=agent1.id,
            created_at=datetime.utcnow()
        )


        # Lekki additional properties
        prop7 = Property(
            title="Lekki Terrace Duplex",
            description="Modern terrace duplex in a secure estate.",
            location="Lekki, Lagos",
            price=55_000_000,
            bedrooms=3,
            bathrooms=3,
            property_type=PropertyType.DUPLEX,
            listing_type=ListingType.SALE,
            status=PropertyStatus.AVAILABLE,
            agent_id=agent1.id,
            created_at=datetime.utcnow()
        )

        prop8 = Property(
            title="Lekki Mini Flat",
            description="Affordable mini flat ideal for young professionals.",
            location="Lekki, Lagos",
            price=12_000_000,
            bedrooms=1,
            bathrooms=1,
            property_type=PropertyType.ONE_BEDROOM_FLAT,
            listing_type=ListingType.SALE,
            status=PropertyStatus.AVAILABLE,
            agent_id=agent1.id,
            created_at=datetime.utcnow()
        )


        # Asokoro additional properties
        prop9 = Property(
            title="Luxury Asokoro Mansion",
            description="Massive 5-bedroom luxury mansion with private pool.",
            location="Asokoro, Abuja",
            price=350_000_000,
            bedrooms=5,
            bathrooms=5,
            property_type=PropertyType.DUPLEX,
            listing_type=ListingType.SALE,
            status=PropertyStatus.AVAILABLE,
            agent_id=agent2.id,
            created_at=datetime.utcnow()
        )

        prop10 = Property(
            title="Asokoro 3 Bedroom Flat",
            description="Well-finished 3-bedroom flat in a serene environment.",
            location="Asokoro, Abuja",
            price=65_000_000,
            bedrooms=3,
            bathrooms=3,
            property_type=PropertyType.THREE_BEDROOM_FLAT,
            listing_type=ListingType.SALE,
            status=PropertyStatus.AVAILABLE,
            agent_id=agent2.id,
            created_at=datetime.utcnow()
        )

        session.add_all([
            prop1, prop2, 
            prop3, prop4, 
            prop5, prop6, 
            prop7, prop8, 
            prop9, prop10
        ])
        await session.commit()

        # ---------------------------
        # 4️⃣ Property Images
        # ---------------------------
        images = [
            PropertyImage(property_id=prop1.id, image_url="https://picsum.photos/id/1011/800/600", is_primary=True),
            PropertyImage(property_id=prop1.id, image_url="https://picsum.photos/id/1012/800/600"),
            PropertyImage(property_id=prop2.id, image_url="https://picsum.photos/id/1013/800/600", is_primary=True),
            PropertyImage(property_id=prop3.id, image_url="https://picsum.photos/id/1014/800/600", is_primary=True),
            PropertyImage(property_id=prop3.id, image_url="https://picsum.photos/id/1015/800/600"),
            
            PropertyImage(property_id=prop4.id, image_url="https://picsum.photos/id/1011/800/600", is_primary=True),
            PropertyImage(property_id=prop4.id, image_url="https://picsum.photos/id/1012/800/600"),
            PropertyImage(property_id=prop5.id, image_url="https://picsum.photos/id/1013/800/600", is_primary=True),
            PropertyImage(property_id=prop5.id, image_url="https://picsum.photos/id/1014/800/600", is_primary=True),
            PropertyImage(property_id=prop4.id, image_url="https://picsum.photos/id/1015/800/600"),
            PropertyImage(property_id=prop6.id, image_url="https://picsum.photos/id/1011/800/600", is_primary=True),
            PropertyImage(property_id=prop5.id, image_url="https://picsum.photos/id/1012/800/600"),
            PropertyImage(property_id=prop5.id, image_url="https://picsum.photos/id/1013/800/600", is_primary=True),
            PropertyImage(property_id=prop6.id, image_url="https://picsum.photos/id/1014/800/600", is_primary=True),
            PropertyImage(property_id=prop6.id, image_url="https://picsum.photos/id/1015/800/600"),
            PropertyImage(property_id=prop7.id, image_url="https://picsum.photos/id/1025/800/600", is_primary=True),
            PropertyImage(property_id=prop7.id, image_url="https://picsum.photos/id/1026/800/600"),
            PropertyImage(property_id=prop8.id, image_url="https://picsum.photos/id/1027/800/600", is_primary=True),
            PropertyImage(property_id=prop9.id, image_url="https://picsum.photos/id/1031/800/600", is_primary=True),
            PropertyImage(property_id=prop9.id, image_url="https://picsum.photos/id/1033/800/600"),
            PropertyImage(property_id=prop10.id, image_url="https://picsum.photos/id/1035/800/600", is_primary=True),
            PropertyImage(property_id=prop10.id, image_url="https://picsum.photos/id/1037/800/600"),
        ]

        session.add_all(images)
        await session.commit()

        # ---------------------------
        # 5️⃣ Leads
        # ---------------------------
        lead1 = Lead(
            property_id=prop1.id,
            agent_id=agent1.id,
            user_full_name="Fola Ade",
            user_phone="+2348021122334",
            user_email="fola.ade@example.com",
            budget=50_000_000,
            preferred_viewing_date=date.today() + timedelta(days=3),
            message="I am very interested in this property.",
            status=LeadStatus.NEW,
            created_at=datetime.utcnow()
        )

        lead2 = Lead(
            property_id=prop3.id,
            agent_id=agent2.id,
            user_full_name="Ngozi Obi",
            user_phone="+2348034455667",
            budget=125_000_000,
            message="Please schedule a viewing for next week.",
            status=LeadStatus.NEW,
            created_at=datetime.utcnow()
        )

        session.add_all([lead1, lead2])
        await session.commit()

        # ---------------------------
        # 6️⃣ Viewings
        # ---------------------------
        viewing1 = Viewing(
            lead_id=lead1.id,
            scheduled_date=date.today() + timedelta(days=3),
            confirmed=False,
            created_at=datetime.utcnow()
        )

        viewing2 = Viewing(
            lead_id=lead2.id,
            scheduled_date=date.today() + timedelta(days=7),
            confirmed=False,
            created_at=datetime.utcnow()
        )

        session.add_all([viewing1, viewing2])
        await session.commit()

        print("✅ Database seeded successfully!")

# Run
if __name__ == "__main__":
    asyncio.run(seed_data())
