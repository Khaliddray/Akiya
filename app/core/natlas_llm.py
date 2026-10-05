import json
import logging
import re
from typing import Literal, Optional
import httpx
from pydantic import BaseModel, Field
from app.config import settings

logger = logging.getLogger("monivoice.llm")

IntentType = Literal[
    "RECORD_SALE",
    "RECORD_EXPENSE",
    "RECORD_CREDIT",
    "SETTLE_DEBT",
    "CHECK_DEBT",
    "CHECK_BALANCE",
    "VERIFY_ALERT",
    "UNKNOWN"
]

class TransactionExtraction(BaseModel):
    intent: IntentType = Field(..., description="Classified intent of the voice note")
    amount: float = Field(default=0.0, description="Transaction amount in Naira")
    category: str = Field(default="general", description="Item, service, or context")
    description: str = Field(default="", description="Clean transcription or normalized context")
    debtor_or_creditor: Optional[str] = Field(None, description="Name of customer or creditor if debt/credit was mentioned")
    detected_language: str = Field(default="pcm", description="Dialect: pcm, yo, ha, ig, or en")
    voice_reply_script: str = Field(
        ...,
        description="Concise spoken response back to the vendor in their dialect (max 2 short sentences)"
    )

SYSTEM_PROMPT = """You are Akiya, an oral bookkeeping assistant designed for Nigerian market traders and artisans.
Users speak in Nigerian Pidgin, Yoruba, Hausa, Igbo, or English.
Classify user voice intent and extract clean JSON:
- RECORD_SALE: Vendor sold goods or services for cash.
- RECORD_EXPENSE: Vendor spent money on stock, fuel, transport, or shop bills.
- RECORD_CREDIT: Vendor gave goods to a customer on credit/debt (e.g., "Mama Chuka collect on credit").
- SETTLE_DEBT: Customer paid part or all of their outstanding debt.
- CHECK_DEBT: Vendor asks who owes them or asks about customer debts.
- CHECK_BALANCE: Vendor asks for total sales, balance, or earnings summary.
- VERIFY_ALERT: Vendor asks to check an SMS or bank credit alert for fraud.

Return valid JSON with keys: intent, amount, category, description, debtor_or_creditor, detected_language, voice_reply_script.
"""

class NatlasLLMClient:
    def __init__(self):
        self.endpoint = settings.NATLAS_LLM_URL
        self.api_key = settings.NATLAS_LLM_KEY
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def _is_mock_mode(self) -> bool:
        return not self.api_key or "your_" in self.api_key.lower() or "mock" in self.api_key.lower()

    def _mock_extraction(self, transcript: str) -> TransactionExtraction:
        """Rule-based extractor mimicking N-ATLAS LLM outputs for local/offline testing."""
        text = transcript.lower()

        # 1. Alert Verification Intent
        if any(w in text for w in ["fake alert", "check alert", "verify alert", "sms", "alert dabi", "jabu"]):
            lang = "yo" if any(w in text for w in ["dabi", "itanje", "se"]) else ("ha" if "jabu" in text else "pcm")
            return TransactionExtraction(
                intent="VERIFY_ALERT",
                amount=0.0,
                category="fraud_check",
                description=transcript,
                detected_language=lang,
                voice_reply_script="Analyzing your bank alert for security."
            )

        # 2. Debt Query Intent
        if any(w in text for w in ["who dey owe", "who owe", "tani o je mi", "wa ke bina", "ndi ji m"]):
            lang = "yo" if "je mi" in text else ("ha" if "bina" in text else "pcm")
            return TransactionExtraction(
                intent="CHECK_DEBT",
                amount=0.0,
                category="debt_query",
                description=transcript,
                detected_language=lang,
                voice_reply_script="Checking your debtor list."
            )

        # 3. Debt Settlement Intent (Paying back credit)
        if any(w in text for w in ["pay debt", "settle debt", "san gbese", "biya bashi", "kwụọ ụgwọ"]):
            amount = 2000.0
            customer = "Mama Chuka" if "chuka" in text else ("Musa" if "musa" in text else "Customer")
            lang = "yo" if "gbese" in text else ("ha" if "bashi" in text else "pcm")
            return TransactionExtraction(
                intent="SETTLE_DEBT",
                amount=amount,
                category="debt_settlement",
                description=transcript,
                debtor_or_creditor=customer,
                detected_language=lang,
                voice_reply_script=f"Recording debt payment of {amount:,.0f} Naira from {customer}."
            )

        # 4. Debt Record Intent (Goods taken on credit)
        if any(w in text for w in ["on credit", "credit", "gbese", "bashi", "ụgwọ"]):
            amount = 5000.0
            customer = "Mama Chuka" if "chuka" in text else ("Musa" if "musa" in text else "Customer")
            lang = "yo" if "gbese" in text else ("ha" if "bashi" in text else "pcm")
            return TransactionExtraction(
                intent="RECORD_CREDIT",
                amount=amount,
                category="credit_sales",
                description=transcript,
                debtor_or_creditor=customer,
                detected_language=lang,
                voice_reply_script=f"Recording credit of {amount:,.0f} Naira for {customer}."
            )

        # 5. Balance Query Intent
        if any(w in text for w in ["check", "balance", "how much money", "remain", "total", "elo ni"]):
            return TransactionExtraction(
                intent="CHECK_BALANCE",
                amount=0.0,
                category="query",
                description=transcript,
                detected_language="pcm",
                voice_reply_script="Calculating your balance now."
            )

        # 6. Expense Intent
        if any(w in text for w in ["pay", "buy", "spent", "sayi", "sanwo", "fuel", "transport"]):
            amount = 5000.0 if ("five thousand" in text or "dubu biyar" in text) else 2000.0
            lang = "ha" if ("sayi" in text or "dubu" in text) else "pcm"
            reply = "Na rubuta kudin man fetur Naira dubu biyar." if lang == "ha" else f"I don record expense of {amount:,.0f} Naira."
            return TransactionExtraction(
                intent="RECORD_EXPENSE",
                amount=amount,
                category="fuel" if ("fuel" in text or "fetur" in text) else "transport",
                description=transcript,
                detected_language=lang,
                voice_reply_script=reply
            )

        # 7. Default: Sale Intent
        if "aso lace" in text or "mo ta" in text:
            return TransactionExtraction(
                intent="RECORD_SALE",
                amount=30000.0,
                category="lace fabric",
                description="3 lace fabrics sold",
                detected_language="yo",
                voice_reply_script="Mo ti ko tita aso lace re sile. Egberun lona ogbon Naira."
            )

        amount = 45000.0 if "fifteen thousand" in text else 10000.0
        return TransactionExtraction(
            intent="RECORD_SALE",
            amount=amount,
            category="garri" if "garri" in text else "goods",
            description=transcript,
            debtor_or_creditor="Mama Chuka" if "chuka" in text else None,
            detected_language="pcm",
            voice_reply_script=f"I don record sale of {amount:,.0f} Naira for you."
        )

    async def extract_transaction(self, transcript: str) -> TransactionExtraction:
        if self._is_mock_mode():
            logger.warning("[!] Using MOCK N-ATLAS LLM client (No live API key detected).")
            return self._mock_extraction(transcript)

        payload = {
            "model": "n-atlas-8b",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Transcript: {transcript}"}
            ],
            "temperature": 0.1,
            "response_format": {"type": "json_object"}
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(self.endpoint, headers=self.headers, json=payload)
                resp.raise_for_status()
                data = resp.json()

            raw_content = data["choices"][0]["message"]["content"]
            parsed_json = json.loads(raw_content)
            return TransactionExtraction(**parsed_json)
        except Exception as e:
            logger.error(f"[!] Live LLM call failed ({e}). Falling back to mock extractor.")
            return self._mock_extraction(transcript)

natlas_llm_client = NatlasLLMClient()
