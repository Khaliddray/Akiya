import logging
from typing import AsyncGenerator, List, Dict, Any
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select, func
from app.config import settings
from app.db.models import Base, LedgerTransaction, CustomerDebt

logger = logging.getLogger("monivoice.db")

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True
)

async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("[+] Database tables initialized.")

async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session

async def save_transaction(
    user_phone: str,
    intent: str,
    amount: float,
    category: str,
    description: str,
    debtor_or_creditor: str | None = None,
    detected_language: str = "pcm"
) -> LedgerTransaction:
    async with async_session_maker() as session:
        txn = LedgerTransaction(
            user_phone=user_phone,
            intent=intent,
            amount=amount,
            category=category,
            description=description,
            debtor_or_creditor=debtor_or_creditor,
            detected_language=detected_language
        )
        session.add(txn)
        await session.commit()
        await session.refresh(txn)
        return txn

async def get_user_summary(user_phone: str) -> Dict[str, Any]:
    async with async_session_maker() as session:
        sales_query = select(func.coalesce(func.sum(LedgerTransaction.amount), 0.0)).where(
            LedgerTransaction.user_phone == user_phone,
            LedgerTransaction.intent == "RECORD_SALE"
        )
        expenses_query = select(func.coalesce(func.sum(LedgerTransaction.amount), 0.0)).where(
            LedgerTransaction.user_phone == user_phone,
            LedgerTransaction.intent == "RECORD_EXPENSE"
        )
        debt_query = select(CustomerDebt).where(
            CustomerDebt.user_phone == user_phone,
            CustomerDebt.is_settled == False
        )

        sales_res = await session.execute(sales_query)
        expenses_res = await session.execute(expenses_query)
        debt_res = await session.execute(debt_query)

        total_sales = sales_res.scalar() or 0.0
        total_expenses = expenses_res.scalar() or 0.0
        active_debts = debt_res.scalars().all()
        total_debt_owed = sum(d.remaining_balance for d in active_debts)

        return {
            "total_sales": total_sales,
            "total_expenses": total_expenses,
            "net_balance": total_sales - total_expenses,
            "total_debt_owed": total_debt_owed,
            "active_debtors_count": len(active_debts)
        }

async def record_customer_credit(user_phone: str, customer_name: str, amount: float) -> CustomerDebt:
    """Creates or increments credit given to a customer."""
    async with async_session_maker() as session:
        query = select(CustomerDebt).where(
            CustomerDebt.user_phone == user_phone,
            func.lower(CustomerDebt.customer_name) == customer_name.strip().lower(),
            CustomerDebt.is_settled == False
        )
        res = await session.execute(query)
        debt = res.scalar_one_or_none()

        if debt:
            debt.total_owed += amount
        else:
            debt = CustomerDebt(
                user_phone=user_phone,
                customer_name=customer_name.strip(),
                total_owed=amount,
                total_paid=0.0
            )
            session.add(debt)

        await session.commit()
        await session.refresh(debt)
        return debt

async def settle_customer_debt(user_phone: str, customer_name: str, amount_paid: float) -> CustomerDebt | None:
    """Applies payment toward a customer's outstanding balance."""
    async with async_session_maker() as session:
        query = select(CustomerDebt).where(
            CustomerDebt.user_phone == user_phone,
            func.lower(CustomerDebt.customer_name) == customer_name.strip().lower(),
            CustomerDebt.is_settled == False
        )
        res = await session.execute(query)
        debt = res.scalar_one_or_none()

        if not debt:
            return None

        debt.total_paid += amount_paid
        if debt.total_paid >= debt.total_owed:
            debt.is_settled = True

        await session.commit()
        await session.refresh(debt)
        return debt

async def get_active_debtors(user_phone: str) -> List[Dict[str, Any]]:
    """Returns list of all customers currently owing the vendor."""
    async with async_session_maker() as session:
        query = select(CustomerDebt).where(
            CustomerDebt.user_phone == user_phone,
            CustomerDebt.is_settled == False
        )
        res = await session.execute(query)
        debts = res.scalars().all()
        return [d.to_dict() for d in debts if d.remaining_balance > 0]
