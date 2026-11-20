import pytest
from backend.stt_service import normalize_bengali_transcript, devanagari_to_bengali_unicode

def test_user_whisper_phonetic_string_normalizes_to_bengali():
    raw_whisper = "Amitua Banu La Kodha Vulta Chachikin To Banu la Kodva Vulte Baccin Ake No"
    normalized = normalize_bengali_transcript(raw_whisper)
    assert "বাংলা" in normalized
    assert "বলতে" in normalized
    assert "কথা" in normalized
    assert "চাচ্ছি" in normalized
    # Confirm it contains authentic Bengali characters
    bangla_chars = [c for c in normalized if '\u0980' <= c <= '\u09ff']
    assert len(bangla_chars) > 20

def test_devanagari_to_bengali_unicode():
    hindi_acoustic = "आमी तो बंगलै कोतः बोल्ते चाछी"
    bengali_script = normalize_bengali_transcript(hindi_acoustic)
    assert "আমি" in bengali_script
    assert "বাংলায়" in bengali_script
    assert "কথা" in bengali_script

def test_elderly_care_phrases_normalize():
    samples = [
        ("amar shorir khub kharap", "শরীর"),
        ("buke byatha korche", "ব্যথা"),
        ("ami shommoti dichhi", "সম্মতি"),
        ("na dorkar nei", "দরকার নেই"),
        ("kichu khaini", "কিছু খাইনি")
    ]
    for raw, expected_token in samples:
        norm = normalize_bengali_transcript(raw)
        assert expected_token in norm, f"Expected '{expected_token}' in '{norm}'"

def test_hallucination_filtered():
    hallucination = "shap gins chocol. newspapers. Instagram."
    filtered = normalize_bengali_transcript(hallucination)
    assert filtered == ""
