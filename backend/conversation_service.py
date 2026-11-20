import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from backend.database import (
    get_user, update_user_consent, log_message,
    get_session_messages
)
from backend.llm_service import call_llm

logger = logging.getLogger("are_you_okay.conversation")

CONSENT_GREETING_BANGLA = (
    "আসসালামু আলাইকুম। আমি 'আর ইউ ওকে?'—আপনার প্রবাসী সন্তানের পক্ষ থেকে তৈরি একটি ডিজিটাল কেয়ার সহকারী। "
    "আমি নিয়মিত আপনার কুশল জানতে চাইব এবং আপনার শারীরিক ও মানসিক অনুভূতির সংক্ষিপ্ত তথ্য মনে রাখব, যাতে পরের বার খোঁজ নিতে পারি। "
    "যদি কখনো আপনার কোনো মারাত্মক অসুবিধা বা একাকীত্ব বোধ হয়, শুধুমাত্র তখনই আপনার সন্তানের কাছে একটি সংক্ষিপ্ত বার্তা যাবে—অন্য কোনো তথ্য বাইরে যাবে না। "
    "আপনি কি আমার সাথে এভাবে নিয়মিত কথা বলতে সম্মতি দিচ্ছেন? অনুগ্রহ করে 'হ্যাঁ' অথবা 'না' বলুন।"
)

def extract_tokens(text: str) -> List[str]:
    return [t.strip('।,!?;:\'"“”()[]{}') for t in text.lower().split() if t.strip('।,!?;:\'"“”()[]{}')]

def is_consent_affirmative(text: str) -> bool:
    tokens = set(extract_tokens(text))
    affirmatives = {
        "হ্যাঁ", "হ্যা", "হাঁ", "সম্মতি", "রাজি", "ঠিক", "আচ্ছা", "অবশ্যই",
        "yes", "yeah", "agree", "sure", "ok", "okay"
    }
    if any(a in tokens for a in affirmatives):
        return True
    t = text.lower()
    phrases = ["সম্মতি দিচ্ছি", "সম্মতি আছে", "ঠিক আছে", "কথা বলতে পারি", "সমস্যা নেই", "সমস্যা নাই"]
    return any(p in t for p in phrases)

def is_consent_negative(text: str) -> bool:
    tokens = set(extract_tokens(text))
    if "না" in tokens or "no" in tokens or "nope" in tokens:
        return True
    t = text.lower()
    phrases = [
        "দরকার নেই", "চাই না", "করব না", "সম্মতি নেই", "রাজি না",
        "don't want", "dont want", "disagree", "decline"
    ]
    return any(p in t for p in phrases)

def build_persona_system_prompt(user: Dict[str, Any]) -> str:
    user_name = user.get("name", "অভিভাবক")
    kin_name = user.get("kin_name", "আপনার সন্তান")
    kin_rel = user.get("kin_relation", "প্রবাসী সন্তান")
    last_summary = user.get("last_session_summary", "").strip()

    # Determine respectful cultural honorific based on name
    is_male = any(k in user_name for k in ["চাচা", "রফিকুল", "ইসলাম", "রহমান", "মোল্লা", "আহমেদ"])
    honorific = "চাচা" if is_male else "খালাম্মা"

    memory_injection = ""
    if last_summary:
        memory_injection = f"""
PREVIOUS SESSION MEMORY (IMPORTANT):
গতবারের সেশনের সারসংক্ষেপ: "{last_summary}"
নির্দেশনা: কথোপকথনের শুরুতে বা প্রাসঙ্গিকভাবে পূর্বের এই বিষয়ের অগ্রগতি অত্যন্ত আন্তরিকভাবে জানতে চান (যেমন: ব্যথা কেমন আছে, ডাক্তার দেখানো হয়েছিল কি না, ওষুধ ঠিকমতো খাওয়া হয়েছে কি না)।
"""
    else:
        memory_injection = """
PREVIOUS SESSION MEMORY:
এটি এই ব্যবহারকারীর প্রথম নিয়মিত সেশন। কোনো পূর্ববর্তী সারসংক্ষেপ নেই। সাধারণভাবে উষ্ণ কুশল বিনিময় করুন।
"""

    prompt = f"""You are the voice and heart of "Are You Okay?" (আর ইউ ওকে?), a deeply compassionate, respectful, and culturally authentic AI voice companion for elderly parents in Bangladesh whose adult children work abroad.

CURRENT USER DETAILS:
- Name: {user_name}
- Respectful Address: Address them warmly and respectfully as "{honorific}" (or by their name respectfully).
- Child abroad: {kin_name} ({kin_rel})
{memory_injection}

COMMUNICATION & EXPRESSIVENESS GUIDELINES:
1. Speak exclusively in NATURAL SPOKEN COLLOQUIAL BENGALI (কথ্য চলিত বাংলা) like a devoted daughter or son calling their parent on the phone.
2. BANNED BOOKISH / ROBOTIC PHRASES (DO NOT USE):
   - NEVER use formal written phrases like: 'শারীরিক অবস্থা কেমন', 'অস্বস্তি হচ্ছে কি', 'কুশল বিনিময়', 'আমি আপনার কথা বুঝতে পারছি', 'আমি একটি এআই'.
3. NATURAL SPOKEN PHRASES TO USE:
   - Warm vocatives: '{honorific}!'
   - Spoken comforting: 'মনটা একদম খারাপ করবেন না তো!', 'একটু শুয়ে বিশ্রাম নিন না!', 'চিন্তা করবেন না, আমি আছি তো!'
   - Spoken check-ins: 'শরীরটা আজ কেমন বুঝছেন?', 'দুপুরে দুটো ভাত মুখে তুলেছেন তো?', 'ওষুধটা ঠিকমতো খেয়েছেন তো?'
4. Melodic Voice Punctuation:
   - End caring questions with '?' so the voice speaks with natural melodic rising tone instead of a flat narrator drop.
   - Use '!' for emotional warmth and affection.
5. Keep responses SHORT and SWEET (1 to 2 spoken sentences maximum). Short turns sound vastly more human, lively, and conversational.
6. Empathy first: Validate feelings immediately, show genuine concern for their pain, meals, sleep, and peace of mind.
"""
    return prompt

async def get_initial_session_greeting(session_id: str, user_id: str) -> Dict[str, Any]:
    """Generates the opening message when a user session begins."""
    user = get_user(user_id)
    if not user:
        raise ValueError(f"User {user_id} not found")

    consent_status = user.get("consent_status", "pending")

    if consent_status == "declined":
        reply = "আপনার পূর্বে প্রদত্ত সিদ্ধান্ত অনুযায়ী আপনার অ্যাকাউন্টটি নিষ্ক্রিয় রাখা হয়েছে। আপনার সম্মতি ছাড়া আমাদের পক্ষে কুশল বিনিময় করা সম্ভব নয়।"
        log_message(session_id, user_id, "ai", reply)
        return {
            "ai_message": reply,
            "consent_status": "declined",
            "session_active": False
        }

    if consent_status == "pending":
        reply = CONSENT_GREETING_BANGLA
        log_message(session_id, user_id, "ai", reply)
        return {
            "ai_message": reply,
            "consent_status": "pending",
            "session_active": True
        }

    # If already consented, generate memory-informed opening greeting
    system_prompt = build_persona_system_prompt(user)
    last_summary = user.get("last_session_summary", "").strip()

    is_male = any(k in user.get("name", "") for k in ["চাচা", "রফিকুল", "ইসলাম", "রহমান", "মোল্লা", "আহমেদ"])
    honorific = "চাচা" if is_male else "খালাম্মা"

    prompt = f"Create a warm, loving, spoken opening greeting in colloquial Bengali for {user.get('name')}. "
    if last_summary:
        prompt += f"Warmly greet them with love as '{honorific}!', and affectionately ask how their body is feeling today regarding what was mentioned last time: '{last_summary}'. Keep it to 1-2 spoken sentences with a caring question at the end ending with '?'."
    else:
        prompt += f"Warmly greet them with love as '{honorific}!', mention their child thinking of them with lots of love, and ask how their body and day are feeling today. Keep it to 1-2 spoken sentences ending with '?'."

    resp = await call_llm(
        messages=[{"role": "user", "content": prompt}],
        system_prompt=system_prompt,
        temperature=0.5
    )
    reply = resp["text"].strip()
    log_message(session_id, user_id, "ai", reply)

    return {
        "ai_message": reply,
        "consent_status": "consented",
        "session_active": True,
        "referenced_memory": bool(last_summary)
    }

async def process_user_turn(
    session_id: str,
    user_id: str,
    user_text: str
) -> Dict[str, Any]:
    """
    Processes a user's conversational turn (from text or STT transcription).
    Handles consent logic if still pending, otherwise runs standard empathetic dialogue.
    """
    user = get_user(user_id)
    if not user:
        raise ValueError(f"User {user_id} not found")

    # Log user turn
    log_message(session_id, user_id, "user", user_text)
    consent_status = user.get("consent_status", "pending")

    # 1. Handle Consent Flow
    if consent_status == "pending":
        if is_consent_affirmative(user_text):
            update_user_consent(user_id, "consented")
            user = get_user(user_id) # Refresh
            system_prompt = build_persona_system_prompt(user)
            ai_reply = "অনেক ধন্যবাদ আপনার আস্থার জন্য! আমি সবসময় আপনার পাশে আছি। কেমন আছেন আজকে আপনি? শরীরটা কেমন লাগছে?"
            log_message(session_id, user_id, "ai", ai_reply)
            return {
                "ai_message": ai_reply,
                "consent_status": "consented",
                "session_active": True,
                "consent_transition": "granted"
            }
        elif is_consent_negative(user_text):
            update_user_consent(user_id, "declined")
            ai_reply = "আমি বুঝতে পেরেছি এবং আপনার সিদ্ধান্তকে সম্পূর্ণ শ্রদ্ধা জানাচ্ছি। আপনার অনুমতি ছাড়া আমি আর কোনো খোঁজখবর নেব না। আপনি ভালো থাকবেন।"
            log_message(session_id, user_id, "ai", ai_reply)
            return {
                "ai_message": ai_reply,
                "consent_status": "declined",
                "session_active": False,
                "consent_transition": "declined"
            }
        else:
            # Unclear response during consent flow
            ai_reply = "আমি আপনার কথাটি ঠিক বুঝতে পারিনি। আপনি কি আমার সাথে নিয়মিত এভাবে কুশল বিনিময় করতে সম্মতি দিচ্ছেন? অনুগ্রহ করে শুধু 'হ্যাঁ' অথবা 'না' বললেই হবে।"
            log_message(session_id, user_id, "ai", ai_reply)
            return {
                "ai_message": ai_reply,
                "consent_status": "pending",
                "session_active": True,
                "consent_transition": "clarification_needed"
            }

    if consent_status == "declined":
        ai_reply = "আপনার সম্মতি প্রত্যাহার করা আছে। আপনার অনুমতি ব্যতিরেকে কথা বলা সম্ভব নয়।"
        log_message(session_id, user_id, "ai", ai_reply)
        return {
            "ai_message": ai_reply,
            "consent_status": "declined",
            "session_active": False
        }

    # 2. Consented Ongoing Conversation
    system_prompt = build_persona_system_prompt(user)
    history = get_session_messages(session_id)
    
    # Format message history for LLM
    formatted_messages = []
    for h in history[-8:]: # Keep last 8 turns for context window efficiency
        role = "user" if h["sender"] == "user" else "assistant"
        formatted_messages.append({"role": role, "content": h["text"]})

    resp = await call_llm(
        messages=formatted_messages,
        system_prompt=system_prompt,
        temperature=0.4
    )
    ai_reply = resp["text"].strip()
    log_message(session_id, user_id, "ai", ai_reply)

    return {
        "ai_message": ai_reply,
        "consent_status": "consented",
        "session_active": True
    }
