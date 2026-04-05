# get_account.py
import asyncio, random
from sqlmodel import select

from models import async_session, Account, Customer, Bank

async def get_all_accounts():
    async with async_session() as session:
        statement = (
            select(
                Account,
                Customer.full_name,
                Customer.email,
                Customer.phone,
                Bank.name,
                Bank.code
            )
            .join(Customer, Account.customer_id == Customer.id)
            .join(Bank, Account.bank_id == Bank.id)
        )
        result = await session.exec(statement)
        accounts = result.all()

        for acc, cust_name, cust_email, cust_phone, bank_name, bank_code in accounts:
            print(f"Account ID: {acc.id}")
            print(f"Account Number: {acc.account_number}")
            print(f"Account Name: {acc.account_name}")
            print(f"Account Type: {acc.account_type}")
            print(f"Balance: ₦{acc.balance}")
            print(f"Customer Name: {cust_name}")
            print(f"Customer Email: {cust_email}")
            print(f"Customer Phone: {cust_phone}")
            print(f"Bank Name: {bank_name}")
            print(f"Bank Code: {bank_code}")
            print("-" * 40)

# if __name__ == "__main__":
#     asyncio.run(get_all_accounts())


async def delete_customer_pin(customer_id: int):
    """
    Resets a customer's transaction PIN.
    Sets:
    - has_pin = False
    - pin_hash = None
    - pending_pin_creation = False
    - pin_attempts = 0
    - pin_blocked_until = None
    """

    async with async_session() as session:
        customer = await session.get(Customer, customer_id)

        if not customer:
            print("Customer not found.")
            return

        customer.has_pin = False
        customer.pin_hash = None
        customer.pending_pin_creation = False
        customer.pin_attempts = 0
        customer.pin_blocked_until = None

        await session.commit()

        print(f"✅ PIN removed successfully for Customer ID: {customer_id}")





import random
from datetime import date # <--- Make sure this is imported
from sqlalchemy import select
from .models import Customer, Account, Bank, async_session

async def add_firstbank_customer(
    full_name: str, 
    phone: str, 
    email: str, 
    dob: date, # <--- Added this parameter
    initial_balance: float = 250000.0
):
    async with async_session() as session:
        result = await session.execute(select(Bank).where(Bank.name == "FirstBank"))
        firstbank = result.scalar_one_or_none()
        
        if not firstbank:
            print("Error: FirstBank not found.")
            return

        new_customer = Customer(
            bank_id=firstbank.id,
            full_name=full_name,
            email=email,
            phone=phone,
            date_of_birth=dob, # <--- Now passing the date
            is_validated=True,
            has_pin=False
        )
        session.add(new_customer)
        await session.flush() 

        account_num = f"30{random.randint(10000000, 99999999)}"
        new_account = Account(
            customer_id=new_customer.id,
            bank_id=firstbank.id,
            account_name=new_customer.full_name,
            account_number=account_num,
            account_type="Savings",
            balance=initial_balance
        )
        session.add(new_account)
        
        await session.commit()
        print(f"✅ Created: {full_name} | Phone: {phone} | Account: {account_num}")


# --- UPDATED RUN FUNCTION ---
async def run_specific_seed():
    await add_firstbank_customer(
        full_name="Emmanuel Dev", 
        phone="2349037020418", 
        email="dev@example.com",
        dob=date(1995, 1, 1) 
    )

    
if __name__ == "__main__":
    asyncio.run(delete_customer_pin(3))
    # asyncio.run(get_all_accounts())
