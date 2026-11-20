import os
import uuid
import logging
import urllib.parse
from typing import Optional, Dict, Any, List
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.database import (
    init_db, get_user, list_users, reset_user,
    create_session, get_session_messages, finish_session,
    get_recent_alerts
)
from backend.conversation_service import (
    get_initial_session_greeting, process_user_turn
)
from backend.distress_service import (
    analyze_session_distress, generate_and_save_session_summary,
    ALERTS_FILE_PATH
)
from backend.tts_service import (
    synthesize_speech, stream_speech_generator, DEFAULT_VOICE, DEFAULT_RATE, DEFAULT_PITCH
)
from backend.stt_service import transcribe_audio_bytes, get_stt_backend_name
from backend.llm_service import OLLAMA_HOST, OLLAMA_MODEL, GROQ_API_KEY, GEMINI_API_KEY

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("are_you_okay.api")

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUDIO_CACHE_DIR = os.path.join(PROJECT_ROOT, "data", "audio_cache")
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend")

os.makedirs(AUDIO_CACHE_DIR, exist_ok=True)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DB on startup
    init_db()
    logger.info("Are You Okay? backend initialized successfully.")
    yield

app = FastAPI(
    title="Are You Okay? — AI Family Care Layer",
    description="Bangla AI Voice Companion for Elderly Parents with Rubric-based Distress Detection",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic Schemas
class StartSessionRequest(BaseModel):
    user_id: str
    synthesize_audio: bool = True
    voice: Optional[str] = None
    style: Optional[str] = "expressive"

class TextChatRequest(BaseModel):
    session_id: str
    user_id: str
    text: str
    synthesize_audio: bool = True
    voice: Optional[str] = None
    style: Optional[str] = "expressive"

class EndSessionRequest(BaseModel):
    session_id: str
    user_id: str

@app.get("/api/health")
async def health_check():
    provider = "ollama"
    if not os.path.exists(OLLAMA_HOST):
        if GROQ_API_KEY:
            provider = "groq"
        elif GEMINI_API_KEY:
            provider = "gemini"
        else:
            provider = "offline-rule-engine"
    return {
        "status": "healthy",
        "project": "Are You Okay? — AI Family Care Layer",
        "llm_config": {
            "ollama_host": OLLAMA_HOST,
            "ollama_model": OLLAMA_MODEL,
            "groq_configured": bool(GROQ_API_KEY),
            "gemini_configured": bool(GEMINI_API_KEY),
            "current_provider": provider
        },
        "tts_voice": DEFAULT_VOICE,
        "stt": get_stt_backend_name()
    }

@app.get("/api/users")
async def get_all_users():
    return list_users()

@app.get("/api/users/{user_id}")
async def get_single_user(user_id: str):
    u = get_user(user_id)
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    return u

@app.post("/api/users/{user_id}/reset")
async def reset_user_data(user_id: str):
    success = reset_user(user_id)
    if not success:
        raise HTTPException(status_code=404, detail="User not found")
    return {"status": "success", "message": f"User {user_id} memory and consent reset.", "user": get_user(user_id)}

@app.get("/api/tts/stream")
async def stream_tts(
    text: str,
    voice: Optional[str] = None,
    rate: Optional[str] = None,
    pitch: Optional[str] = None,
    style: Optional[str] = "expressive"
):
    if not text.strip():
        raise HTTPException(status_code=400, detail="Empty text provided")
    
    return StreamingResponse(
        stream_speech_generator(text, voice=voice, rate=rate, pitch=pitch, style=style),
        media_type="audio/mpeg",
        headers={
            "Cache-Control": "no-cache",
            "Accept-Ranges": "bytes"
        }
    )

@app.get("/api/tts/preview")
async def preview_tts(
    voice: Optional[str] = None,
    style: Optional[str] = "expressive"
):
    samples = {
        "bn-BD-NabanitaNeural": "আসসালামু আলাইকুম খালাম্মা! আমি আপনার পাশে আছি, মনটা একদম ভালো রাখুন!",
        "bn-BD-PradeepNeural": "আসসালামু আলাইকুম খালাম্মা! কোনো চিন্তা করবেন না, শরীর কেমন লাগছে আপনার?",
        "bn-IN-TanishaaNeural": "আসসালামু আলাইকুম! দিনটা কেমন কাটছে আপনার? আজ কি শরীরে একটু আরাম পাচ্ছেন?",
        "bn-IN-BashkarNeural": "আসসালামু আলাইকুম। শান্তিতে বিশ্রাম নিন, আপনার পরিবারের সবাই আপনার কথা ভাবছে।",
        "nova": "Hello! I am your caring companion, speaking with natural warmth.",
        "alloy": "Hello! I am here whenever you need someone to talk to."
    }
    selected_voice = voice or DEFAULT_VOICE
    text = samples.get(selected_voice, "আসসালামু আলাইকুম খালাম্মা! কেমন আছেন আজকে আপনি?")
    return StreamingResponse(
        stream_speech_generator(text, voice=selected_voice, style=style),
        media_type="audio/mpeg",
        headers={"Cache-Control": "no-cache", "Accept-Ranges": "bytes"}
    )

@app.post("/api/session/start")
async def start_session(req: StartSessionRequest):
    user = get_user(req.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    session_id = f"sess_{uuid.uuid4().hex[:12]}"
    create_session(session_id, req.user_id)

    greeting_res = await get_initial_session_greeting(session_id, req.user_id)
    ai_text = greeting_res["ai_message"]

    audio_url = None
    if req.synthesize_audio and ai_text:
        selected_voice = req.voice or DEFAULT_VOICE
        encoded_text = urllib.parse.quote(ai_text)
        encoded_voice = urllib.parse.quote(selected_voice)
        encoded_style = urllib.parse.quote(req.style or "expressive")
        audio_url = f"/api/tts/stream?text={encoded_text}&voice={encoded_voice}&style={encoded_style}"

    return {
        "session_id": session_id,
        "user": user,
        "ai_message": ai_text,
        "consent_status": greeting_res["consent_status"],
        "session_active": greeting_res["session_active"],
        "audio_url": audio_url
    }

@app.post("/api/session/text-chat")
async def handle_text_chat(req: TextChatRequest):
    user = get_user(req.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    turn_res = await process_user_turn(
        session_id=req.session_id,
        user_id=req.user_id,
        user_text=req.text
    )
    ai_text = turn_res["ai_message"]

    audio_url = None
    if req.synthesize_audio and ai_text:
        selected_voice = req.voice or DEFAULT_VOICE
        encoded_text = urllib.parse.quote(ai_text)
        encoded_voice = urllib.parse.quote(selected_voice)
        encoded_style = urllib.parse.quote(req.style or "expressive")
        audio_url = f"/api/tts/stream?text={encoded_text}&voice={encoded_voice}&style={encoded_style}"

    return {
        "session_id": req.session_id,
        "user_id": req.user_id,
        "user_text": req.text,
        "ai_message": ai_text,
        "consent_status": turn_res["consent_status"],
        "session_active": turn_res["session_active"],
        "consent_transition": turn_res.get("consent_transition"),
        "audio_url": audio_url
    }

@app.post("/api/session/voice-chat")
async def handle_voice_chat(
    session_id: str = Form(...),
    user_id: str = Form(...),
    voice: Optional[str] = Form(None),
    style: Optional[str] = Form("expressive"),
    native_transcript: Optional[str] = Form(None),
    audio_file: UploadFile = File(...)
):
    user = get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    audio_bytes = await audio_file.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio recording received")

    # Transcribe Bengali speech
    user_transcript = ""
    try:
        user_transcript = transcribe_audio_bytes(audio_bytes, file_ext="webm", language="bn")
    except Exception as e:
        logger.error(f"STT transcription failed: {e}")
        if not native_transcript:
            raise HTTPException(status_code=500, detail=f"Voice transcription error: {str(e)}")

    if (not user_transcript or user_transcript.strip() in ["...", ""]) and native_transcript:
        user_transcript = native_transcript.strip()

    if not user_transcript:
        user_transcript = "..."

    # Process conversational turn
    turn_res = await process_user_turn(
        session_id=session_id,
        user_id=user_id,
        user_text=user_transcript
    )
    ai_text = turn_res["ai_message"]

    # Generate immediate streaming audio URL for zero-latency audio playback
    audio_url = None
    if ai_text:
        selected_voice = voice or DEFAULT_VOICE
        encoded_text = urllib.parse.quote(ai_text)
        encoded_voice = urllib.parse.quote(selected_voice)
        encoded_style = urllib.parse.quote(style or "expressive")
        audio_url = f"/api/tts/stream?text={encoded_text}&voice={encoded_voice}&style={encoded_style}"

    return {
        "session_id": session_id,
        "user_id": user_id,
        "user_transcript": user_transcript,
        "ai_message": ai_text,
        "consent_status": turn_res["consent_status"],
        "session_active": turn_res["session_active"],
        "consent_transition": turn_res.get("consent_transition"),
        "audio_url": audio_url
    }

@app.post("/api/session/end")
async def handle_end_session(req: EndSessionRequest):
    user = get_user(req.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    messages = get_session_messages(req.session_id)
    
    # 1. Distress detection rubric evaluation (dedicated LLM call)
    distress_eval = await analyze_session_distress(
        session_id=req.session_id,
        user=user,
        messages=messages
    )

    # 2. Session summary generation (2-3 sentences for memory)
    summary = await generate_and_save_session_summary(
        session_id=req.session_id,
        user=user,
        messages=messages
    )

    # 3. Update session record in SQLite
    finish_session(
        session_id=req.session_id,
        status="completed",
        summary=summary,
        distress_flagged=distress_eval["flagged"],
        distress_reason=distress_eval["reason"],
        matched_rule=distress_eval["matched_rule"]
    )

    # Refresh updated user record
    updated_user = get_user(req.user_id)

    return {
        "session_id": req.session_id,
        "status": "completed",
        "distress_eval": distress_eval,
        "summary": summary,
        "updated_memory": updated_user.get("last_session_summary")
    }

@app.get("/api/alerts")
async def get_alerts():
    db_alerts = get_recent_alerts(30)
    return {
        "alerts_file": ALERTS_FILE_PATH,
        "alerts": db_alerts
    }

@app.get("/api/audio/{filename}")
async def get_audio_file(filename: str):
    file_path = os.path.join(AUDIO_CACHE_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Audio file not found")
    return FileResponse(file_path, media_type="audio/mpeg")

# Serve frontend single page app
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

@app.get("/")
async def serve_index():
    index_file = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return JSONResponse({"message": "Frontend not found. Please create index.html in frontend/"})
