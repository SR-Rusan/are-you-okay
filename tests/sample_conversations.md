# Sample Test Conversation Logs & Evaluations
### Project: "Are You Okay?" (আর ইউ ওকে?) — AI Family Care Layer

This document contains end-to-end simulated conversation logs demonstrating the three mandatory scenarios validated during the MVP test suite.

---

## Scenario 1: First-Session Consent Flow (New User ID: `user_new`)

**Context:** Chhobi Begum (`ছবি বেগম`) has just been registered by her son Tanvir Ahmed (`তানভীর আহমেদ`), who lives and works abroad in Toronto, Canada. Consent is a first-class feature: the AI **never** assumes consent and must explain who it is, what it remembers, who sees alerts, and explicitly request consent before proceeding.

### Dialogue Transcript:

> **🤖 AI Caregiver:**  
> "আসসালামু আলাইকুম। আমি 'আর ইউ ওকে?'—আপনার প্রবাসী সন্তানের পক্ষ থেকে তৈরি একটি ডিজিটাল কেয়ার সহকারী। আমি নিয়মিত আপনার কুশল জানতে চাইব এবং আপনার শারীরিক ও মানসিক অনুভূতির সংক্ষিপ্ত তথ্য মনে রাখব, যাতে পরের বার খোঁজ নিতে পারি। যদি কখনো আপনার কোনো মারাত্মক অসুবিধা বা একাকীত্ব বোধ হয়, শুধুমাত্র তখনই আপনার সন্তানের কাছে একটি সংক্ষিপ্ত বার্তা যাবে—অন্য কোনো তথ্য বাইরে যাবে না। আপনি কি আমার সাথে এভাবে নিয়মিত কথা বলতে সম্মতি দিচ্ছেন? অনুগ্রহ করে 'হ্যাঁ' অথবা 'না' বলুন।"  
> *(As-salamu alaykum. I am 'Are You Okay?'—a digital care assistant created on behalf of your expatriate child. I will regularly ask about your wellbeing and remember a brief summary of how your body and mind feel, so I can follow up next time. If you ever feel severely unwell or lonely, only then will a short alert be sent to your child—no other information will be shared outside. Do you consent to speaking with me regularly in this way? Please say 'Yes' or 'No'.)*

> **👤 Parent (Chhobi Begum):**  
> "হ্যাঁ, আমি সম্মতি দিচ্ছি।"  
> *(Yes, I give my consent.)*

> **🤖 AI Caregiver:**  
> "অনেক ধন্যবাদ আপনার আস্থার জন্য! আমি সবসময় আপনার পাশে আছি। কেমন আছেন আজকে আপনি? শরীরটা কেমন লাগছে?"  
> *(Thank you so much for your trust! I am always here for you. How are you today? How is your health feeling?)*

### State & Database Outcome:
- **`consent_status`**: Changed from `pending` ➔ `consented`
- **`consent_timestamp`**: `2026-09-24T15:36:50.525Z`
- **Session State**: Transitioned to active check-in.

---

## Scenario 2: Ongoing Conversation with Memory Follow-Up (User ID: `user_fatema`)

**Context:** Fatema Begum (`বেগম ফাতেমা`) previously consented. In her prior session, she mentioned she had right knee pain and couldn't sleep well at night. In this session, the AI companion automatically injects that memory and warmly follows up on her knee and sleep.

### Dialogue Transcript:

> **🤖 AI Caregiver:**  
> "আসসালামু আলাইকুম খালাম্মা! কেমন আছেন আজকে আপনি? গতবার আপনি বলেছিলেন আপনার ডান হাঁটুতে বেশ ব্যথা করছিল আর রাতে ঘুমে একটু সমস্যা হচ্ছিল। এখন ব্যথাটা কেমন? ডাক্তার কি দেখানো হয়েছিল?"  
> *(As-salamu alaykum Khalammo! How are you today? Last time you mentioned your right knee was hurting quite a bit and you had trouble sleeping at night. How is the pain now? Did you see the doctor?)*

> **👤 Parent (Fatema Begum):**  
> "আজ একটু ভালো আছি, সকালে ডাক্তারের দেওয়া ওষুধ খেয়েছি আর দুপুরে ঠিকমতো ভাত খেয়েছি।"  
> *(I am a bit better today, I took the medicine prescribed by the doctor in the morning, and ate my rice properly at lunch.)*

> **🤖 AI Caregiver:**  
> "আলহামদুলিল্লাহ, শুনে খুব শান্তি পেলাম খালাম্মা! নিয়মিত ওষুধগুলো খেয়ে নেবেন আর কোনো ভারী কাজ করবেন না। প্রয়োজন হলে একটু বিশ্রাম নিন।"  
> *(Alhamdulillah, it brings such peace of mind to hear that! Please continue taking your medicines regularly and avoid heavy chores. Get some good rest when needed.)*

### Post-Session Distress Rubric Audit:
```json
{
  "flagged": false,
  "reason": "Parent reported calm condition, took medication/meals, or showed no signs matching the distress rubric.",
  "matched_rule": "NONE"
}
```

### Generated Session Summary (Stored in SQLite `last_session_summary`):
> *"অভিভাবক বেগম ফাতেমা জানিয়েছেন তিনি আজ তুলনামূলক ভালো আছেন। সকালে ডাক্তারের প্রেসক্রিপশনের ওষুধ গ্রহণ করেছেন এবং দুপুরে নিয়মিত খাবার খেয়েছেন। হাঁটুর ব্যথা উন্নতির দিকে।"*

---

## Scenario 3: Distress Detection Triggered & Simulated SMS Dispatch (User ID: `user_rafiq`)

**Context:** Rafiqul Islam (`রফিকুল ইসলাম`) is checked in on. His daughter Farhana lives in Sydney, Australia. During the session, he reports acute chest pain, dizziness, and that he hasn't eaten since last night. The post-session clinical rubric triggers Rule (b) and immediately logs a formatted SMS alert to the console and `alerts.json`.

### Dialogue Transcript:

> **🤖 AI Caregiver:**  
> "আসসালামু আলাইকুম চাচা! কেমন আছেন আজকে? শরীর ও দিনকাল কেমন যাচ্ছে আপনার?"  
> *(As-salamu alaykum Chacha! How are you today? How are your health and spirits?)*

> **👤 Parent (Rafiqul Islam):**  
> "আমার খুব খারাপ লাগছে। কাল রাত থেকে বুকে তীব্র ব্যথা করছে আর কিছু খাইনি, মাথা ভীষণ ঘুরছে।"  
> *(I am feeling very bad. Since last night I have had severe chest pain and haven't eaten anything, and my head is spinning heavily.)*

> **🤖 AI Caregiver:**  
> "ইন্নালিল্লাহ, চাচা! আপনি একদম নড়াচড়া করবেন না, সাবধানে সোজা হয়ে বসুন অথবা আরাম করে শুয়ে পড়ুন। আপনার সন্তান ও স্বজনদের দ্রুত অবহিত করা হচ্ছে। কোনো ওষুধ বা সাহায্যের প্রয়োজন হলে এখনই জানান।"  
> *(Chacha, please do not strain yourself! Sit upright carefully or lie down comfortably. Your family is being notified immediately. If you need medicine or immediate assistance, tell me right away.)*

### Distress Rubric Evaluation (Separate Dedicated LLM Audit):
- **Rule Evaluated Against:**
  - *(a) Explicit statements of loneliness/sadness*
  - *(b) Explicit statements of physical discomfort or not eating well* ➔ **MATCHED**
  - *(c) Unusually short/withdrawn replies*
  - *(d) Explicit requests for help*
- **Structured JSON Output:**
```json
{
  "flagged": true,
  "reason": "Parent explicitly reported physical suffering or nutrition failure ('বুকে তীব্র ব্যথা').",
  "matched_rule": "RULE_B_PHYSICAL_DISCOMFORT_NUTRITION"
}
```

### Simulated Console Output:
```
======================================================================
🚨 [ARE YOU OKAY? — DISTRESS ALERT TRIGGERED]
Time: 2026-09-24 15:37:24
Target Family Contact: ফারহানা হক (মেয়ে (প্রবাসী - সিডনি, অস্ট্রেলিয়া), +61-491-570156)
Parent: রফিকুল ইসলাম (Rafiqul Islam) (User ID: user_rafiq)
Matched Rule: RULE_B_PHYSICAL_DISCOMFORT_NUTRITION
Clinical Reason: Parent explicitly reported physical suffering or nutrition failure ('বুকে তীব্র ব্যথা').
----------------------------------------------------------------------
📱 SIMULATED SMS DISPATCHED:
"Care Alert from 'Are You Okay?': Your father's recent check-in showed signs that reported physical discomfort or skipped meals. Consider calling him today."
======================================================================
```

### Written Entry in `alerts.json`:
```json
[
  {
    "id": "alert_20260924_153724_user_rafiq",
    "timestamp": "2026-09-24T15:37:24.526102",
    "user_id": "user_rafiq",
    "user_name": "রফিকুল ইসলাম (Rafiqul Islam)",
    "family_contact": {
      "name": "ফারহানা হক",
      "relation": "মেয়ে (প্রবাসী - সিডনি, অস্ট্রেলিয়া)",
      "phone": "+61-491-570156"
    },
    "matched_rule": "RULE_B_PHYSICAL_DISCOMFORT_NUTRITION",
    "reason": "Parent explicitly reported physical suffering or nutrition failure ('বুকে তীব্র ব্যথা').",
    "sms_text": "Care Alert from 'Are You Okay?': Your father's recent check-in showed signs that reported physical discomfort or skipped meals. Consider calling him today.",
    "status": "simulated_sent"
  }
]
```
