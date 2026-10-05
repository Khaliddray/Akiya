import re
import logging
from typing import Dict, Any

logger = logging.getLogger("monivoice.alert_detector")

KNOWN_BANK_IDENTIFIERS = [
    "gtbank", "zenith", "access", "firstbank", "uba", "opay", "palmpay",
    "kuda", "stanbic", "fcmb", "fidelity", "wema"
]

SUSPICIOUS_PHRASES = [
    "pending credit", "credited shortly", "call this number to claim",
    "delayed payment", "24 hours", "ref id pending"
]

def analyze_sms_alert(text: str, language: str = "pcm") -> Dict[str, Any]:
    """
    Analyzes an incoming SMS alert or spoken message description for fraud indicators.
    Returns risk level, flags found, and oral warning script.
    """
    clean_text = text.lower()
    flags = []
    risk_score = 0  # 0 to 100

    # Check 1: Suspicious payment delay or claim instructions
    for phrase in SUSPICIOUS_PHRASES:
        if phrase in clean_text:
            flags.append(f"Suspicious terminology detected: '{phrase}'")
            risk_score += 40

    # Check 2: Missing standard transaction references (Ref/Session ID)
    has_ref = bool(re.search(r'(ref|ref\s*no|session|trn|txn|stan)\s*[:#]?\s*[a-z0-9]+', clean_text))
    if not has_ref:
        flags.append("Missing official bank transaction or session reference number.")
        risk_score += 30

    # Check 3: Check for bank name mentions
    has_bank = any(bank in clean_text for bank in KNOWN_BANK_IDENTIFIERS)
    if not has_bank:
        flags.append("No recognized Nigerian commercial bank or licensed fintech name found.")
        risk_score += 25

    # Check 4: Check if amount is specified
    amount_match = re.search(r'(ngn|naira|n|\#)\s*([0-9,]+(\.[0-9]{2})?)', clean_text)
    extracted_amount = amount_match.group(2) if amount_match else None

    # Determine risk category
    is_safe = risk_score < 40
    status = "SAFE" if is_safe else ("SUSPICIOUS" if risk_score < 70 else "HIGH_RISK")

    # Generate oral warning script in user's detected language
    if not is_safe:
        if language == "yo":
            oral_script = "Ikilọ o! Ifiranṣẹ yii dabi itanjẹ. Maṣe fun onibara ni ẹru titi owo yoo fi wọ akọọlẹ banki rẹ gangan."
        elif language == "ha":
            oral_script = "Hattara! Wannan sakon alert din yana kama da na jabu. Kada ka saki kaya har sai ka duba asusun bankin ka."
        elif language == "ig":
            oral_script = "Kpachara anya! Ozi a dị ka wayo. Enyela ngwa ahịa gị ma ọ bụrụ na ị hụbeghị ego na akaụntụ gị."
        else:
            oral_script = "Warning o! This alert look like fake alert. No give out your goods until you check your real bank app or press USSD to confirm the money."
    else:
        if language == "yo":
            oral_script = "Ifiranṣẹ banki yii dabi ojulowo, ṣugbọn rii daju pe o ṣayẹwo akọọlẹ rẹ."
        elif language == "ha":
            oral_script = "Sakon bankin nan yana da kyau, amma ka tabbatar ka duba asusunka."
        elif language == "ig":
            oral_script = "Ozi a dị ka nke ezigbo ya, mana buru ụzọ lelee akaụntụ gị."
        else:
            oral_script = "This alert details look okay, but always check your bank balance to confirm before customer commot."

    return {
        "status": status,
        "risk_score": risk_score,
        "extracted_amount": extracted_amount,
        "flags": flags,
        "voice_reply_script": oral_script
    }
