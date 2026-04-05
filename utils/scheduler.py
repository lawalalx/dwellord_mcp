
import asyncio
from datetime import datetime
from sqlalchemy.future import select
from datetime import datetime, date, timedelta, time

from run_periodic_task import run_periodic_task
from models import (
    async_session,
    PropertyReservation, 
    Property, 
    Reminder,
    PropertyStatus,
    Lead,
    Viewing
)

async def reservation_expiry_worker():
    while True:
        async with async_session() as session:
            now = datetime.utcnow()
            expired_reservations = await session.exec(
                select(PropertyReservation)
                .where(PropertyReservation.expires_at <= now)
                .where(PropertyReservation.status == "pending")
            )
            for res in expired_reservations:
                res.status = "expired"
                property_obj = await session.get(Property, res.property_id)
                if property_obj:
                    property_obj.status = "available"
                    session.add(property_obj)
                session.add(res)
            await session.commit()
        await asyncio.sleep(60)  # run every minute

async def reminder_worker():
    while True:
        async with async_session() as session:
            now = datetime.utcnow()
            reminders = await session.exec(
                select(Reminder)
                .where(Reminder.scheduled_at <= now)
                .where(Reminder.sent == False)
            )
            for rem in reminders:
                # Here you would trigger an SMS/email
                print(f"Sending reminder for {rem.user_phone} about {rem.property_id}")
                rem.sent = True
                session.add(rem)
            await session.commit()
        await asyncio.sleep(60)
        



async def expire_reservations():
    async with async_session() as session:
        now = datetime.utcnow()
        reservations = await session.execute(
            select(PropertyReservation)
            .where(PropertyReservation.expires_at <= now)
        )
        for r in reservations.scalars():
            property_obj = await session.get(Property, r.property_id)
            if property_obj:
                property_obj.status = PropertyStatus.AVAILABLE
            await session.delete(r)
        await session.commit()




async def send_viewing_reminders():
    async with async_session() as session:
        now = datetime.utcnow()
        reminder_time = now + timedelta(hours=24)
        viewings = await session.execute(
            select(Viewing).where(
                Viewing.scheduled_date.between(reminder_time - timedelta(minutes=1),
                                              reminder_time + timedelta(minutes=1)),
                Viewing.reminder_sent == False
            )
        )
        for v in viewings.scalars():
            lead = await session.get(Lead, v.lead_id)
            # Send SMS/notification to lead.user_phone
            # mark reminder as sent
            v.reminder_sent = True
        await session.commit()





asyncio.create_task(reservation_expiry_worker())
asyncio.create_task(reminder_worker())

# Run every 10 minutes (or configurable)
asyncio.create_task(run_periodic_task(expire_reservations, interval=600))
asyncio.create_task(run_periodic_task(send_viewing_reminders, interval=3600))
