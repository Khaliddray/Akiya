import csv
import io
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.database import get_db_session, get_user_summary, get_active_debtors
from app.db.models import LedgerTransaction

router = APIRouter(prefix="/api", tags=["Ledger & Dashboard"])


@router.get("/summary/{phone}")
async def get_vendor_summary(phone: str):
    """Returns high-level business financial health metrics for a phone number."""
    summary = await get_user_summary(phone)
    return {
        "user_phone": phone,
        "metrics": summary
    }


@router.get("/ledger/{phone}")
async def get_vendor_transactions(
    phone: str, 
    limit: int = 50, 
    session: AsyncSession = Depends(get_db_session)
):
    """Returns historical transactions recorded via voice note."""
    query = (
        select(LedgerTransaction)
        .where(LedgerTransaction.user_phone == phone)
        .order_by(LedgerTransaction.created_at.desc())
        .limit(limit)
    )
    result = await session.execute(query)
    records = result.scalars().all()
    return {
        "user_phone": phone,
        "total_records": len(records),
        "transactions": [r.to_dict() for r in records]
    }


@router.get("/debts/{phone}")
async def get_vendor_debts(phone: str):
    """Returns active debtors and outstanding credit balances."""
    debts = await get_active_debtors(phone)
    return {
        "user_phone": phone,
        "active_debtors_count": len(debts),
        "debtors": debts
    }


@router.get("/ledger/{phone}/export/csv")
async def export_ledger_csv(
    phone: str, 
    session: AsyncSession = Depends(get_db_session)
):
    """Generates a downloadable CSV ledger statement for micro-finance loan applications."""
    query = (
        select(LedgerTransaction)
        .where(LedgerTransaction.user_phone == phone)
        .order_by(LedgerTransaction.created_at.asc())
    )
    result = await session.execute(query)
    records = result.scalars().all()

    if not records:
        raise HTTPException(status_code=404, detail="No transactions found for this user.")

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Timestamp (UTC)", "Type", "Amount (NGN)", "Category", "Description", "Language"])

    for r in records:
        writer.writerow([
            r.id,
            r.created_at.isoformat(),
            r.intent,
            f"{r.amount:.2f}",
            r.category,
            r.description,
            r.detected_language
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=akiya_ledger_{phone}.csv"}
    )
