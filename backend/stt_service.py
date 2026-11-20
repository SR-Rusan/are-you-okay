"""
Speech-to-Text (STT) Service for Bengali Spoken Audio.

Provides multi-tiered speech recognition:
1. Cloud High-Accuracy Tier:
   - Groq API (whisper-large-v3, ultra-fast 300ms, free tier)
   - Google Gemini 1.5 Flash (multimodal audio, free tier)
2. Local Offline Tier (Zero Network / Zero Cost):
   - faster-whisper ('small' cached model with INT8 quantization on CPU)
   - Direct Devanagari-to-Bengali Unicode transduction (+0x080 code point shift)
   - Avro Phonetic Engine (avro.py) for English/Romanized speech patterns
   - Whisper acoustic phonetics normalizer & Indic orthography correction
"""

import os
import sys
import re
import logging
import tempfile
import subprocess
import base64
from typing import Optional
from dotenv import load_dotenv

# Load .env file automatically
load_dotenv()

logger = logging.getLogger("are_you_okay.stt")

# Ensure /Users/rusan/.local/bin is in PATH for ffmpeg
LOCAL_BIN = os.path.expanduser("~/.local/bin")
if LOCAL_BIN not in os.environ.get("PATH", ""):
    os.environ["PATH"] = f"{LOCAL_BIN}:{os.environ.get('PATH', '')}"

# Check for cached small model first; fallback to base
SMALL_CACHE_DIR = os.path.expanduser("~/.cache/huggingface/hub/models--Systran--faster-whisper-small")
DEFAULT_MODEL = "small" if os.path.exists(SMALL_CACHE_DIR) else "base"
WHISPER_MODEL_SIZE = os.environ.get("WHISPER_MODEL", DEFAULT_MODEL)
COMPUTE_TYPE = os.environ.get("WHISPER_COMPUTE_TYPE", "int8")

def get_groq_api_key():
    return os.environ.get("GROQ_API_KEY", "")

def get_gemini_api_key():
    return os.environ.get("GEMINI_API_KEY", os.environ.get("GOOGLE_API_KEY", ""))

_whisper_instance = None

try:
    import avro
except ImportError:
    avro = None

def get_stt_backend_name() -> str:
    """Returns the descriptive name of the currently active STT provider."""
    if get_groq_api_key():
        return "Groq Whisper-Large-v3 (Cloud High-Accuracy)"
    if get_gemini_api_key():
        return "Google Gemini 1.5 Flash (Multimodal Audio)"
    return f"Local faster-whisper ({WHISPER_MODEL_SIZE}) + Bengali Script Normalizer"

def get_whisper_model():
    """Lazy loader for the local faster-whisper model."""
    global _whisper_instance
    if _whisper_instance is None:
        try:
            from faster_whisper import WhisperModel
            logger.info(f"Loading faster-whisper model '{WHISPER_MODEL_SIZE}' on CPU (compute_type={COMPUTE_TYPE})...")
            _whisper_instance = WhisperModel(
                WHISPER_MODEL_SIZE,
                device="cpu",
                compute_type=COMPUTE_TYPE,
                cpu_threads=4
            )
            logger.info(f"faster-whisper model '{WHISPER_MODEL_SIZE}' successfully loaded.")
        except Exception as e:
            logger.error(f"Failed to initialize faster-whisper: {e}")
            raise e
    return _whisper_instance

def convert_to_wav_16k(input_path: str) -> str:
    """Converts audio into 16kHz mono 16-bit PCM WAV for optimal acoustic fidelity."""
    wav_path = input_path + ".normalized.wav"
    try:
        cmd = [
            "ffmpeg", "-y", "-i", input_path,
            "-ar", "16000",
            "-ac", "1",
            "-c:a", "pcm_s16le",
            wav_path
        ]
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return wav_path
    except Exception as e:
        logger.warning(f"ffmpeg conversion note: {e}. Using original audio file.")
        return input_path

def devanagari_to_bengali_unicode(text: str) -> str:
    """
    Shifts Devanagari unicode code points (0x0900 - 0x097F) directly
    to their corresponding Bengali code points (0x0980 - 0x09FF).
    Whisper's acoustic encoder frequently decodes Bengali into Devanagari
    characters with high acoustic fidelity; this maps them to Bengali script.
    """
    converted = []
    for ch in text:
        cp = ord(ch)
        if 0x0900 <= cp <= 0x097F:
            converted.append(chr(cp + 0x080))
        else:
            converted.append(ch)
    return ''.join(converted)

# Phonetic and acoustic substitutions for spoken Bengali
PHONETIC_PAIRS = [
    # Multi-word phrases & common elder expressions
    (r'\bamitua\b', 'আমি তো'),
    (r'\bamitu\b', 'আমি তো'),
    (r'\bami\s*to\b', 'আমি তো'),
    (r'\bbanu\s*la\b', 'বাংলা'),
    (r'\bbangla[\'’]i\b', 'বাংলায়'),
    (r'\bbanglay\b', 'বাংলায়'),
    (r'\bkodha\b', 'কথা'),
    (r'\bkotha\b', 'কথা'),
    (r'\bvulta\b', 'বলতে'),
    (r'\bbolte\b', 'বলতে'),
    (r'\bchachikin\s*to\b', 'চাচ্ছি কিন্তু'),
    (r'\bcha\s*chikintu\b', 'চাচ্ছি কিন্তু'),
    (r'\bchachchi\b', 'চাচ্ছি'),
    (r'\bchacchi\b', 'চাচ্ছি'),
    (r'\bkodva\b', 'কথা'),
    (r'\bvulte\b', 'বলতে'),
    (r'\bbaccin\s*ake\s*no\b', 'পারছি না কেন'),
    (r'\bparcinah\b', 'পারছি না'),
    (r'\bparchina\b', 'পারছি না'),
    (r'\bparchi\s*na\b', 'পারছি না'),
    (r'\bkeno\b', 'কেন'),
    (r'\bassalamualaikum|as-salamu alaykum|asalamu alaikum|salam\b', 'আসসালামু আলাইকুম'),
    (r'\balhamdulillah|al hamdu lillah\b', 'আলহামদুলিল্লাহ'),
    (r'\bshommoti\s*dichhi\b', 'সম্মতি দিচ্ছি'),
    (r'\bshommoti\s*dicchi\b', 'সম্মতি দিচ্ছি'),
    (r'\bsommoti\s*dicchi\b', 'সম্মতি দিচ্ছি'),
    (r'\bshommoti\b', 'সম্মতি'),
    (r'\bsommoti\b', 'সম্মতি'),
    (r'\bdorkar\s*nei\b', 'দরকার নেই'),
    (r'\bdorkar\s*nai\b', 'দরকার নেই'),
    (r'\bkichu\s*khaini\b', 'কিছু খাইনি'),
    (r'\bkisu\s*kaini\b', 'কিছু খাইনি'),
    (r'\bmatha\s*ghurchhe\b', 'মাথা ঘুরছে'),
    (r'\bmatha\s*ghurche\b', 'মাথা ঘুরছে'),
    (r'\bshorir\s*khub\s*kharap\b', 'শরীর খুব খারাপ'),
    (r'\bsorir\s*kub\s*karap\b', 'শরীর খুব খারাপ'),
    (r'\bshorir\s*kharap\b', 'শরীর খারাপ'),
    (r'\bsorir\s*karap\b', 'শরীর খারাপ'),
    (r'\bshorir\b', 'শরীর'),
    (r'\bsorir\b', 'শরীর'),
    (r'\bbuke\s*byatha\b', 'বুকে ব্যথা'),
    (r'\bbuke\s*betha\b', 'বুকে ব্যথা'),
    (r'\bbyatha\b', 'ব্যথা'),
    (r'\bbetha\b', 'ব্যথা'),
    (r'\bdaktar\s*dakun\b', 'ডাক্তার ডাকুন'),
    (r'\bdaktar\b', 'ডাক্তার'),
    (r'\bkhub\s*eka\b', 'খুব একা'),
    (r'\bbhalo\s*achi\b', 'ভালো আছি'),
    (r'\bvalo\s*asi\b', 'ভালো আছি'),
    (r'\bamar\b', 'আমার'),
    (r'\bapnar\b', 'আপনার'),
    (r'\bapni\b', 'আপনি'),
    (r'\btumi\b', 'তুমি'),
    (r'\bkemon\b', 'কেমন'),
    (r'\bachen\b', 'আছেন'),
    (r'\be[i|y]\s*to\b', 'এই তো'),
]

BENGALI_SPELLING_CORRECTIONS = [
    (r'(^|\s)আমী(\s|$|,|\.)', r'\1আমি\2'),
    (r'(^|\s)অমী(\s|$|,|\.)', r'\1আমি\2'),
    (r'(^|\s)আমিতো(\s|$|,|\.)', r'\1আমি তো\2'),
    (r'বাংগলে|বংখলে|ভংখলে|বংগলৈ|বংগলে|বাংলাই', 'বাংলায়'),
    (r'বংগলা', 'বাংলা'),
    (r'কোত্হ|কোতঃ|কোথা|কোতা|কো\s*থা|কো\s*ঠা', 'কথা'),
    (r'ভূল্তে|ভুলতে|বোল্তে|বোলতে|বূল্তে|ব৉ল্টে|বল্তে', 'বলতে'),
    (r'চাত্ছি|চকিন্তু', 'চাচ্ছি'),
    (r'চাছী|চাছি', 'চাচ্ছি'),
    (r'কিন\s*তো', 'কিন্তু'),
    (r'পার্ছি\s*না|পর\s*ছিনা|পর্ছিনা|পার্চিনা|পারছিনা', 'পারছি না'),
    (r'(^|\s)আমা(\s|$)', r'\1আমার\2'),
    (r'হাতু\s*তে|হাঁটূতে', 'হাঁটুতে'),
    (r'কুব|খ়ুব', 'খুব'),
    (r'বেতা|ব্যাথ়া|ব্যেথা', 'ব্যথা'),
    (r'কুর্চে', 'করছে'),
    (r'কুর্চী', 'করছি'),
    (r'এক\s*বোদ', 'একা বোধ'),
    (r'ক্যো', 'কেউ'),
    (r'খূজ|খোজ', 'খোঁজ'),
    (r'নেনা\b', 'নেয় না'),
    (r'খাল\s*রাত্তে\s*কে', 'কাল রাত থেকে'),
    (r'কী\s*চীচু|কী\s*কিছু', 'কিছু'),
    (r'চীচু', 'কিছু'),
    (r'খাযনী', 'খাইনি'),
    (r'মাতা', 'মাথা'),
    (r'গূর্চে', 'ঘুরছে'),
    (r'সোম্মতি', 'সম্মতি'),
    (r'শাহাজ়র|সাহ়ায্যের', 'সাহায্যের'),
    (r'দর\s*কর\s*নহীং', 'দরকার নেই'),
    (r'ভ়ালো', 'ভালো'),
    (r'আছ়ি|আচী|অচি', 'আছি'),
    (r'আল্হাম\s*দূলিল্লা|আল-হামদুলিল্লাহ', 'আলহামদুলিল্লাহ'),
]

def normalize_bengali_transcript(raw_text: str) -> str:
    """
    Ensures raw speech transcript is transformed into authentic Bengali script (বাংলা লিপি).
    Filters repetitive hallucinations, maps Devanagari to Bengali, applies Avro phonetics,
    and corrects common acoustic distortions.
    """
    text = raw_text.strip()
    if not text:
        return text

    # 1. Hallucination filter (Whisper low-resource repetitive video junk)
    junk_patterns = [
        r'instagram', r'newspapers', r'chocol', r'subtitles',
        r'subscribe', r'thank you for watching', r'amara\.org'
    ]
    lower = text.lower()
    for jp in junk_patterns:
        if re.search(jp, lower) and len(text.split()) < 10:
            logger.warning(f"Filtered Whisper hallucination segment: '{text}'")
            return ""

    # 2. Convert Devanagari code points to Bengali code points
    t = devanagari_to_bengali_unicode(text)

    # 3. Apply phonetic pairs for common spoken Banglish words
    for pat, rep in PHONETIC_PAIRS:
        t = re.sub(pat, rep, t, flags=re.IGNORECASE)

    # 4. If Latin characters remain, parse through Avro Phonetic engine
    latin_words = re.findall(r'[a-zA-Z]+', t)
    if latin_words and avro:
        for lw in latin_words:
            try:
                avro_bn = avro.parse(lw)
                if avro_bn and avro_bn != lw:
                    t = re.sub(rf'\b{re.escape(lw)}\b', avro_bn, t)
            except Exception:
                pass

    # 5. Apply Bengali orthographic corrections
    for pat, rep in BENGALI_SPELLING_CORRECTIONS:
        t = re.sub(pat, rep, t)

    return re.sub(r'\s+', ' ', t).strip()

def transcribe_with_groq(audio_path: str) -> Optional[str]:
    """Transcribes audio using Groq's free-tier whisper-large-v3 (ultra-fast & highly accurate)."""
    api_key = get_groq_api_key()
    if not api_key:
        return None
    try:
        import httpx
        url = "https://api.groq.com/openai/v1/audio/transcriptions"
        headers = {"Authorization": f"Bearer {api_key}"}
        with open(audio_path, "rb") as f:
            files = {"file": (os.path.basename(audio_path), f, "audio/wav")}
            data = {
                "model": "whisper-large-v3",
                "language": "bn",
                "response_format": "json"
            }
            with httpx.Client(timeout=20.0) as client:
                res = client.post(url, headers=headers, files=files, data=data)
                if res.status_code == 200:
                    text = res.json().get("text", "").strip()
                    logger.info(f"Groq whisper-large-v3 transcription: '{text}'")
                    return text
                else:
                    logger.warning(f"Groq STT error {res.status_code}: {res.text}")
    except Exception as e:
        logger.warning(f"Groq STT failed: {e}")
    return None

def transcribe_with_gemini(audio_path: str) -> Optional[str]:
    """Transcribes audio using Google Gemini 1.5 Flash multimodal capabilities."""
    api_key = get_gemini_api_key()
    if not api_key:
        return None
    try:
        import httpx
        with open(audio_path, "rb") as f:
            audio_b64 = base64.b64encode(f.read()).decode("utf-8")

        ext = os.path.splitext(audio_path)[1].lower().strip(".")
        mime_type = "audio/wav" if "wav" in ext else ("audio/webm" if "webm" in ext else "audio/mp3")

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
        payload = {
            "contents": [{
                "parts": [
                    {"text": "Transcribe this spoken audio verbatim into clean Bengali script (বাংলা লিপি). Output ONLY the transcribed Bengali text, nothing else. Do not translate to English."},
                    {
                        "inline_data": {
                            "mime_type": mime_type,
                            "data": audio_b64
                        }
                    }
                ]
            }],
            "generationConfig": {
                "temperature": 0.0
            }
        }
        with httpx.Client(timeout=20.0) as client:
            res = client.post(url, json=payload)
            if res.status_code == 200:
                data = res.json()
                candidates = data.get("candidates", [])
                if candidates:
                    text = candidates[0]["content"]["parts"][0]["text"].strip()
                    logger.info(f"Gemini 1.5 Flash transcription: '{text}'")
                    return text
            else:
                logger.warning(f"Gemini STT error {res.status_code}: {res.text}")
    except Exception as e:
        logger.warning(f"Gemini STT failed: {e}")
    return None

def transcribe_audio_file(audio_path: str, language: str = "bn") -> str:
    """
    Transcribes an audio file into Bengali script.
    Checks Cloud Tier first (Groq/Gemini if configured),
    then falls back to local faster-whisper with Indic script normalization.
    """
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio file does not exist: {audio_path}")

    # Step 1: Try Cloud High-Accuracy Providers directly (Groq/Gemini accept webm/mp3 directly with 0 ffmpeg latency)
    groq_key = get_groq_api_key()
    if groq_key:
        cloud_text = transcribe_with_groq(audio_path)
        if cloud_text:
            return normalize_bengali_transcript(cloud_text)

    gemini_key = get_gemini_api_key()
    if gemini_key:
        cloud_text = transcribe_with_gemini(audio_path)
        if cloud_text:
            return normalize_bengali_transcript(cloud_text)

    # Step 2: Normalize audio to 16kHz mono WAV for local faster-whisper
    wav_path = convert_to_wav_16k(audio_path)

    # Step 3: Local faster-whisper inference
    model = get_whisper_model()
    logger.info(f"Transcribing audio file locally: {wav_path} (forced language: '{language}')...")

    segments, info = model.transcribe(
        wav_path,
        language=language,
        task="transcribe",
        beam_size=5,
        no_repeat_ngram_size=3,
        repetition_penalty=1.2,
        initial_prompt=None,
        condition_on_previous_text=False,
        vad_filter=True,
        vad_parameters=dict(min_silence_duration_ms=400, speech_pad_ms=250)
    )

    full_text = " ".join([segment.text for segment in segments]).strip()
    logger.info(f"Raw Whisper transcription: '{full_text}'")

    # Step 4: Bengali Script & Phonetics Normalization
    normalized_text = normalize_bengali_transcript(full_text)
    logger.info(f"Final normalized transcription: '{normalized_text}'")

    # Cleanup temporary normalized WAV
    if wav_path != audio_path and os.path.exists(wav_path):
        try:
            os.remove(wav_path)
        except Exception:
            pass

    return normalized_text

def transcribe_audio_bytes(audio_bytes: bytes, file_ext: str = "webm", language: str = "bn") -> str:
    """Writes audio bytes to a temporary file, normalizes, and transcribes it."""
    with tempfile.NamedTemporaryFile(suffix=f".{file_ext}", delete=False) as temp_audio:
        temp_audio.write(audio_bytes)
        temp_path = temp_audio.name

    try:
        text = transcribe_audio_file(temp_path, language=language)
        return text
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass
