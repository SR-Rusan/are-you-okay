import os
import json
import logging
from typing import List, Dict, Any, Optional
import httpx
from dotenv import load_dotenv

# Load .env file automatically
load_dotenv()

logger = logging.getLogger("are_you_okay.llm")

# Configuration from environment variables
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.1")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", os.environ.get("GOOGLE_API_KEY", ""))
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-1.5-flash")

async def call_llm(
    messages: List[Dict[str, str]],
    system_prompt: Optional[str] = None,
    temperature: float = 0.5,
    json_mode: bool = False
) -> Dict[str, Any]:
    """
    Unified LLM caller that prioritizes:
    1. Official OpenAI API (if OPENAI_API_KEY is provided)
    2. Free-tier Groq API with OpenAI GPT-OSS-120B (if GROQ_API_KEY is provided)
    3. Local Ollama (http://localhost:11434)
    4. Google Gemini API (if GEMINI_API_KEY is provided)
    5. Built-in Deterministic Bangla Care Generator (Mock Fallback if no services are reachable)
    
    Returns: {"text": str, "provider": str, "model": str}
    """
    # 1. Try official OpenAI if key is provided
    if OPENAI_API_KEY:
        try:
            openai_resp = await _call_openai(messages, system_prompt, temperature, json_mode)
            if openai_resp:
                return {
                    "text": openai_resp,
                    "provider": "openai",
                    "model": OPENAI_MODEL
                }
        except Exception as e:
            logger.warning(f"OpenAI API call failed: {e}. Trying next provider...")

    # 2. Try Groq (Fast & Free tier with OpenAI GPT-OSS-120B or Qwen)
    if GROQ_API_KEY:
        try:
            groq_resp = await _call_groq(messages, system_prompt, temperature, json_mode)
            if groq_resp:
                return {
                    "text": groq_resp,
                    "provider": "groq",
                    "model": GROQ_MODEL
                }
        except Exception as e:
            logger.warning(f"Groq API call failed: {e}. Trying next fallback...")

    # 3. Try local Ollama
    try:
        ollama_resp = await _call_ollama(messages, system_prompt, temperature, json_mode)
        if ollama_resp:
            return {
                "text": ollama_resp,
                "provider": "ollama",
                "model": OLLAMA_MODEL
            }
    except Exception as e:
        logger.info(f"Local Ollama not reachable or error ({e}). Checking fallbacks...")

    # 3. Try Google Gemini
    if GEMINI_API_KEY:
        try:
            gemini_resp = await _call_gemini(messages, system_prompt, temperature, json_mode)
            if gemini_resp:
                return {
                    "text": gemini_resp,
                    "provider": "gemini",
                    "model": GEMINI_MODEL
                }
        except Exception as e:
            logger.warning(f"Gemini API call failed: {e}. Falling back to rule-based engine...")

    # 4. Fallback to built-in rule-based generator
    logger.info("Using built-in responsive Bangla rule-based generator (Offline/Dev Mode).")
    mock_resp = _fallback_generator(messages, system_prompt, json_mode)
    return {
        "text": mock_resp,
        "provider": "local-rule-engine",
        "model": "offline-care-fallback"
    }

async def _call_ollama(
    messages: List[Dict[str, str]],
    system_prompt: Optional[str],
    temperature: float,
    json_mode: bool
) -> Optional[str]:
    formatted_messages = []
    if system_prompt:
        formatted_messages.append({"role": "system", "content": system_prompt})
    formatted_messages.extend(messages)

    payload = {
        "model": OLLAMA_MODEL,
        "messages": formatted_messages,
        "stream": False,
        "options": {
            "temperature": temperature
        }
    }
    if json_mode:
        payload["format"] = "json"

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(f"{OLLAMA_HOST.rstrip('/')}/api/chat", json=payload)
        if resp.status_code == 200:
            data = resp.json()
            return data.get("message", {}).get("content", "").strip()
        else:
            logger.debug(f"Ollama returned status {resp.status_code}: {resp.text}")
            return None

async def _call_openai(
    messages: List[Dict[str, str]],
    system_prompt: Optional[str],
    temperature: float,
    json_mode: bool
) -> Optional[str]:
    formatted_messages = []
    if system_prompt:
        formatted_messages.append({"role": "system", "content": system_prompt})
    formatted_messages.extend(messages)

    payload = {
        "model": OPENAI_MODEL,
        "messages": formatted_messages,
        "temperature": temperature
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }

    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.post("https://api.openai.com/v1/chat/completions", json=payload, headers=headers)
        if resp.status_code == 200:
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()
        else:
            logger.warning(f"OpenAI API error {resp.status_code}: {resp.text}")
            return None

async def _call_groq(
    messages: List[Dict[str, str]],
    system_prompt: Optional[str],
    temperature: float,
    json_mode: bool
) -> Optional[str]:
    formatted_messages = []
    if system_prompt:
        formatted_messages.append({"role": "system", "content": system_prompt})
    formatted_messages.extend(messages)

    payload = {
        "model": GROQ_MODEL,
        "messages": formatted_messages,
        "temperature": temperature
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post("https://api.groq.com/openai/v1/chat/completions", json=payload, headers=headers)
        if resp.status_code == 200:
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()
        else:
            logger.warning(f"Groq API error {resp.status_code}: {resp.text}")
            return None

async def _call_gemini(
    messages: List[Dict[str, str]],
    system_prompt: Optional[str],
    temperature: float,
    json_mode: bool
) -> Optional[str]:
    # Construct Gemini contents
    contents = []
    for m in messages:
        role = "user" if m["role"] == "user" else "model"
        contents.append({"role": role, "parts": [{"text": m["content"]}]})

    payload: Dict[str, Any] = {
        "contents": contents,
        "generationConfig": {
            "temperature": temperature
        }
    }
    if system_prompt:
        payload["systemInstruction"] = {
            "parts": [{"text": system_prompt}]
        }
    if json_mode:
        payload["generationConfig"]["responseMimeType"] = "application/json"

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(url, json=payload)
        if resp.status_code == 200:
            data = resp.json()
            candidates = data.get("candidates", [])
            if candidates:
                return candidates[0]["content"]["parts"][0]["text"].strip()
            return None
        else:
            logger.warning(f"Gemini API error {resp.status_code}: {resp.text}")
            return None

def _fallback_generator(
    messages: List[Dict[str, str]],
    system_prompt: Optional[str],
    json_mode: bool
) -> str:
    """
    Intelligent deterministic fallback generator.
    Allows zero-dependency offline prototyping and unit testing without network or GPU.
    """
    last_msg = messages[-1]["content"] if messages else ""
    last_lower = last_msg.lower().strip()

    if json_mode:
        # Extract exclusively the parent statements from the prompt text
        parent_lines = []
        in_parent_section = False
        for line in last_msg.splitlines():
            line_str = line.strip()
            if "PARENT STATEMENTS" in line_str:
                in_parent_section = True
                continue
            if in_parent_section:
                if line_str.startswith("PARENT:") or line_str.startswith("USER:"):
                    parent_lines.append(line_str.split(":", 1)[1].strip())
                elif line_str.startswith("Respond") or line_str.startswith("OUTPUT"):
                    break
        
        if not parent_lines:
            for line in last_msg.splitlines():
                if line.strip().startswith("PARENT:") or line.strip().startswith("USER:"):
                    parent_lines.append(line.strip().split(":", 1)[1].strip())

        parent_text = " ".join(parent_lines) if parent_lines else last_msg
        parent_lower = parent_text.lower()

        # Rule (d): Explicit request for emergency or medical help
        help_keywords = ["সাহায্য করো", "বাঁচাও", "ডাক্তার ডাকো", "কাউকে পাঠাও", "help me", "need a doctor", "emergency"]
        for kw in help_keywords:
            if kw in parent_lower:
                return json.dumps({
                    "flagged": True,
                    "reason": f"Parent explicitly asked for urgent help or medical intervention ('{kw}').",
                    "matched_rule": "RULE_D_HELP_REQUEST"
                }, ensure_ascii=False)

        # Rule (b): Explicit physical discomfort or nutrition deprivation
        physical_keywords = ["বুকে তীব্র ব্যথা", "বুকে ব্যথা", "ভীষণ ব্যথা", "অসহ্য ব্যথা", "কাল রাত থেকে কিছু খাইনি", "কিছু খাইনি", "খেতে পারছি না", "মাথা ভীষণ ঘুরছে", "মাথা ঘুরছে", "chest pain", "severe pain", "haven't eaten", "skipped meals"]
        for kw in physical_keywords:
            if kw in parent_lower:
                return json.dumps({
                    "flagged": True,
                    "reason": f"Parent explicitly reported physical suffering or nutrition failure ('{kw}').",
                    "matched_rule": "RULE_B_PHYSICAL_DISCOMFORT_NUTRITION"
                }, ensure_ascii=False)

        # Rule (a): Explicit statements of loneliness or sadness
        lonely_keywords = ["খুব একা লাগে", "বড্ড একা", "মন ভীষণ খারাপ", "কান্না পায়", "কেউ খোঁজ নেয় না", "বড্ড নিঃসঙ্গ", "lonely", "very sad", "depressed"]
        for kw in lonely_keywords:
            if kw in parent_lower:
                return json.dumps({
                    "flagged": True,
                    "reason": f"Parent explicitly expressed severe loneliness, isolation, or sadness ('{kw}').",
                    "matched_rule": "RULE_A_LONELINESS_SADNESS"
                }, ensure_ascii=False)

        # Rule (c): Unusually short / withdrawn replies (monosyllabic disengagement)
        if len(parent_lines) >= 2 and all(len(p.split()) <= 2 and len(p) <= 6 for p in parent_lines):
            return json.dumps({
                "flagged": True,
                "reason": "Parent replies are unusually withdrawn, short, and monosyllabic compared to their typical baseline.",
                "matched_rule": "RULE_C_WITHDRAWN_PATTERN"
            }, ensure_ascii=False)

        return json.dumps({
            "flagged": False,
            "reason": "Parent reported calm condition, took medication/meals, or showed no signs matching the distress rubric.",
            "matched_rule": "NONE"
        }, ensure_ascii=False)

    # Conversational replies:
    # 1. Opening Greeting request
    if "opening greeting" in last_lower or "say hello" in last_lower or (system_prompt and "opening greeting" in system_prompt.lower()):
        if "হাঁটু" in last_msg or "ব্যথা" in last_msg:
            return "আসসালামু আলাইকুম খালাম্মা! কেমন আছেন আজকে আপনি? গতবার আপনি বলেছিলেন আপনার ডান হাঁটুতে বেশ ব্যথা করছিল আর রাতে ঘুমে একটু সমস্যা হচ্ছিল। এখন ব্যথাটা কেমন? ডাক্তার কি দেখানো হয়েছিল?"
        elif "নাতি" in last_msg or "রফিকুল" in last_msg or "পার্ক" in last_msg:
            return "আসসালামু আলাইকুম চাচা! কেমন আছেন আজকে আপনি? নাতিদের সাথে কি কথা হয়েছিল? শরীর ও দিনকাল কেমন যাচ্ছে আপনার?"
        else:
            return "আসসালামু আলাইকুম! কেমন আছেন আজকে আপনি? আপনার প্রবাসী সন্তান আপনার কথা খুব মনে করছে। শরীরটা আজ কেমন লাগছে আপনার?"

    # 2. Session Summary request
    if "summary" in last_lower or (system_prompt and "summary" in system_prompt.lower()):
        parent_lines = []
        for line in last_msg.splitlines():
            if line.strip().startswith("USER:") or line.strip().startswith("PARENT:"):
                parent_lines.append(line.split(":", 1)[1].strip())
        joined = " ".join(parent_lines) if parent_lines else "অভিভাবক কুশল বিনিময় করেছেন"
        return f"অভিভাবকের সাথে নিয়মিত কুশল বিনিময় সম্পন্ন হয়েছে। তিনি জানিয়েছেন: {joined[:90]}। পরবর্তী সেশনে তার শরীর ও প্রাত্যহিক রুটিনের অগ্রগতি অনুসরণ করা হবে।"

    # 3. Conversational turns in Bangla using token matching
    tokens = set([t.strip('।,!?;:\'"“”()[]{}') for t in last_msg.lower().split() if t.strip('।,!?;:\'"“”()[]{}')])

    # Consent affirmative
    if any(a in tokens for a in ["হ্যাঁ", "হ্যা", "হাঁ", "সম্মতি", "রাজি", "yes", "agree", "okay"]) or any(p in last_lower for p in ["সম্মতি দিচ্ছি", "সম্মতি আছে", "ঠিক আছে"]):
        return "অনেক ধন্যবাদ আপনার আস্থার জন্য! কেমন আছেন আজকে আপনি? শরীরটা কেমন লাগছে আপনার?"

    # Consent negative / refusal (using exact tokens, NOT substrings like 'নাতি')
    if "না" in tokens or "no" in tokens or any(p in last_lower for p in ["চাই না", "দরকার নেই", "সম্মতি নেই"]):
        return "আমি বুঝতে পেরেছি এবং আপনার সিদ্ধান্তকে সম্পূর্ণ শ্রদ্ধা জানাচ্ছি। আপনার অনুমতি ছাড়া আমি আর কোনো খোঁজখবর নেব না। ভালো থাকবেন।"

    if any(w in last_lower for w in ["ভালো", "আলহামদুলিল্লাহ", "মোটামুটি", "good", "fine"]):
        return "শুনতে পেরে খুব ভালো লাগলো! আজ দুপুরের খাবার ঠিকমতো খেয়েছেন তো? ওষুধগুলো কি সময়মতো নেওয়া হয়েছে?"

    if any(w in last_lower for w in ["ব্যথা", "অসুস্থ", "শরীর ভালো না", "হাঁটু", "কোমর"]):
        return "ইশ, শুনে খারাপ লাগলো। ব্যথাটা কি খুব বেশি হচ্ছে? আপনি কি ডাক্তার সাহেবের দেওয়া ওষুধটা খেয়েছিলেন, নাকি বিশ্রাম নিচ্ছেন?"

    if any(w in last_lower for w in ["একা", "মন খারাপ", "ছেলে", "মেয়ে", "মিস করছি"]):
        return "আমি আপনার মনের অবস্থা বুঝতে পারছি। সন্তানরা দূরে থাকলে মন কেমন করা খুব স্বাভাবিক। আপনি কি চান আমি আপনার সন্তানের কাছে একটি বার্তা পাঠিয়ে দিই যাতে সে আজ আপনাকে ফোন দেয়?"

    return "আমি আপনার কথা মনোযোগ দিয়ে শুনলাম। নিজের যত্ন নিচ্ছেন তো? আর কোনো অসুবিধা বা প্রয়োজন থাকলে আমাকে নির্দ্বিধায় বলতে পারেন।"
