import os
import json
import logging
from datetime import datetime
from typing import List, Dict, Any, Tuple
from backend.llm_service import call_llm
from backend.database import record_alert, update_user_summary, finish_session

logger = logging.getLogger("are_you_okay.distress")

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALERTS_FILE_PATH = os.environ.get("ALERTS_FILE", os.path.join(PROJECT_ROOT, "alerts.json"))

RUBRIC_SYSTEM_PROMPT = """You are a specialized clinical safety audit engine for "Are You Okay?", an AI family care companion in Bangladesh.
Your task is to analyze the conversation transcript between an AI companion and an elderly parent.

EVALUATION RUBRIC:
You must evaluate strictly and exclusively against the following 4 rules. You MUST NOT infer or speculate beyond these rules:
Rule (a) [RULE_A_LONELINESS_SADNESS]: Explicit statements of loneliness, persistent sadness, isolation, or crying (e.g. "খুব একা লাগে", "মন ভীষণ খারাপ", "কেউ কথা বলে না", "বড্ড একা হয়ে গেছি").
Rule (b) [RULE_B_PHYSICAL_DISCOMFORT_NUTRITION]: Explicit statements of physical discomfort, severe pain, sickness, falling, or not eating / skipped meals (e.g. "বুকে ব্যথা করছে", "কাল রাত থেকে কিছু খাইনি", "শরীর ভীষণ খারাপ", "মাথা ঘুরছে").
Rule (c) [RULE_C_WITHDRAWN_PATTERN]: Unusually short or withdrawn replies versus normal pattern (e.g. answering only "হুম", "না", "হুঁ", abrupt monosyllables indicating disengagement or distress).
Rule (d) [RULE_D_HELP_REQUEST]: Explicit requests for immediate help, medical attention, or an emergency visit (e.g. "আমাকে সাহায্য করো", "ডাক্তার ডাকো", "কাউকে পাঠাও").

OUTPUT REQUIREMENTS:
Output strictly valid JSON matching this schema:
{
  "flagged": true or false,
  "reason": "Clear explanation of why this was or was not flagged",
  "matched_rule": "RULE_A_LONELINESS_SADNESS" | "RULE_B_PHYSICAL_DISCOMFORT_NUTRITION" | "RULE_C_WITHDRAWN_PATTERN" | "RULE_D_HELP_REQUEST" | "NONE"
}
"""

def _format_sms_alert(user: Dict[str, Any], matched_rule: str, reason: str) -> str:
    """Formats the simulated SMS exactly as it would be sent to the family member abroad."""
    kin_name = user.get("kin_name", "Family Member")
    kin_rel = user.get("kin_relation", "Parent")
    parent_name = user.get("name", "Your parent")

    # Contextual tone
    if "মা" in parent_name or "Mother" in kin_rel or "মা" in kin_rel:
        subject = "Your mother"
        subject_pronoun = "her"
    elif "বাবা" in parent_name or "Father" in kin_rel or "বাবা" in kin_rel:
        subject = "Your father"
        subject_pronoun = "him"
    else:
        subject = f"{parent_name}"
        subject_pronoun = "them"

    rule_descriptions = {
        "RULE_A_LONELINESS_SADNESS": "expressed strong feelings of loneliness or sadness",
        "RULE_B_PHYSICAL_DISCOMFORT_NUTRITION": "reported physical discomfort or skipped meals",
        "RULE_C_WITHDRAWN_PATTERN": "gave unusually short/withdrawn replies today",
        "RULE_D_HELP_REQUEST": "explicitly asked for assistance"
    }

    signal = rule_descriptions.get(matched_rule, "recent pattern has changed noticeably")
    sms_text = f"Care Alert from 'Are You Okay?': {subject}'s recent check-in showed signs that {signal}. Consider calling {subject_pronoun} today."
    return sms_text

async def analyze_session_distress(
    session_id: str,
    user: Dict[str, Any],
    messages: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Runs the transcript through a SEPARATE dedicated LLM call using the fixed rubric.
    If flagged, triggers console alert and writes to alerts.json.
    """
    user_msgs = [m for m in messages if m["sender"] == "user"]
    if not user_msgs:
        return {
            "flagged": False,
            "reason": "No user responses recorded in this session.",
            "matched_rule": "NONE"
        }

    # Format transcript for evaluator
    full_transcript = "\n".join([f"{m['sender'].upper()}: {m['text']}" for m in messages])
    parent_only_text = "\n".join([f"PARENT: {m['text']}" for m in messages if m["sender"] == "user"])

    eval_user_prompt = f"""Evaluate this elderly care session transcript against the 4 fixed rubric rules:

USER BASELINE INFO:
Name: {user.get('name')}
Normal average reply length: {user.get('avg_reply_length', 35)} characters

FULL CONVERSATION CONTEXT:
{full_transcript}

PARENT STATEMENTS (AUDIT THESE SPECIFICALLY FOR DISTRESS):
{parent_only_text}

Respond strictly in valid JSON matching the schema."""

    # Separate LLM call with temperature 0.1 for high consistency
    result = await call_llm(
        messages=[{"role": "user", "content": eval_user_prompt}],
        system_prompt=RUBRIC_SYSTEM_PROMPT,
        temperature=0.1,
        json_mode=True
    )

    raw_text = result["text"]
    try:
        # Strip potential markdown code blocks
        clean_text = raw_text.strip()
        if clean_text.startswith("```json"):
            clean_text = clean_text[7:]
        if clean_text.startswith("```"):
            clean_text = clean_text[3:]
        if clean_text.endswith("```"):
            clean_text = clean_text[:-3]
        eval_data = json.loads(clean_text.strip())
    except Exception as e:
        logger.warning(f"Could not parse LLM JSON: '{raw_text}'. Using rule parser fallback: {e}")
        # Secondary fallback
        eval_data = json.loads(call_llm(messages=[{"role": "user", "content": eval_user_prompt}], system_prompt=RUBRIC_SYSTEM_PROMPT, json_mode=True)["text"])

    flagged = bool(eval_data.get("flagged", False))
    reason = str(eval_data.get("reason", ""))
    matched_rule = str(eval_data.get("matched_rule", "NONE"))

    if flagged:
        alert_id = f"alert_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{user.get('user_id')}"
        sms_text = _format_sms_alert(user, matched_rule, reason)
        
        # 1. Log simulated alert to console
        print("\n" + "=" * 70)
        print("🚨 [ARE YOU OKAY? — DISTRESS ALERT TRIGGERED]")
        print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Target Family Contact: {user.get('kin_name')} ({user.get('kin_relation')}, {user.get('kin_phone')})")
        print(f"Parent: {user.get('name')} (User ID: {user.get('user_id')})")
        print(f"Matched Rule: {matched_rule}")
        print(f"Clinical Reason: {reason}")
        print("-" * 70)
        print(f"📱 SIMULATED SMS DISPATCHED:")
        print(f"\"{sms_text}\"")
        print("=" * 70 + "\n")

        # 2. Append to alerts.json file
        append_to_alerts_file({
            "id": alert_id,
            "timestamp": datetime.now().isoformat(),
            "user_id": user.get("user_id"),
            "user_name": user.get("name"),
            "family_contact": {
                "name": user.get("kin_name"),
                "relation": user.get("kin_relation"),
                "phone": user.get("kin_phone")
            },
            "matched_rule": matched_rule,
            "reason": reason,
            "sms_text": sms_text,
            "status": "simulated_sent"
        })

        # 3. Record in SQLite
        record_alert(
            alert_id=alert_id,
            user_id=user["user_id"],
            session_id=session_id,
            matched_rule=matched_rule,
            reason=reason,
            sms_text=sms_text
        )

    return {
        "flagged": flagged,
        "reason": reason,
        "matched_rule": matched_rule
    }

def append_to_alerts_file(alert_dict: Dict[str, Any]) -> None:
    """Reads existing alerts from alerts.json, appends the new one, and saves."""
    alerts = []
    if os.path.exists(ALERTS_FILE_PATH):
        try:
            with open(ALERTS_FILE_PATH, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    alerts = json.loads(content)
        except Exception as e:
            logger.error(f"Error reading {ALERTS_FILE_PATH}: {e}")
            alerts = []

    alerts.insert(0, alert_dict) # Newest first

    try:
        with open(ALERTS_FILE_PATH, "w", encoding="utf-8") as f:
            json.dump(alerts, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved alert to {ALERTS_FILE_PATH}")
    except Exception as e:
        logger.error(f"Error writing to {ALERTS_FILE_PATH}: {e}")

async def generate_and_save_session_summary(
    session_id: str,
    user: Dict[str, Any],
    messages: List[Dict[str, Any]]
) -> str:
    """
    Generates a concise 2-3 sentence Bangla summary of the session
    and stores it in the user's running memory in SQLite.
    """
    user_msgs = [m for m in messages if m["sender"] == "user"]
    if not user_msgs:
        return "কোনো নতুন তথ্য রেকর্ড করা হয়নি।"

    transcript_text = "\n".join([f"{m['sender'].upper()}: {m['text']}" for m in messages])
    
    summary_prompt = f"""Write a short (2-3 sentences), warm, and factually accurate summary in Bengali (Bangla) of this check-in session with elderly parent {user.get('name')}.
Highlight their health condition, what they ate or did, and any specific topic that should be followed up on in the next conversation.
Do not use introductory phrases like "এখানে সারসংক্ষেপ দেওয়া হলো" or markdown headers. Output only the 2-3 sentences in natural Bangla.

TRANSCRIPT:
{transcript_text}"""

    resp = await call_llm(
        messages=[{"role": "user", "content": summary_prompt}],
        temperature=0.3
    )

    summary_text = resp["text"].strip()
    # Calculate average reply length for this session to update baseline
    lengths = [len(m["text"]) for m in user_msgs]
    session_avg_len = sum(lengths) / len(lengths) if lengths else None

    # Update user's memory in SQLite
    update_user_summary(user["user_id"], summary_text, session_avg_len)
    return summary_text
