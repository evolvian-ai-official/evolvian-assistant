import { useEffect, useState, useRef } from "react";
import { useParams } from "react-router-dom";
import "./evoin-tokens.css";

const API = import.meta.env.VITE_API_URL || "http://localhost:8001";

const SCREENS = { WELCOME: "welcome", QUESTION: "question", DONE: "done", ERROR: "error" };

export default function ParticipantFlow() {
  const { id: interviewId } = useParams();
  const [screen, setScreen] = useState(SCREENS.WELCOME);
  const [interview, setInterview] = useState(null);
  const [sessionId, setSessionId] = useState(null);
  const [questionIndex, setQuestionIndex] = useState(0);
  const [answer, setAnswer] = useState("");
  const [followupMsg, setFollowupMsg] = useState(null);
  const [isFollowup, setIsFollowup] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [welcomeMsg, setWelcomeMsg] = useState("");
  const [recording, setRecording] = useState(false);
  const recognitionRef = useRef(null);
  const [contactName, setContactName] = useState("");
  const [contactEmail, setContactEmail] = useState("");
  const [contactSent, setContactSent] = useState(false);
  const [sendingContact, setSendingContact] = useState(false);

  useEffect(() => {
    fetch(`${API}/api/evoin/public/interviews/${interviewId}`)
      .then(r => {
        if (!r.ok) throw new Error("not found");
        return r.json();
      })
      .then(d => {
        setInterview(d);
        // Restore session from localStorage if exists
        const saved = localStorage.getItem(`evoin_session_${interviewId}`);
        if (saved) {
          const { sessionId: sid, qIndex } = JSON.parse(saved);
          setSessionId(sid);
          setQuestionIndex(qIndex);
          setScreen(SCREENS.QUESTION);
        }
      })
      .catch(() => setScreen(SCREENS.ERROR));
  }, [interviewId]);

  async function startSession() {
    const res = await fetch(`${API}/api/evoin/sessions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ interview_id: interviewId }),
    });
    const d = await res.json();
    const sid = d.session.id;
    setSessionId(sid);
    localStorage.setItem(`evoin_session_${interviewId}`, JSON.stringify({ sessionId: sid, qIndex: 0 }));
    setScreen(SCREENS.QUESTION);
  }

  async function submitAnswer() {
    if (!answer.trim() || submitting) return;
    setSubmitting(true);
    const q = interview.questions[questionIndex];

    try {
      const res = await fetch(`${API}/api/evoin/sessions/${sessionId}/respond`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question_id: q.id,
          question_text: isFollowup ? followupMsg : q.text,
          answer: answer.trim(),
          is_followup: isFollowup,
        }),
      });
      const d = await res.json();
      setAnswer("");

      if (d.action === "deepen" && !isFollowup) {
        setFollowupMsg(d.message);
        setIsFollowup(true);
      } else {
        // Advance to next question
        setIsFollowup(false);
        setFollowupMsg(null);
        const nextIdx = questionIndex + 1;
        if (nextIdx >= interview.questions.length) {
          // Complete session
          await fetch(`${API}/api/evoin/sessions/${sessionId}/complete`, { method: "POST" });
          localStorage.removeItem(`evoin_session_${interviewId}`);
          setScreen(SCREENS.DONE);
        } else {
          setQuestionIndex(nextIdx);
          localStorage.setItem(`evoin_session_${interviewId}`, JSON.stringify({ sessionId, qIndex: nextIdx }));
        }
      }
    } finally {
      setSubmitting(false);
    }
  }

  async function submitContact() {
    if (sendingContact) return;
    setSendingContact(true);
    try {
      await fetch(`${API}/api/evoin/sessions/${sessionId}/complete`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          participant_name: contactName.trim() || null,
          participant_email: contactEmail.trim() || null,
        }),
      });
    } finally {
      setSendingContact(false);
      setContactSent(true);
    }
  }

  function toggleVoice() {
    if (!("webkitSpeechRecognition" in window) && !("SpeechRecognition" in window)) {
      alert("Tu navegador no soporta dictado por voz. Usa Chrome para esta función.");
      return;
    }
    if (recording) {
      recognitionRef.current?.stop();
      setRecording(false);
      return;
    }
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    const r = new SR();
    r.lang = "es-MX";
    r.continuous = false;
    r.interimResults = false;
    r.onresult = e => setAnswer(prev => prev + " " + e.results[0][0].transcript);
    r.onend = () => setRecording(false);
    r.start();
    recognitionRef.current = r;
    setRecording(true);
  }

  const totalQ = interview?.questions?.length || 0;
  const currentQ = interview?.questions?.[questionIndex];
  const progress = totalQ > 0 ? ((questionIndex) / totalQ) * 100 : 0;

  // --- WELCOME ---
  if (screen === SCREENS.WELCOME && interview) {
    const msg = welcomeMsg || (interview.segment ? `Un fundador quiere entender tu día a día como ${interview.segment}. Son ${totalQ} preguntas, sin respuestas correctas.` : "");
    return (
      <MobileShell>
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", textAlign: "center", flex: 1, padding: "24px 20px" }}>
          <div style={{ width: 52, height: 52, borderRadius: "50%", background: "var(--ei-blue-50)", display: "flex", alignItems: "center", justifyContent: "center", marginBottom: 20 }}>
            <ChatIcon />
          </div>
          <h2 style={{ fontSize: 18, fontWeight: 700, color: "var(--ei-text)", marginBottom: 10 }}>Tu opinión nos ayuda</h2>
          <p style={{ fontSize: 13, color: "var(--ei-text-2)", lineHeight: 1.65, marginBottom: 22, maxWidth: 260 }}>{msg}</p>
          <div style={{ display: "flex", gap: 8, justifyContent: "center", marginBottom: 24, flexWrap: "wrap" }}>
            <Pill icon={<ClockIcon />} label={`~${Math.round(totalQ * 2)} min`} />
            <Pill icon={<LockIcon />} label="Anónimo" />
          </div>
          <button onClick={startSession} style={btnPrimaryStyle}>Comenzar →</button>
        </div>
      </MobileShell>
    );
  }

  // --- QUESTION ---
  if (screen === SCREENS.QUESTION && currentQ) {
    const displayQ = isFollowup ? followupMsg : currentQ.text;
    return (
      <MobileShell>
        <div style={{ display: "flex", flexDirection: "column", flex: 1, padding: "18px 18px 22px" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <span style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--ei-green-600)", display: "inline-block" }} />
              <span style={{ fontSize: 11, color: "var(--ei-text-3)", fontWeight: 700, letterSpacing: ".06em" }}>DISCOVERY</span>
            </div>
            <span style={{ fontSize: 11, color: "var(--ei-text-3)" }}>{questionIndex + 1} / {totalQ}</span>
          </div>

          {/* Progress */}
          <div style={{ height: 4, background: "var(--ei-border)", borderRadius: 3, marginBottom: 22, overflow: "hidden" }}>
            <div style={{ height: "100%", width: `${progress}%`, background: "var(--ei-text)", borderRadius: 3, transition: "width .3s" }} />
          </div>

          {isFollowup && (
            <div style={{ fontSize: 11, color: "var(--ei-blue-800)", background: "var(--ei-blue-50)", padding: "6px 10px", borderRadius: "var(--ei-radius-sm)", marginBottom: 10, fontWeight: 600 }}>
              Pregunta de profundización
            </div>
          )}

          <p style={{ fontSize: 16, fontWeight: 600, color: "var(--ei-text)", lineHeight: 1.45, marginBottom: 16, flex: 0 }}>{displayQ}</p>

          <textarea
            value={answer}
            onChange={e => setAnswer(e.target.value)}
            placeholder="Escribe o usa el micrófono..."
            rows={4}
            style={{ ...textareaStyle, flex: 1, minHeight: 90 }}
          />

          <div style={{ display: "flex", alignItems: "center", gap: 10, marginTop: 10, marginBottom: 14 }}>
            <button
              onClick={toggleVoice}
              style={{
                width: 40, height: 40, borderRadius: "50%",
                background: recording ? "var(--ei-coral-600)" : "var(--ei-text)",
                border: "none", cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
              }}
            >
              <MicIcon />
            </button>
            <span style={{ fontSize: 11, color: "var(--ei-text-3)" }}>{recording ? "Grabando — toca para detener" : "Mantén presionado para hablar"}</span>
          </div>

          <button
            onClick={submitAnswer}
            disabled={submitting || !answer.trim()}
            style={{ ...btnPrimaryStyle, opacity: (!answer.trim() || submitting) ? .5 : 1 }}
          >
            {submitting ? "Procesando..." : "Continuar →"}
          </button>
        </div>
      </MobileShell>
    );
  }

  // --- DONE ---
  if (screen === SCREENS.DONE) {
    return (
      <MobileShell>
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", textAlign: "center", flex: 1, padding: "24px 20px" }}>
          <div style={{ width: 56, height: 56, borderRadius: "50%", background: "var(--ei-green-50)", display: "flex", alignItems: "center", justifyContent: "center", marginBottom: 20 }}>
            <CheckIcon />
          </div>
          <h2 style={{ fontSize: 18, fontWeight: 700, color: "var(--ei-text)", marginBottom: 10 }}>¡Listo, gracias!</h2>
          <p style={{ fontSize: 13, color: "var(--ei-text-2)", lineHeight: 1.65, marginBottom: 22, maxWidth: 250 }}>
            Tus respuestas ya fueron enviadas. Esto ayuda a construir mejores soluciones.
          </p>

          {!contactSent ? (
            <div style={{ width: "100%", maxWidth: 260, textAlign: "left", marginBottom: 22 }}>
              <p style={{ fontSize: 12, color: "var(--ei-text-3)", marginBottom: 10, textAlign: "center" }}>
                ¿Quieres que te avisemos cuando lancemos? (opcional)
              </p>
              <input
                type="text"
                value={contactName}
                onChange={e => setContactName(e.target.value)}
                placeholder="Tu nombre (opcional)"
                style={{ ...textareaStyle, marginBottom: 8 }}
              />
              <input
                type="email"
                value={contactEmail}
                onChange={e => setContactEmail(e.target.value)}
                placeholder="Tu email (opcional)"
                style={{ ...textareaStyle, marginBottom: 12 }}
              />
              <div style={{ display: "flex", gap: 8 }}>
                <button
                  onClick={() => setContactSent(true)}
                  style={{ ...btnPrimaryStyle, background: "var(--ei-surface-2)", color: "var(--ei-text-2)", border: "1px solid var(--ei-border)" }}
                >
                  Omitir
                </button>
                <button
                  onClick={submitContact}
                  disabled={sendingContact || (!contactName.trim() && !contactEmail.trim())}
                  style={{ ...btnPrimaryStyle, opacity: (sendingContact || (!contactName.trim() && !contactEmail.trim())) ? .5 : 1 }}
                >
                  {sendingContact ? "Enviando..." : "Enviar"}
                </button>
              </div>
            </div>
          ) : (
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <ShieldIcon />
              <span style={{ fontSize: 11, color: "var(--ei-text-3)" }}>Tus datos no se comparten con terceros</span>
            </div>
          )}
        </div>
      </MobileShell>
    );
  }

  // --- ERROR ---
  if (screen === SCREENS.ERROR) {
    return (
      <MobileShell>
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", textAlign: "center", flex: 1, padding: 24 }}>
          <p style={{ fontSize: 15, fontWeight: 600, color: "var(--ei-text)", marginBottom: 8 }}>Este link no está disponible</p>
          <p style={{ fontSize: 13, color: "var(--ei-text-3)" }}>La entrevista pudo haber expirado o el link es incorrecto.</p>
        </div>
      </MobileShell>
    );
  }

  return <div style={{ padding: 40, textAlign: "center", color: "var(--ei-text-3)", fontFamily: "inherit" }}>Cargando...</div>;
}

function MobileShell({ children }) {
  return (
    <div style={{
      minHeight: "100vh", background: "var(--ei-surface-2)",
      display: "flex", alignItems: "center", justifyContent: "center",
      fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
      padding: "16px",
    }}>
      <div style={{
        width: "100%", maxWidth: 380, background: "var(--ei-surface)",
        borderRadius: 24, border: "1px solid var(--ei-border)",
        minHeight: 520, display: "flex", flexDirection: "column",
        boxShadow: "0 2px 12px rgba(0,0,0,.06)",
      }}>
        {children}
      </div>
    </div>
  );
}

function Pill({ icon, label }) {
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 5, fontSize: 11, color: "var(--ei-text-2)", border: "1px solid var(--ei-border)", borderRadius: 20, padding: "5px 12px" }}>
      {icon}{label}
    </span>
  );
}

const btnPrimaryStyle = {
  width: "100%", background: "var(--ei-text)", color: "#fff",
  border: "none", borderRadius: "var(--ei-radius-sm)",
  padding: "13px", fontSize: 14, fontWeight: 700, cursor: "pointer",
  fontFamily: "inherit",
};

const textareaStyle = {
  width: "100%", background: "var(--ei-surface-2)", border: "1px solid var(--ei-border)",
  borderRadius: "var(--ei-radius-sm)", padding: "12px 14px", fontSize: 14,
  color: "var(--ei-text)", fontFamily: "inherit", resize: "none", boxSizing: "border-box",
};

function ChatIcon() {
  return <svg width="22" height="22" fill="none" stroke="#185FA5" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/></svg>;
}
function ClockIcon() {
  return <svg width="12" height="12" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>;
}
function LockIcon() {
  return <svg width="12" height="12" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>;
}
function MicIcon() {
  return <svg width="16" height="16" fill="none" stroke="#fff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/></svg>;
}
function CheckIcon() {
  return <svg width="24" height="24" fill="none" stroke="#3B6D11" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12"/></svg>;
}
function ShieldIcon() {
  return <svg width="13" height="13" fill="none" stroke="#A3A199" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>;
}
