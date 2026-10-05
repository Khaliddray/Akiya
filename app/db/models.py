from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class LedgerTransaction(Base):
    __tablename__ = "ledger_transactions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_phone = Column(String(32), index=True, nullable=False)
    intent = Column(String(32), nullable=False)  # RECORD_SALE, RECORD_EXPENSE
    amount = Column(Float, nullable=False, default=0.0)
    category = Column(String(100), nullable=False, default="general")
    description = Column(String(255), nullable=True)
    debtor_or_creditor = Column(String(100), nullable=True)
    detected_language = Column(String(10), nullable=False, default="pcm")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "user_phone": self.user_phone,
            "intent": self.intent,
            "amount": self.amount,
            "category": self.category,
            "description": self.description,
            "debtor_or_creditor": self.debtor_or_creditor,
            "detected_language": self.detected_language,
            "created_at": self.created_at.isoformat()
        }


class CustomerDebt(Base):
    __tablename__ = "customer_debts"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_phone = Column(String(32), index=True, nullable=False)
    customer_name = Column(String(100), index=True, nullable=False)
    total_owed = Column(Float, nullable=False, default=0.0)
    total_paid = Column(Float, nullable=False, default=0.0)
    is_settled = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    @property
    def remaining_balance(self) -> float:
        return max(0.0, self.total_owed - self.total_paid)

    def to_dict(self):
        return {
            "id": self.id,
            "user_phone": self.user_phone,
            "customer_name": self.customer_name,
            "total_owed": self.total_owed,
            "total_paid": self.total_paid,
            "remaining_balance": self.remaining_balance,
            "is_settled": self.is_settled,
            "updated_at": self.updated_at.isoformat() if self.updated_at else self.created_at.isoformat()
        }
