"""
Text-to-Speech (TTS) Service using Edge-TTS (Free) and OpenAI TTS-1 (Premium).

Features:
- Restored to original normal conversational speed (+0% rate)
- Dual-engine: Free Microsoft Neural Edge-TTS + Optional OpenAI TTS-1
- Real-time chunked streaming for ultra-fast playback
"""

import os
import re
import logging
from typing import Optional, AsyncGenerator
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("are_you_okay.tts")

# Primary voice: bn-BD-NabanitaNeural (female)
# Alternative voice: bn-BD-PradeepNeural (male)
DEFAULT_VOICE = os.environ.get("TTS_VOICE", "bn-BD-NabanitaNeural")
DEFAULT_RATE = os.environ.get("TTS_RATE", "+0%")
DEFAULT_PITCH = os.environ.get("TTS_PITCH", "+0Hz")

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_TTS_VOICE = os.environ.get("OPENAI_TTS_VOICE", "nova")

def format_expressive_bengali_text(text: str) -> str:
    """
    Polishes Bengali text for clean, natural, expressive speech delivery.
    Converts flat declarative question sentences into authentic '?' so neural voices
    apply melodic rising inflection instead of dead monotone drop.
    """
    t = text.strip()
    if not t:
        return t
    # Replace multiple dots or ellipses with single comma for smooth vocal pause
    t = re.sub(r'\.{2,}', ', ', t)
    
    # Ensure question sentences end with '?' instead of '।'
    question_clues = ["কেমন", "কি", "কী", "কবে", "কোথায়", "কেন", "কার", "হয়েছে তো", "খাওয়া হয়েছে", "আছেন তো", "খাবেন কি"]
    for q in question_clues:
        if q in t and t.endswith("।"):
            t = t[:-1] + "?"
            break

    # Add gentle pause after respectful honorifics if followed immediately by text
    t = re.sub(r'\b(খালাম্মা|চাচা|মা|বাবা)\s*([A-Za-z\u0980-\u09FF])', r'\1, \2', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t

async def stream_openai_speech(text: str, voice: Optional[str] = None) -> AsyncGenerator[bytes, None]:
    """Streams audio chunks using OpenAI's high-fidelity tts-1 model."""
    import httpx
    selected_voice = voice if voice in ["alloy", "echo", "fable", "onyx", "nova", "shimmer"] else OPENAI_TTS_VOICE
    url = "https://api.openai.com/v1/audio/speech"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "tts-1",
        "voice": selected_voice,
        "input": text,
        "response_format": "mp3"
    }
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            async with client.stream("POST", url, headers=headers, json=payload) as resp:
                if resp.status_code == 200:
                    async for chunk in resp.aiter_bytes():
                        yield chunk
                else:
                    error_text = await resp.aread()
                    logger.warning(f"OpenAI TTS error {resp.status_code}: {error_text.decode('utf-8', errors='ignore')}")
    except Exception as e:
        logger.error(f"OpenAI TTS stream exception: {e}")

async def stream_speech_generator(
    text: str,
    voice: Optional[str] = None,
    rate: Optional[str] = None,
    pitch: Optional[str] = None,
    style: Optional[str] = "expressive"
) -> AsyncGenerator[bytes, None]:
    """
    Streams MP3 audio chunks on-the-fly for real-time browser playback.
    Uses OpenAI TTS-1 if OPENAI_API_KEY is configured, otherwise uses Edge-TTS
    with calibrated prosody to sound warm, human, and conversational.
    """
    expressive_text = format_expressive_bengali_text(text)
    if not expressive_text:
        return

    # 1. Use OpenAI TTS if key is provided and requested
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if api_key and (voice in ["alloy", "echo", "fable", "onyx", "nova", "shimmer"] or voice == "openai"):
        async for chunk in stream_openai_speech(expressive_text, voice):
            yield chunk
        return

    # 2. Free Microsoft Neural Edge-TTS with expressive human pitch & cadence
    selected_voice = voice if (voice and voice.startswith("bn-")) else DEFAULT_VOICE
    
    # Emotional prosody tuning
    if not rate:
        if style == "gentle":
            selected_rate = "-2%"
        elif style == "expressive":
            selected_rate = "+2%" if "Nabanita" in selected_voice or "Tanishaa" in selected_voice else "+1%"
        else:
            selected_rate = DEFAULT_RATE
    else:
        selected_rate = rate

    if not pitch:
        if style == "gentle":
            selected_pitch = "+0Hz"
        elif style == "expressive":
            # Female voices get a slight +2Hz lift for warm loving daughter inflection
            selected_pitch = "+2Hz" if ("Nabanita" in selected_voice or "Tanishaa" in selected_voice) else "+1Hz"
        else:
            selected_pitch = DEFAULT_PITCH
    else:
        selected_pitch = pitch

    try:
        import edge_tts
        communicate = edge_tts.Communicate(
            text=expressive_text,
            voice=selected_voice,
            rate=selected_rate,
            pitch=selected_pitch
        )
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                yield chunk["data"]
    except Exception as e:
        logger.error(f"Edge-TTS streaming error: {e}")

async def synthesize_speech(
    text: str,
    output_path: Optional[str] = None,
    voice: Optional[str] = None,
    rate: Optional[str] = None,
    pitch: Optional[str] = None
) -> bytes:
    """
    Synthesize Bangla text to MP3 audio bytes.
    If output_path is provided, also writes the audio to disk.
    """
    expressive_text = format_expressive_bengali_text(text)
    if not expressive_text:
        return b""

    selected_voice = voice if (voice and voice.startswith("bn-")) else DEFAULT_VOICE
    selected_rate = rate or DEFAULT_RATE
    selected_pitch = pitch or DEFAULT_PITCH

    try:
        import edge_tts
        communicate = edge_tts.Communicate(
            text=expressive_text,
            voice=selected_voice,
            rate=selected_rate,
            pitch=selected_pitch
        )
        audio_buffer = bytearray()
        
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_buffer.extend(chunk["data"])
        
        audio_bytes = bytes(audio_buffer)
        
        if output_path:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(audio_bytes)
                
        return audio_bytes
    except Exception as e:
        logger.error(f"TTS synthesis failed for text '{text[:40]}...': {e}")
        raise e
