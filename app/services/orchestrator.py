import logging
from pathlib import Path
from app.core.whatsapp import whatsapp_client
from app.core.audio import convert_to_wav, cleanup_audio_files
from app.core.natlas_asr import natlas_asr_client
from app.core.natlas_llm import natlas_llm_client
from app.core.tts import synthesize_speech
from app.services.alert_detector import analyze_sms_alert
from app.db.database import (
    save_transaction,
    get_user_summary,
    record_customer_credit,
    settle_customer_debt,
    get_active_debtors
)

logger = logging.getLogger("monivoice.orchestrator")


async def orchestrate_voice_transaction(user_phone: str, raw_audio_path: str | Path) -> None:
    """
    Executes the multimodal oral pipeline:
    Audio -> ASR -> LLM Intent -> Route (Sales / Debts / Fraud Check / Balance) -> TTS -> WhatsApp
    """
    raw_path = Path(raw_audio_path).resolve()
    wav_path: Path | None = None
    reply_audio_path: Path | None = None

    try:
        logger.info(f"[*] Processing audio transaction for {user_phone}...")

        # 1. Transcode input to 16kHz mono WAV
        wav_path = await convert_to_wav(raw_path)

        # 2. Transcribe audio with dialect identification
        asr_result = await natlas_asr_client.transcribe(wav_path)
        transcript = asr_result.text.strip()
        lang = asr_result.detected_language
        logger.info(f"[+] Transcript ({lang}): '{transcript}'")

        if not transcript:
            fallback_text = "I no hear wetin you talk clearly. Abeg record am again."
            reply_audio_path = await synthesize_speech(fallback_text, language="pcm")
            media_id = await whatsapp_client.upload_audio_file(str(reply_audio_path))
            await whatsapp_client.send_audio_message(user_phone, media_id)
            return

        # 3. Extract intent and entities
        extraction = await natlas_llm_client.extract_transaction(transcript)
        intent = extraction.intent
        lang = extraction.detected_language
        reply_script = extraction.voice_reply_script

        logger.info(f"[+] Routing Intent: {intent} (Dialect: {lang})")

        # 4. Route based on extracted intent
        if intent in ["RECORD_SALE", "RECORD_EXPENSE"]:
            await save_transaction(
                user_phone=user_phone,
                intent=intent,
                amount=extraction.amount,
                category=extraction.category,
                description=extraction.description,
                debtor_or_creditor=extraction.debtor_or_creditor,
                detected_language=lang
            )

        elif intent == "RECORD_CREDIT":
            # Customer took goods on credit ("Mama Chuka collect 5k credit")
            customer = extraction.debtor_or_creditor or "Customer"
            debt = await record_customer_credit(user_phone, customer, extraction.amount)
            if lang == "yo":
                reply_script = f"Mo ti kọ gbese {customer} sile. Owo to ku ti o gbọdọ san jẹ {debt.remaining_balance:,.0f} Naira."
            elif lang == "ha":
                reply_script = f"Na rubuta bashin {customer}. Ragowar kudin da zai biya Naira {debt.remaining_balance:,.0f}."
            else:
                reply_script = f"I don record credit for {customer}. Him balance wey remain na {debt.remaining_balance:,.0f} Naira."

        elif intent == "SETTLE_DEBT":
            # Customer paid back their debt
            customer = extraction.debtor_or_creditor or "Customer"
            debt = await settle_customer_debt(user_phone, customer, extraction.amount)
            if debt:
                status_msg = "Debt don clear complete!" if debt.is_settled else f"Him balance remain {debt.remaining_balance:,.0f} Naira."
                reply_script = f"Payment of {extraction.amount:,.0f} Naira from {customer} recorded. {status_msg}"
            else:
                reply_script = f"I record payment for {customer}, but no previous credit record dey for this name."

        elif intent == "CHECK_DEBT":
            # Query who owes money
            debtors = await get_active_debtors(user_phone)
            if not debtors:
                reply_script = "Nobody dey owe you money right now. Clean record!"
            else:
                top_debtors = ", ".join([f"{d['customer_name']} ({d['remaining_balance']:,.0f} Naira)" for d in debtors[:3]])
                reply_script = f"You get {len(debtors)} people wey owe you: {top_debtors}."

        elif intent == "VERIFY_ALERT":
            # Bank alert verification check
            analysis = analyze_sms_alert(transcript, language=lang)
            reply_script = analysis["voice_reply_script"]

        elif intent == "CHECK_BALANCE":
            summary = await get_user_summary(user_phone)
            if lang == "yo":
                reply_script = f"Gbogbo tita rẹ jẹ {summary['total_sales']:,.0f} Naira. Owo to ku jẹ {summary['net_balance']:,.0f} Naira."
            elif lang == "ha":
                reply_script = f"Jimillar cinikin ka Naira {summary['total_sales']:,.0f}. Ragowar kuɗin ka Naira {summary['net_balance']:,.0f}."
            elif lang == "ig":
                reply_script = f"Ngụkọta ahịa gị bụ Naira {summary['total_sales']:,.0f}. Ego fọdụrụ bụ Naira {summary['net_balance']:,.0f}."
            else:
                reply_script = f"Total sales na {summary['total_sales']:,.0f} Naira. Your balance wey remain na {summary['net_balance']:,.0f} Naira."

        # 5. Synthesize spoken response in user's detected dialect
        reply_audio_path = await synthesize_speech(text=reply_script, language=lang)

        # 6. Dispatch voice note back to WhatsApp
        media_id = await whatsapp_client.upload_audio_file(str(reply_audio_path))
        await whatsapp_client.send_audio_message(user_phone, media_id)
        logger.info(f"[+] Outbound response delivered to {user_phone}")

    except Exception as e:
        logger.error(f"[!] Orchestrator failure for {user_phone}: {e}", exc_info=True)
        try:
            await whatsapp_client.send_text_message(
                recipient_phone=user_phone,
                text="Small network issue dey delay processing your voice note. Abeg try again in 1 minute."
            )
        except Exception as send_err:
            logger.error(f"[!] Error message dispatch failed: {send_err}")

    finally:
        to_clean = [p for p in (raw_path, wav_path, reply_audio_path) if p is not None]
        await cleanup_audio_files(*to_clean)
