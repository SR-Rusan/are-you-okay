// "Are You Okay?" — Frontend Application Logic

let state = {
  users: [],
  currentUser: null,
  sessionId: null,
  sessionActive: false,
  mode: 'text', // 'text' | 'voice'
  mediaRecorder: null,
  audioChunks: [],
  recordingInterval: null,
  recordingSeconds: 0,
  currentAudio: null
};

// DOM Elements
const userSelect = document.getElementById('user-select');
const btnResetUser = document.getElementById('btn-reset-user');
const btnModeText = document.getElementById('btn-mode-text');
const btnModeVoice = document.getElementById('btn-mode-voice');
const btnStartSession = document.getElementById('btn-start-session');
const btnEndSession = document.getElementById('btn-end-session');

const dispUserName = document.getElementById('disp-user-name');
const dispKinName = document.getElementById('disp-kin-name');
const dispKinPhone = document.getElementById('disp-kin-phone');
const dispConsentBadge = document.getElementById('disp-consent-badge');
const dispMemoryText = document.getElementById('disp-memory-text');

const sessionDot = document.getElementById('session-dot');
const sessionStatusText = document.getElementById('session-status-text');
const audioPlayingIndicator = document.getElementById('audio-playing-indicator');
const chatMessages = document.getElementById('chat-messages');

const consentPromptActions = document.getElementById('consent-prompt-actions');
const btnQuickConsentYes = document.getElementById('btn-quick-consent-yes');
const btnQuickConsentNo = document.getElementById('btn-quick-consent-no');

const textInputArea = document.getElementById('text-input-area');
const textInput = document.getElementById('text-input');
const btnSendText = document.getElementById('btn-send-text');

const voiceInputArea = document.getElementById('voice-input-area');
const btnMic = document.getElementById('btn-mic');
const micStatusLabel = document.getElementById('mic-status-label');
const recordingTimer = document.getElementById('recording-timer');

const lastEvaluationCard = document.getElementById('last-evaluation-card');
const evalFlagPill = document.getElementById('eval-flag-pill');
const evalRuleName = document.getElementById('eval-rule-name');
const evalReason = document.getElementById('eval-reason');
const evalSmsText = document.getElementById('eval-sms-text');
const alertsFeed = document.getElementById('alerts-feed');
const alertCounter = document.getElementById('alert-counter');
const ttsAudioPlayer = document.getElementById('tts-audio-player');
const llmIndicator = document.getElementById('llm-indicator');
const liveSpeechBox = document.getElementById('live-speech-box');
const liveSpeechText = document.getElementById('live-speech-text');
const sttEngineBadge = document.getElementById('stt-engine-badge');
const ttsVoiceSelect = document.getElementById('tts-voice-select');
const voiceStyleSelect = document.getElementById('voice-style-select');
const btnPreviewVoice = document.getElementById('btn-preview-voice');

// Initialization
document.addEventListener('DOMContentLoaded', async () => {
  setupEventListeners();
  await checkHealth();
  await loadUsers();
  await loadAlerts();
});

async function checkHealth() {
  try {
    const res = await fetch('/api/health');
    const data = await res.json();
    if (data && data.llm_config) {
      llmIndicator.textContent = `LLM: ${data.llm_config.current_provider.toUpperCase()}`;
    }
    if (data && data.stt) {
      console.log("Active STT Engine:", data.stt);
    }
  } catch (e) {
    console.warn("Health check error:", e);
  }
}

function setupEventListeners() {
  // Mode toggles
  btnModeText.addEventListener('click', () => setMode('text'));
  btnModeVoice.addEventListener('click', () => setMode('voice'));

  // User dropdown switch
  userSelect.addEventListener('change', (e) => {
    switchUser(e.target.value);
  });

  // Reset user memory/consent
  btnResetUser.addEventListener('click', resetCurrentPersona);

  // Session start & end
  btnStartSession.addEventListener('click', startNewSession);
  btnEndSession.addEventListener('click', endCurrentSession);

  // Send text message
  btnSendText.addEventListener('click', sendTextMessage);
  textInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendTextMessage();
    }
  });

  // Quick consent responses
  btnQuickConsentYes.addEventListener('click', () => sendTextMessage("হ্যাঁ, আমি সম্মতি দিচ্ছি"));
  btnQuickConsentNo.addEventListener('click', () => sendTextMessage("না, আমার কোনো দরকার নেই"));

  // Voice recording button
  btnMic.addEventListener('click', toggleRecording);

  // Instant Voice Preview button
  if (btnPreviewVoice) {
    btnPreviewVoice.addEventListener('click', () => {
      const voice = ttsVoiceSelect ? ttsVoiceSelect.value : 'bn-BD-NabanitaNeural';
      const style = voiceStyleSelect ? voiceStyleSelect.value : 'expressive';
      const previewUrl = `/api/tts/preview?voice=${encodeURIComponent(voice)}&style=${encodeURIComponent(style)}&t=${Date.now()}`;
      playAudio(previewUrl);
    });
  }

  // Voice selector change listener
  if (ttsVoiceSelect) {
    ttsVoiceSelect.addEventListener('change', (e) => {
      const voiceNames = {
        'bn-BD-NabanitaNeural': 'Voice: Nabanita (Female)',
        'bn-BD-PradeepNeural': 'Voice: Pradeep (Male)',
        'bn-IN-TanishaaNeural': 'Voice: Tanishaa (Female)',
        'bn-IN-BashkarNeural': 'Voice: Bashkar (Male)',
        'nova': 'Voice: OpenAI Nova',
        'alloy': 'Voice: OpenAI Alloy'
      };
      const voiceIndicator = document.getElementById('voice-indicator');
      if (voiceIndicator) {
        voiceIndicator.textContent = voiceNames[e.target.value] || `Voice: ${e.target.value}`;
      }
    });
  }
}

function setMode(mode) {
  state.mode = mode;
  if (mode === 'text') {
    btnModeText.classList.add('active');
    btnModeVoice.classList.remove('active');
    textInputArea.classList.remove('hidden');
    voiceInputArea.classList.add('hidden');
  } else {
    btnModeVoice.classList.add('active');
    btnModeText.classList.remove('active');
    textInputArea.classList.add('hidden');
    voiceInputArea.classList.remove('hidden');
  }
}

async function loadUsers() {
  try {
    const res = await fetch('/api/users');
    const users = await res.json();
    state.users = users;
    
    // Select first or default
    const initialId = userSelect.value || users[0].user_id;
    switchUser(initialId);
  } catch (e) {
    console.error("Error loading users:", e);
  }
}

function switchUser(userId) {
  const user = state.users.find(u => u.user_id === userId);
  if (!user) return;

  state.currentUser = user;
  dispUserName.textContent = user.name;
  dispKinName.textContent = `${user.kin_name} (${user.kin_relation})`;
  dispKinPhone.textContent = user.kin_phone;

  updateConsentBadge(user.consent_status);
  updateMemoryView(user.last_session_summary);

  // Reset chat view
  chatMessages.innerHTML = '';
  appendSystemMessage(`সুইচ করা হয়েছে: ${user.name}। কথোপকথন শুরু করতে 'সেশন শুরু করুন' চাপুন।`);
  
  state.sessionId = null;
  state.sessionActive = false;
  btnEndSession.disabled = true;
  btnStartSession.disabled = false;
  sessionDot.className = "dot dot-idle";
  sessionStatusText.textContent = "সেশন অপেক্ষমাণ।";
  consentPromptActions.classList.add('hidden');
}

function updateConsentBadge(status) {
  dispConsentBadge.className = 'status-pill';
  if (status === 'consented') {
    dispConsentBadge.classList.add('status-consented');
    dispConsentBadge.textContent = '✅ সম্মতিপ্রাপ্ত (Consented)';
  } else if (status === 'declined') {
    dispConsentBadge.classList.add('status-declined');
    dispConsentBadge.textContent = '❌ সম্মতি অস্বীকৃত (Declined)';
  } else {
    dispConsentBadge.classList.add('status-pending');
    dispConsentBadge.textContent = '⏳ সম্মতি অপেক্ষমাণ (Pending)';
  }
}

function updateMemoryView(summary) {
  if (summary && summary.trim()) {
    dispMemoryText.textContent = `"${summary.trim()}"`;
  } else {
    dispMemoryText.textContent = "কোনো পূর্ববর্তী সেশন রেকর্ড নেই (নতুন অভিভাবক)।";
  }
}

async function resetCurrentPersona() {
  if (!state.currentUser) return;
  const userId = state.currentUser.user_id;
  try {
    const res = await fetch(`/api/users/${userId}/reset`, { method: 'POST' });
    const data = await res.json();
    await loadUsers();
    appendSystemMessage(`🔄 ${state.currentUser.name}-এর মেমোরি ও কনসেন্ট সফলভাবে রিসেট করা হয়েছে।`);
  } catch (e) {
    alert("রিসেট ব্যর্থ হয়েছে: " + e.message);
  }
}

async function startNewSession() {
  if (!state.currentUser) return;

  btnStartSession.disabled = true;
  sessionStatusText.textContent = "সেশন চালু হচ্ছে...";
  
  try {
    const res = await fetch('/api/session/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        user_id: state.currentUser.user_id,
        synthesize_audio: true,
        voice: ttsVoiceSelect ? ttsVoiceSelect.value : 'bn-BD-NabanitaNeural',
        style: voiceStyleSelect ? voiceStyleSelect.value : 'expressive'
      })
    });
    const data = await res.json();
    
    state.sessionId = data.session_id;
    state.sessionActive = data.session_active;
    btnEndSession.disabled = !data.session_active;

    sessionDot.className = "dot dot-active";
    sessionStatusText.textContent = "সেশন চলমান...";

    // Append AI greeting
    appendAIMessage(data.ai_message, data.audio_url);

    // Play speech audio automatically
    if (data.audio_url) {
      playAudio(data.audio_url);
    }

    // If consent is pending, display the quick consent prompt bar
    if (data.consent_status === 'pending') {
      consentPromptActions.classList.remove('hidden');
    } else {
      consentPromptActions.classList.add('hidden');
    }

    updateConsentBadge(data.consent_status);
  } catch (e) {
    btnStartSession.disabled = false;
    alert("সেশন শুরু করতে ত্রুটি হয়েছে: " + e.message);
  }
}

async function sendTextMessage(overrideText = null) {
  if (!state.sessionId) {
    alert("অনুগ্রহ করে আগে 'সেশন শুরু করুন' চাপুন।");
    return;
  }

  const text = overrideText || textInput.value.trim();
  if (!text) return;

  appendUserMessage(text);
  if (!overrideText) {
    textInput.value = '';
  }
  consentPromptActions.classList.add('hidden');

  try {
    sessionStatusText.textContent = "AI ভাবছে...";
    const res = await fetch('/api/session/text-chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: state.sessionId,
        user_id: state.currentUser.user_id,
        text: text,
        synthesize_audio: true,
        voice: ttsVoiceSelect ? ttsVoiceSelect.value : 'bn-BD-NabanitaNeural',
        style: voiceStyleSelect ? voiceStyleSelect.value : 'expressive'
      })
    });
    const data = await res.json();

    sessionStatusText.textContent = data.session_active ? "সেশন চলমান..." : "সেশন স্থগিত।";
    appendAIMessage(data.ai_message, data.audio_url);

    if (data.audio_url) {
      playAudio(data.audio_url);
    }

    updateConsentBadge(data.consent_status);
    state.sessionActive = data.session_active;
    btnEndSession.disabled = !data.session_active;

    if (data.consent_status === 'pending') {
      consentPromptActions.classList.remove('hidden');
    }
  } catch (e) {
    console.error("Chat error:", e);
    appendSystemMessage("বার্তা পাঠাতে সমস্যা হয়েছে।");
  }
}

// Voice Recognition State
const SpeechRecognitionAPI = window.SpeechRecognition || window.webkitSpeechRecognition;
let nativeRecognizer = null;
let nativeTranscript = '';

// Voice Recording Handlers
async function toggleRecording() {
  if (!state.sessionId) {
    alert("অনুগ্রহ করে আগে 'সেশন শুরু করুন' চাপুন।");
    return;
  }

  if (state.mediaRecorder && state.mediaRecorder.state === 'recording') {
    stopRecording();
  } else {
    await startRecording();
  }
}

async function startRecording() {
  try {
    state.isRecording = true;
    nativeTranscript = '';
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true
      }
    });
    state.audioChunks = [];
    
    // WebM format with opus codec supported across modern browsers
    let mimeType = 'audio/webm;codecs=opus';
    if (!MediaRecorder.isTypeSupported(mimeType)) {
      mimeType = MediaRecorder.isTypeSupported('audio/webm') ? 'audio/webm' : 'audio/mp4';
    }
    state.mediaRecorder = new MediaRecorder(stream, { mimeType });

    state.mediaRecorder.ondataavailable = (event) => {
      if (event.data && event.data.size > 0) {
        state.audioChunks.push(event.data);
      }
    };

    state.mediaRecorder.onstop = async () => {
      const audioBlob = new Blob(state.audioChunks, { type: mimeType });
      // Stop all microphone tracks immediately
      stream.getTracks().forEach(track => track.stop());

      // Give Web Speech API a brief moment to settle final transcript if active
      await new Promise(r => setTimeout(r, 200));

      if (audioBlob.size < 1200 && (!nativeTranscript || !nativeTranscript.trim())) {
        alert("খুব সংক্ষিপ্ত অডিও রেকর্ড হয়েছে। অনুগ্রহ করে বাটনে চাপ দিয়ে স্পষ্ট করে বাংলায় কথা বলুন।");
        micStatusLabel.textContent = "কথা বলতে মাইক বাটনে ক্লিক করুন";
        liveSpeechText.textContent = "রেকর্ডিং খুব সংক্ষিপ্ত ছিল।";
        return;
      }

      sttEngineBadge.textContent = "হুইস্পার এআই রূপান্তর...";
      liveSpeechText.textContent = nativeTranscript ? `"${nativeTranscript}"` : "অডিও ফাইল থেকে বাংলায় রূপান্তর করা হচ্ছে...";
      // Always send the full recorded audio to the server with nativeTranscript as fallback
      await sendVoiceMessage(audioBlob, nativeTranscript);
    };

    // If browser supports native Web Speech API in bn-BD, activate continuous speech recognition
    if (SpeechRecognitionAPI) {
      try {
        nativeRecognizer = new SpeechRecognitionAPI();
        nativeRecognizer.lang = 'bn-BD'; // Bengali (Bangladesh)
        nativeRecognizer.interimResults = true;
        nativeRecognizer.continuous = true; // DO NOT stop after sentence 1; capture all sentences!

        nativeRecognizer.onresult = (event) => {
          let interim = '';
          let finalAccumulated = '';
          for (let i = 0; i < event.results.length; ++i) {
            const piece = event.results[i][0].transcript;
            if (event.results[i].isFinal) {
              finalAccumulated += piece.trim() + ' ';
            } else {
              interim += piece;
            }
          }
          if (finalAccumulated.trim()) {
            nativeTranscript = finalAccumulated.trim();
          }
          const fullSpoken = (nativeTranscript ? nativeTranscript + ' ' : '') + interim;
          if (fullSpoken.trim()) {
            liveSpeechText.textContent = `"${fullSpoken.trim()}"`;
            micStatusLabel.textContent = `শুনছি: "${fullSpoken.trim()}"`;
            sttEngineBadge.textContent = "লাইভ বাংলা (ব্রাউজার)";
          }
        };

        nativeRecognizer.onend = () => {
          // If the user hasn't pressed stop yet, restart continuous recognition seamlessly
          if (state.isRecording && nativeRecognizer) {
            try {
              nativeRecognizer.start();
            } catch (e) {
              // Ignore if already restarting
            }
          }
        };

        nativeRecognizer.onerror = (e) => {
          console.warn("Native SpeechRecognition note:", e.error);
          sttEngineBadge.textContent = "হুইস্পার এআই ব্যাকএন্ড";
        };

        nativeRecognizer.start();
        sttEngineBadge.textContent = "লাইভ শুনছি (Chrome/Edge)";
      } catch (e) {
        console.warn("Could not start SpeechRecognition:", e);
        sttEngineBadge.textContent = "হুইস্পার এআই ব্যাকএন্ড";
      }
    } else {
      sttEngineBadge.textContent = "হুইস্পার এআই ব্যাকএন্ড";
    }

    // Show live speech preview box
    liveSpeechBox.classList.remove('hidden');
    liveSpeechText.textContent = "শুনছি... একাধিক বাক্যে স্পষ্ট করে বাংলায় বলুন";

    // Emit timeslice chunks every 200ms to guarantee complete audio data
    state.mediaRecorder.start(200);
    btnMic.classList.add('recording');
    micStatusLabel.textContent = "রেকর্ডিং হচ্ছে... একাধিক বাক্যে স্পষ্ট করে বলুন";
    recordingTimer.classList.remove('hidden');
    
    state.recordingSeconds = 0;
    recordingTimer.textContent = "00:00";
    state.recordingInterval = setInterval(() => {
      state.recordingSeconds++;
      const mins = String(Math.floor(state.recordingSeconds / 60)).padStart(2, '0');
      const secs = String(state.recordingSeconds % 60).padStart(2, '0');
      recordingTimer.textContent = `${mins}:${secs}`;
    }, 1000);

  } catch (err) {
    state.isRecording = false;
    alert("মাইক্রোফোন অ্যাক্সেস করতে সমস্যা: " + err.message);
  }
}

function stopRecording() {
  state.isRecording = false;
  if (nativeRecognizer) {
    try { nativeRecognizer.stop(); } catch (e) {}
  }
  if (state.mediaRecorder && state.mediaRecorder.state === 'recording') {
    state.mediaRecorder.stop();
  }
  btnMic.classList.remove('recording');
  micStatusLabel.textContent = "অডিও রূপান্তর ও বিশ্লেষণ হচ্ছে...";
  clearInterval(state.recordingInterval);
  recordingTimer.classList.add('hidden');
}

async function sendVoiceMessage(blob, fallbackTranscript = '') {
  const formData = new FormData();
  formData.append('session_id', state.sessionId);
  formData.append('user_id', state.currentUser.user_id);
  formData.append('voice', ttsVoiceSelect ? ttsVoiceSelect.value : 'bn-BD-NabanitaNeural');
  formData.append('style', voiceStyleSelect ? voiceStyleSelect.value : 'expressive');
  if (fallbackTranscript) {
    formData.append('native_transcript', fallbackTranscript);
  }
  formData.append('audio_file', blob, 'recording.webm');

  try {
    sessionStatusText.textContent = "ভয়েস রূপান্তর ও বিশ্লেষণ হচ্ছে...";
    const res = await fetch('/api/session/voice-chat', {
      method: 'POST',
      body: formData
    });
    const data = await res.json();

    micStatusLabel.textContent = "কথা বলতে মাইক বাটনে ক্লিক করুন";
    sessionStatusText.textContent = data.session_active ? "সেশন চলমান..." : "সেশন সমাপ্ত।";

    // Update live speech preview with the transcribed Bengali text
    if (data.user_transcript) {
      liveSpeechText.textContent = `"${data.user_transcript}"`;
      sttEngineBadge.textContent = "রূপান্তর সম্পন্ন";
    }

    // Show transcribed user speech
    appendUserMessage(data.user_transcript || "[ভয়েস রিকগনিশন]");
    // Show AI reply
    appendAIMessage(data.ai_message, data.audio_url);

    if (data.audio_url) {
      playAudio(data.audio_url);
    }

    updateConsentBadge(data.consent_status);
    state.sessionActive = data.session_active;
    btnEndSession.disabled = !data.session_active;

    if (data.consent_status === 'pending') {
      consentPromptActions.classList.remove('hidden');
    }
  } catch (e) {
    micStatusLabel.textContent = "কথা বলতে মাইক বাটনে ক্লিক করুন";
    alert("ভয়েস প্রক্রিয়াকরণে ত্রুটি: " + e.message);
  }
}

async function endCurrentSession() {
  if (!state.sessionId) return;

  btnEndSession.disabled = true;
  sessionStatusText.textContent = "রুব্রিক ডিস্ট্রেস যাচাই ও মেমোরি আপডেট হচ্ছে...";

  try {
    const res = await fetch('/api/session/end', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: state.sessionId,
        user_id: state.currentUser.user_id
      })
    });
    const data = await res.json();

    sessionDot.className = "dot dot-idle";
    sessionStatusText.textContent = "সেশন সমাপ্ত হয়েছে।";
    btnStartSession.disabled = false;

    // Display Distress Evaluation in Alert Drawer
    const evalData = data.distress_eval;
    lastEvaluationCard.classList.remove('hidden');
    if (evalData.flagged) {
      evalFlagPill.className = "status-pill status-flagged";
      evalFlagPill.textContent = "🚨 ডিস্ট্রেস ফ্ল্যাগড (FLAGGED)";
    } else {
      evalFlagPill.className = "status-pill status-consented";
      evalFlagPill.textContent = "✅ স্বাভাবিক (CALM / NO DISTRESS)";
    }
    evalRuleName.textContent = evalData.matched_rule;
    evalReason.textContent = evalData.reason;
    evalSmsText.textContent = evalData.flagged
      ? `"Care Alert from 'Are You Okay?': Your ${state.currentUser.kin_relation || 'parent'}'s recent check-in showed signs that ${evalData.reason}. Consider calling today."`
      : "কোনো অ্যালার্ট প্রেরণের প্রয়োজন নেই। পরিস্থিতি স্বাভাবিক রয়েছে।";

    // Update memory view
    if (data.updated_memory) {
      updateMemoryView(data.updated_memory);
      appendSystemMessage(`📝 নতুন মেমোরি সংরক্ষিত হয়েছে: "${data.updated_memory}"`);
    }

    appendSystemMessage(`🏁 সেশন সম্পন্ন হয়েছে। রুব্রিক ফলাফল: ${evalData.flagged ? '🚨 ফ্ল্যাগড' : '✅ শান্ত'}`);

    // Refresh alerts list
    await loadAlerts();

  } catch (e) {
    alert("সেশন সমাপ্ত করতে ত্রুটি: " + e.message);
    btnEndSession.disabled = false;
  }
}

async function loadAlerts() {
  try {
    const res = await fetch('/api/alerts');
    const data = await res.json();
    const alerts = data.alerts || [];

    alertCounter.textContent = `${alerts.length} Alerts`;
    if (alerts.length === 0) {
      alertsFeed.innerHTML = '<div class="empty-state">কোনো সতর্কবার্তা পাওয়া যায়নি।</div>';
      return;
    }

    alertsFeed.innerHTML = '';
    alerts.forEach(a => {
      const item = document.createElement('div');
      item.className = 'alert-item';
      item.innerHTML = `
        <div class="alert-item-time">🕒 ${new Date(a.timestamp).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})} • ${a.user_name || 'অভিভাবক'}</div>
        <div class="alert-item-rule">${a.matched_rule}</div>
        <p style="font-size:0.8rem; margin: 4px 0;">${a.reason}</p>
        <div style="font-size:0.75rem; color:#475569; font-style:italic;">"${a.sms_text}"</div>
      `;
      alertsFeed.appendChild(item);
    });
  } catch (e) {
    console.error("Alerts loading error:", e);
  }
}

function appendAIMessage(text, audioUrl) {
  const msg = document.createElement('div');
  msg.className = 'message-bubble msg-ai';
  
  let audioBtnHtml = '';
  if (audioUrl) {
    audioBtnHtml = `<button class="msg-audio-btn" onclick="playAudio('${audioUrl}')">🔊 শুনুন</button>`;
  }

  msg.innerHTML = `
    <div class="sender-label">
      <span>🤖 আর ইউ ওকে? (AI Caregiver)</span>
      ${audioBtnHtml}
    </div>
    <div>${escapeHtml(text)}</div>
  `;
  chatMessages.appendChild(msg);
  scrollToBottom();
}

function appendUserMessage(text) {
  const msg = document.createElement('div');
  msg.className = 'message-bubble msg-user';
  msg.innerHTML = `
    <div class="sender-label">👤 ${escapeHtml(state.currentUser ? state.currentUser.name : 'অভিভাবক')}</div>
    <div>${escapeHtml(text)}</div>
  `;
  chatMessages.appendChild(msg);
  scrollToBottom();
}

function appendSystemMessage(text) {
  const msg = document.createElement('div');
  msg.className = 'message-bubble system-note';
  msg.textContent = text;
  chatMessages.appendChild(msg);
  scrollToBottom();
}

function scrollToBottom() {
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function playAudio(url) {
  if (!url) return;
  ttsAudioPlayer.src = url;
  audioPlayingIndicator.classList.remove('hidden');
  ttsAudioPlayer.play().catch(e => {
    console.warn("Audio autoplay blocked by browser policy:", e);
  });
  ttsAudioPlayer.onended = () => {
    audioPlayingIndicator.classList.add('hidden');
  };
}

// Global scope helper for inline onclick
window.playAudio = playAudio;

function escapeHtml(string) {
  const div = document.createElement('div');
  div.innerText = string;
  return div.innerHTML;
}
