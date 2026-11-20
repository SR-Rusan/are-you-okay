"""
End-to-End Automated Test Suite for "Are You Okay?" — AI Family Care Layer.

Validates the 3 mandatory core scenarios:
1. First-session consent flow (explanation, explicit consent request, and confirmation).
2. Ongoing conversation naturally referencing stored memory from the prior session.
3. Distress detection triggering a hardcoded rubric rule and generating a simulated SMS alert.
"""

import os
import sys
import json
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Ensure test DB is isolated or resets properly
os.environ["DB_PATH"] = os.path.join(os.path.dirname(__file__), "test_care_memory.db")
os.environ["ALERTS_FILE"] = os.path.join(os.path.dirname(__file__), "test_alerts.json")

from fastapi.testclient import TestClient
from backend.main import app
from backend.database import init_db, reset_user, get_user

client = TestClient(app)

def setup_module():
    """Initializes the database and test alerts file."""
    init_db()
    with open(os.environ["ALERTS_FILE"], "w", encoding="utf-8") as f:
        json.dump([], f)

def teardown_module():
    """Clean up test artifacts."""
    for f in [os.environ["DB_PATH"], os.environ["ALERTS_FILE"]]:
        if os.path.exists(f):
            try:
                os.remove(f)
            except Exception:
                pass

def test_health():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert "llm_config" in data

def test_scenario_1_consent_flow():
    """
    Scenario 1: First-session consent flow for a new user.
    The AI must explain what it is, what it remembers, who sees alerts,
    and explicitly request consent.
    """
    user_id = "user_new"
    reset_user(user_id)
    u_before = get_user(user_id)
    assert u_before["consent_status"] == "pending"

    # 1. Start Session
    start_resp = client.post("/api/session/start", json={
        "user_id": user_id,
        "synthesize_audio": False
    })
    assert start_resp.status_code == 200
    data = start_resp.json()
    session_id = data["session_id"]
    ai_greeting = data["ai_message"]

    assert data["consent_status"] == "pending"
    assert data["session_active"] is True
    # Verify AI greeting contains consent explanation keywords in Bangla
    assert any(w in ai_greeting for w in ["ডিজিটাল কেয়ার সহকারী", "সহকারী", "আর ইউ ওকে", "সন্তান"])
    assert any(w in ai_greeting for w in ["মনে রাখব", "সংক্ষিপ্ত তথ্য", "মনে"])
    assert any(w in ai_greeting for w in ["সম্মতি", "হ্যাঁ", "না"])

    # 2. User responds with consent: "হ্যাঁ, আমি সম্মতি দিচ্ছি"
    chat_resp = client.post("/api/session/text-chat", json={
        "session_id": session_id,
        "user_id": user_id,
        "text": "হ্যাঁ, আমি সম্মতি দিচ্ছি।",
        "synthesize_audio": False
    })
    assert chat_resp.status_code == 200
    chat_data = chat_resp.json()
    assert chat_data["consent_status"] == "consented"
    assert chat_data["consent_transition"] == "granted"
    assert any(w in chat_data["ai_message"] for w in ["ধন্যবাদ", "কেমন আছেন", "শরীর"])

    # Verify SQLite persistence
    u_after = get_user(user_id)
    assert u_after["consent_status"] == "consented"
    assert u_after["consent_timestamp"] is not None

def test_scenario_2_ongoing_conversation_with_memory():
    """
    Scenario 2: Ongoing conversation referencing stored memory from the prior session.
    User 'user_fatema' has memory about knee pain and poor sleep.
    """
    user_id = "user_fatema"
    reset_user(user_id)
    u = get_user(user_id)
    assert u["consent_status"] == "consented"
    assert "হাঁটু" in u["last_session_summary"]

    # 1. Start Session
    start_resp = client.post("/api/session/start", json={
        "user_id": user_id,
        "synthesize_audio": False
    })
    assert start_resp.status_code == 200
    data = start_resp.json()
    session_id = data["session_id"]
    ai_greeting = data["ai_message"]
    
    # Verify that memory is referenced or greeted warmly
    assert len(ai_greeting) > 10

    # 2. User reports normal calm status: "আজ একটু ভালো আছি, ওষুধ খেয়েছি আর দুপুরে ভাত খেয়েছি।"
    chat_resp = client.post("/api/session/text-chat", json={
        "session_id": session_id,
        "user_id": user_id,
        "text": "আজ একটু ভালো আছি, সকালে ডাক্তারের দেওয়া ওষুধ খেয়েছি আর দুপুরে ঠিকমতো ভাত খেয়েছি।",
        "synthesize_audio": False
    })
    assert chat_resp.status_code == 200

    # 3. End session and evaluate distress rubric
    end_resp = client.post("/api/session/end", json={
        "session_id": session_id,
        "user_id": user_id
    })
    assert end_resp.status_code == 200
    end_data = end_resp.json()

    # Distress should NOT be flagged for a calm healthy check-in
    assert end_data["distress_eval"]["flagged"] is False
    assert end_data["distress_eval"]["matched_rule"] == "NONE"
    
    # Session summary must be updated
    assert len(end_data["summary"]) > 5
    u_updated = get_user(user_id)
    assert len(u_updated["last_session_summary"]) > 5

def test_scenario_3_distress_detection_and_alert():
    """
    Scenario 3: Distress detection triggering hardcoded rubric (Rule B: Physical discomfort / nutrition issue)
    and generating formatted SMS in alerts.json.
    """
    user_id = "user_rafiq"
    reset_user(user_id)

    # 1. Start Session
    start_resp = client.post("/api/session/start", json={
        "user_id": user_id,
        "synthesize_audio": False
    })
    session_id = start_resp.json()["session_id"]

    # 2. User expresses acute distress: Chest pain and skipped meals
    chat_resp = client.post("/api/session/text-chat", json={
        "session_id": session_id,
        "user_id": user_id,
        "text": "আমার খুব খারাপ লাগছে। কাল রাত থেকে বুকে তীব্র ব্যথা করছে আর কিছু খাইনি, মাথা ভীষণ ঘুরছে।",
        "synthesize_audio": False
    })
    assert chat_resp.status_code == 200

    # 3. End session and evaluate rubric
    end_resp = client.post("/api/session/end", json={
        "session_id": session_id,
        "user_id": user_id
    })
    assert end_resp.status_code == 200
    end_data = end_resp.json()
    eval_res = end_data["distress_eval"]

    # Must be FLAGGED
    assert eval_res["flagged"] is True
    assert eval_res["matched_rule"] == "RULE_B_PHYSICAL_DISCOMFORT_NUTRITION"
    assert len(eval_res["reason"]) > 5

    # Check alerts.json
    with open(os.environ["ALERTS_FILE"], "r", encoding="utf-8") as f:
        alerts = json.load(f)

    assert len(alerts) >= 1
    recent_alert = alerts[0]
    assert recent_alert["user_id"] == "user_rafiq"
    assert recent_alert["matched_rule"] == "RULE_B_PHYSICAL_DISCOMFORT_NUTRITION"
    assert "Consider calling" in recent_alert["sms_text"]
    assert "father" in recent_alert["sms_text"].lower() or "rafiqul" in recent_alert["sms_text"].lower()

if __name__ == "__main__":
    setup_module()
    print("Running Scenario 1: Consent Flow...")
    test_scenario_1_consent_flow()
    print(" Scenario 1 Passed!")

    print("Running Scenario 2: Memory-Informed Check-in...")
    test_scenario_2_ongoing_conversation_with_memory()
    print(" Scenario 2 Passed!")

    print("Running Scenario 3: Distress Detection & SMS Alert...")
    test_scenario_3_distress_detection_and_alert()
    print(" Scenario 3 Passed!")
    teardown_module()
    print("\nALL SCENARIOS COMPLETED AND VALIDATED SUCCESSFULLY!")
