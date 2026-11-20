#!/usr/bin/env python3
"""
CLI Simulation Tool for "Are You Okay?" (আর ইউ ওকে?)

Allows running interactive or automated scripted simulations of elderly care sessions
directly in your terminal with colored logs and simulated SMS outputs.
"""

import sys
import os
import time

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from fastapi.testclient import TestClient
from backend.main import app
from backend.database import init_db, reset_user, get_user

client = TestClient(app)

def print_banner(text: str):
    print("\n" + "=" * 65)
    print(f" {text}")
    print("=" * 65)

def run_simulation_scenario(scenario_num: int):
    init_db()

    if scenario_num == 1:
        print_banner("SCENARIO 1: FIRST-SESSION CONSENT FLOW (ছবি বেগম / Chhobi Begum)")
        user_id = "user_new"
        reset_user(user_id)
        
        # 1. Start session
        print("\n[Step 1] Starting session for new user...")
        resp = client.post("/api/session/start", json={"user_id": user_id, "synthesize_audio": False}).json()
        print(f"\n🤖 AI Caregiver:\n\"{resp['ai_message']}\"")
        print(f"   (Consent Status: {resp['consent_status']})")

        # 2. User consents
        user_reply = "হ্যাঁ, আমি সম্মতি দিচ্ছি।"
        print(f"\n👤 Parent:\n\"{user_reply}\"")
        resp = client.post("/api/session/text-chat", json={
            "session_id": resp["session_id"],
            "user_id": user_id,
            "text": user_reply,
            "synthesize_audio": False
        }).json()
        print(f"\n🤖 AI Caregiver:\n\"{resp['ai_message']}\"")
        print(f"   (Consent Status: {resp['consent_status']})")
        print("\n✅ Consent granted and recorded in SQLite!")

    elif scenario_num == 2:
        print_banner("SCENARIO 2: MEMORY FOLLOW-UP CHECK-IN (বেগম ফাতেমা / Fatema Begum)")
        user_id = "user_fatema"
        reset_user(user_id)
        u = get_user(user_id)
        print(f"📌 Stored Memory from Last Session:\n   \"{u['last_session_summary']}\"")

        # 1. Start session
        resp = client.post("/api/session/start", json={"user_id": user_id, "synthesize_audio": False}).json()
        print(f"\n🤖 AI Caregiver (Informed by Memory):\n\"{resp['ai_message']}\"")

        # 2. User replies calm
        user_reply = "আজ একটু ভালো আছি, সকালে ডাক্তারের দেওয়া ওষুধ খেয়েছি আর দুপুরে ঠিকমতো ভাত খেয়েছি।"
        print(f"\n👤 Parent:\n\"{user_reply}\"")
        resp_turn = client.post("/api/session/text-chat", json={
            "session_id": resp["session_id"],
            "user_id": user_id,
            "text": user_reply,
            "synthesize_audio": False
        }).json()
        print(f"\n🤖 AI Caregiver:\n\"{resp_turn['ai_message']}\"")

        # 3. End session
        print("\n[Step 3] Ending session & auditing distress rubric...")
        end_resp = client.post("/api/session/end", json={
            "session_id": resp["session_id"],
            "user_id": user_id
        }).json()
        eval_data = end_resp["distress_eval"]
        print(f"\n📋 Rubric Result: Flagged = {eval_data['flagged']} (Rule: {eval_data['matched_rule']})")
        print(f"   Reason: {eval_data['reason']}")
        print(f"📝 Updated Memory for Next Time:\n   \"{end_resp['summary']}\"")

    elif scenario_num == 3:
        print_banner("SCENARIO 3: DISTRESS DETECTION & SMS ALERT (রফিকুল ইসলাম / Rafiqul Islam)")
        user_id = "user_rafiq"
        reset_user(user_id)

        # 1. Start session
        resp = client.post("/api/session/start", json={"user_id": user_id, "synthesize_audio": False}).json()
        print(f"\n🤖 AI Caregiver:\n\"{resp['ai_message']}\"")

        # 2. User expresses distress
        user_reply = "আমার খুব খারাপ লাগছে। কাল রাত থেকে বুকে তীব্র ব্যথা করছে আর কিছু খাইনি, মাথা ভীষণ ঘুরছে।"
        print(f"\n👤 Parent (Distress):\n\"{user_reply}\"")
        resp_turn = client.post("/api/session/text-chat", json={
            "session_id": resp["session_id"],
            "user_id": user_id,
            "text": user_reply,
            "synthesize_audio": False
        }).json()
        print(f"\n🤖 AI Caregiver:\n\"{resp_turn['ai_message']}\"")

        # 3. End session & evaluate
        print("\n[Step 3] Ending session & auditing distress rubric...")
        end_resp = client.post("/api/session/end", json={
            "session_id": resp["session_id"],
            "user_id": user_id
        }).json()
        eval_data = end_resp["distress_eval"]
        print(f"\n🚨 Rubric Result: FLAGGED = {eval_data['flagged']} (Rule: {eval_data['matched_rule']})")
        print(f"   Reason: {eval_data['reason']}")
        print("📱 Simulated SMS logged to console and saved to alerts.json!")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        run_simulation_scenario(int(sys.argv[1]))
    else:
        print("Running all 3 demo scenarios sequentially...\n")
        run_simulation_scenario(1)
        time.sleep(1)
        run_simulation_scenario(2)
        time.sleep(1)
        run_simulation_scenario(3)
