import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useClientId } from "../../../hooks/useClientId";
import { authFetch } from "../../../lib/authFetch";

const API = import.meta.env.VITE_API_URL || "http://localhost:8001";

const DEPTH_OPTIONS = [
  { value: 6,  label: "Exploratoria", time: "~10 min" },
  { value: 10, label: "Estándar",     time: "~20 min" },
  { value: 15, label: "Profunda",     time: "~30 min" },
];

export default function EvoInHub() {
  const clientId = useClientId();
  const navigate = useNavigate();

  // Setup form state
  const [hypothesis, setHypothesis] = useState("");
  const [segment, setSegment]       = useState("");
  const [depth, setDepth]           = useState(10);
  const [creating, setCreating]     = useState(false);
  const [createError, setCreateError] = useState(null);

  // Interview list state
  const [interviews, setInterviews] = useState([]);
  const [loadingList, setLoadingList] = useState(true);
  const [copied, setCopied] = useState(null);

  const shareBase = `${window.location.origin.replace(
    window.location.port ? `:${window.location.port}` : "",
    ":5173"
  )}/i/`;

  useEffect(() => {
    if (!clientId) return;
    loadInterviews();
  }, [clientId]);

  async function loadInterviews() {
    setLoadingList(true);
    try {
      const res = await authFetch(`${API}/api/evoin/interviews?founder_token=${clientId}`);
      const d = await res.json();
      setInterviews(d.interviews || []);
    } finally {
      setLoadingList(false);
    }
  }

  async function handleCreate(e) {
    e.preventDefault();
    if (!hypothesis.trim() || !segment.trim()) return;
    setCreating(true);
    setCreateError(null);
    try {
      const res = await authFetch(`${API}/api/evoin/interviews`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ hypothesis, segment, depth, founder_token: clientId }),
      });
      if (!res.ok) throw new Error("Error al crear la entrevista");
      setHypothesis("");
      setSegment("");
      setDepth(10);
      await loadInterviews();
    } catch (err) {
      setCreateError(err.message);
    } finally {
      setCreating(false);
    }
  }

  function copyLink(interviewId) {
    const url = `${shareBase}${interviewId}`;
    navigator.clipboard.writeText(url);
    setCopied(interviewId);
    setTimeout(() => setCopied(null), 2000);
  }

  function completedCount(iv) {
    return (iv.evoin_sessions || []).filter(s => s.completed_at).length;
  }

  return (
    <div style={{ padding: "2rem", maxWidth: 860, margin: "0 auto", fontFamily: "Inter, system-ui, sans-serif" }}>

      {/* Header */}
      <div style={{ marginBottom: "2rem" }}>
        <div style={{ display: "inline-flex", alignItems: "center", gap: 6, background: "#EAF3DE", color: "#27500A", fontSize: 12, fontWeight: 700, padding: "4px 12px", borderRadius: 20, marginBottom: 10 }}>
          <span style={{ width: 6, height: 6, borderRadius: "50%", background: "#3B6D11", display: "inline-block" }} />
          EvoIn · Discovery Agent · Premium
        </div>
        <h1 style={{ fontSize: 22, fontWeight: 700, color: "#1F1E1B", marginBottom: 4 }}>Entrevistas de product discovery</h1>
        <p style={{ fontSize: 14, color: "#6B6A63", lineHeight: 1.5 }}>
          Conduce entrevistas Mom Test de forma asíncrona. Comparte un link con tu segmento y la IA detecta patrones, pains y señales de compra.
        </p>
      </div>

      {/* Two-column layout */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20, alignItems: "start" }}>

        {/* LEFT — Create form */}
        <div>
          <h2 style={sectionTitle}>Nueva entrevista</h2>
          <form onSubmit={handleCreate}>
            <div style={card}>
              <div style={fieldLabel}>Hipótesis de producto</div>
              <textarea
                value={hypothesis}
                onChange={e => setHypothesis(e.target.value)}
                placeholder="Ej: Los doctores pierden demasiado tiempo respondiendo mensajes de pacientes..."
                rows={3}
                required
                style={textarea}
              />
              <div style={{ ...fieldLabel, marginTop: 14 }}>Segmento a entrevistar</div>
              <input
                value={segment}
                onChange={e => setSegment(e.target.value)}
                placeholder="Ej: Doctores particulares, dueños de clínicas"
                required
                style={input}
              />
            </div>

            <div style={card}>
              <div style={fieldLabel}>Profundidad</div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8 }}>
                {DEPTH_OPTIONS.map(opt => (
                  <button
                    type="button"
                    key={opt.value}
                    onClick={() => setDepth(opt.value)}
                    style={{
                      border: `1.5px solid ${depth === opt.value ? "#1F1E1B" : "#E4E2D9"}`,
                      borderRadius: 8,
                      padding: "12px 8px",
                      textAlign: "center",
                      background: depth === opt.value ? "#fff" : "#F3F2ED",
                      cursor: "pointer",
                      fontFamily: "inherit",
                    }}
                  >
                    <span style={{ fontSize: 20, fontWeight: 700, display: "block", color: "#1F1E1B" }}>{opt.value}</span>
                    <span style={{ fontSize: 11, color: depth === opt.value ? "#1F1E1B" : "#6B6A63", fontWeight: depth === opt.value ? 700 : 400 }}>{opt.label}</span>
                    <span style={{ fontSize: 10, color: "#A3A199", display: "block" }}>{opt.time}</span>
                  </button>
                ))}
              </div>
            </div>

            {createError && (
              <div style={{ background: "#FAECE7", border: "1px solid #993C1D", borderRadius: 8, padding: "10px 14px", fontSize: 13, color: "#712B13", marginBottom: 12 }}>
                {createError}
              </div>
            )}

            <button
              type="submit"
              disabled={creating || !hypothesis.trim() || !segment.trim()}
              style={{ ...btnPrimary, opacity: (creating || !hypothesis.trim() || !segment.trim()) ? .5 : 1 }}
            >
              {creating ? "Generando preguntas..." : "Generar entrevista →"}
            </button>
          </form>
        </div>

        {/* RIGHT — Interview list */}
        <div>
          <h2 style={sectionTitle}>Tus entrevistas</h2>
          {loadingList && <p style={{ color: "#A3A199", fontSize: 13 }}>Cargando...</p>}
          {!loadingList && interviews.length === 0 && (
            <div style={{ ...card, textAlign: "center", color: "#A3A199", fontSize: 13, padding: "32px 20px" }}>
              Crea tu primera entrevista para empezar.
            </div>
          )}
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {interviews.map(iv => {
              const done = completedCount(iv);
              const total = (iv.evoin_sessions || []).length;
              return (
                <div key={iv.id} style={card}>
                  <p style={{ fontSize: 12, color: "#A3A199", marginBottom: 3 }}>{iv.segment}</p>
                  <p style={{ fontSize: 14, fontWeight: 600, color: "#1F1E1B", lineHeight: 1.4, marginBottom: 10 }}>{iv.hypothesis}</p>
                  <div style={{ display: "flex", gap: 6, marginBottom: 10, flexWrap: "wrap" }}>
                    <span style={{ fontSize: 11, background: "#EAF3DE", color: "#27500A", fontWeight: 700, padding: "3px 10px", borderRadius: 20 }}>
                      {done} completa{done !== 1 ? "s" : ""} / {total} iniciada{total !== 1 ? "s" : ""}
                    </span>
                    <span style={{ fontSize: 11, color: "#A3A199" }}>{iv.depth} preguntas</span>
                  </div>
                  <div style={{ display: "flex", gap: 8 }}>
                    <button
                      onClick={() => copyLink(iv.id)}
                      style={{ ...btnSecondary, flex: 1 }}
                    >
                      {copied === iv.id ? "¡Copiado!" : "Copiar link"}
                    </button>
                    <button
                      onClick={() => navigate(`/services/evoin/${iv.id}`)}
                      style={{ ...btnPrimary, flex: 1, padding: "8px 12px", fontSize: 12 }}
                    >
                      Ver insights →
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}

const sectionTitle = { fontSize: 14, fontWeight: 700, color: "#6B6A63", textTransform: "uppercase", letterSpacing: ".06em", marginBottom: 12 };
const card = { background: "#fff", border: "1px solid #E4E2D9", borderRadius: 12, padding: "18px 20px", marginBottom: 10 };
const fieldLabel = { fontSize: 11, fontWeight: 700, color: "#A3A199", textTransform: "uppercase", letterSpacing: ".07em", marginBottom: 8 };
const textarea = { width: "100%", background: "#F3F2ED", border: "1px solid #E4E2D9", borderRadius: 8, padding: "11px 13px", fontSize: 14, color: "#1F1E1B", fontFamily: "inherit", resize: "none", boxSizing: "border-box" };
const input   = { width: "100%", background: "#F3F2ED", border: "1px solid #E4E2D9", borderRadius: 8, padding: "11px 13px", fontSize: 14, color: "#1F1E1B", fontFamily: "inherit", boxSizing: "border-box" };
const btnPrimary   = { width: "100%", background: "#1F1E1B", color: "#fff", border: "none", borderRadius: 8, padding: "12px 16px", fontSize: 13, fontWeight: 700, cursor: "pointer", fontFamily: "inherit" };
const btnSecondary = { background: "#F3F2ED", color: "#1F1E1B", border: "1px solid #E4E2D9", borderRadius: 8, padding: "8px 12px", fontSize: 12, fontWeight: 600, cursor: "pointer", fontFamily: "inherit" };
