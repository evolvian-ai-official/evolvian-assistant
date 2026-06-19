import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useClientId } from "../../../hooks/useClientId";
import { authFetch } from "../../../lib/authFetch";

const API = import.meta.env.VITE_API_URL || "http://localhost:8001";

const SIGNAL_STYLES = {
  pain:  { bg: "#FAECE7", color: "#712B13", emoji: "🔴", label: "Pain real" },
  job:   { bg: "#EAF3DE", color: "#27500A", emoji: "✅", label: "Job-to-be-done" },
  buy:   { bg: "#E6F1FB", color: "#0C447C", emoji: "💡", label: "Señal de compra" },
  quote: { bg: "#EEEDFE", color: "#3C3489", emoji: "💬", label: "Quote clave" },
  warn:  { bg: "#FAEEDA", color: "#633806", emoji: "⚠️", label: "Alerta" },
};

const HYPOTHESIS_STATUS = {
  validates:   { bg: "#EAF3DE", color: "#27500A", label: "Hipótesis validada ✓" },
  validated:   { bg: "#EAF3DE", color: "#27500A", label: "Hipótesis validada ✓" },
  invalidates: { bg: "#FAECE7", color: "#712B13", label: "Hipótesis invalidada" },
  invalidated: { bg: "#FAECE7", color: "#712B13", label: "Hipótesis invalidada" },
  pivot_needed:{ bg: "#FAEEDA", color: "#633806", label: "Hipótesis requiere pivote" },
};

export default function EvoInDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const clientId = useClientId();

  const [data, setData]             = useState(null);
  const [loading, setLoading]       = useState(true);
  const [analyzing, setAnalyzing]   = useState(false);
  const [expandedSession, setExpandedSession] = useState(null);
  const [copied, setCopied]         = useState(false);

  useEffect(() => {
    if (!clientId) return;
    authFetch(`${API}/api/evoin/interviews/${id}?founder_token=${clientId}`)
      .then(r => r.json())
      .then(d => { setData(d); setLoading(false); })
      .catch(() => setLoading(false));
  }, [id, clientId]);

  async function runAggregate() {
    setAnalyzing(true);
    try {
      const res = await authFetch(
        `${API}/api/evoin/interviews/${id}/analyze?founder_token=${clientId}`,
        { method: "POST" }
      );
      const d = await res.json();
      if (res.ok) setData(prev => ({ ...prev, analyses: [d.analysis, ...(prev.analyses || [])] }));
    } finally {
      setAnalyzing(false);
    }
  }

  function copyLink() {
    const base = window.location.origin.replace(
      window.location.port ? `:${window.location.port}` : "",
      ":5173"
    );
    navigator.clipboard.writeText(`${base}/i/${id}`);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  if (loading) return <div style={{ padding: 40, color: "#A3A199", fontFamily: "Inter, system-ui, sans-serif" }}>Cargando...</div>;
  if (!data) return null;

  const { interview, sessions = [], analyses = [] } = data;
  const completed   = sessions.filter(s => s.completed_at);
  const aggregate   = analyses.find(a => a.type === "aggregate");
  const individual  = analyses.filter(a => a.type === "individual");

  return (
    <div style={{ padding: "2rem", maxWidth: 860, margin: "0 auto", fontFamily: "Inter, system-ui, sans-serif" }}>

      {/* Back + header */}
      <button onClick={() => navigate("/services/evoin")} style={{ background: "none", border: "none", cursor: "pointer", color: "#6B6A63", fontSize: 13, marginBottom: 20, padding: 0, fontFamily: "inherit" }}>
        ← Volver a EvoIn
      </button>

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: 12, marginBottom: 24 }}>
        <div>
          <div style={{ fontSize: 12, background: "#EAF3DE", color: "#27500A", fontWeight: 700, padding: "4px 12px", borderRadius: 20, marginBottom: 10, display: "inline-block" }}>
            {completed.length} entrevista{completed.length !== 1 ? "s" : ""} completada{completed.length !== 1 ? "s" : ""}
          </div>
          <h2 style={{ fontSize: 20, fontWeight: 700, color: "#1F1E1B", marginBottom: 4 }}>{interview.segment}</h2>
          <p style={{ fontSize: 13, color: "#6B6A63", maxWidth: 500, lineHeight: 1.5 }}>{interview.hypothesis}</p>
        </div>
        <div style={{ display: "flex", gap: 8, flexShrink: 0 }}>
          <button onClick={copyLink} style={btnSecondary}>{copied ? "¡Copiado!" : "Copiar link"}</button>
          {completed.length >= 2 && (
            <button onClick={runAggregate} disabled={analyzing} style={{ ...btnPrimary, opacity: analyzing ? .5 : 1 }}>
              {analyzing ? "Analizando..." : "Analizar todo →"}
            </button>
          )}
        </div>
      </div>

      {/* Stats */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))", gap: 10, marginBottom: 20 }}>
        {[
          { label: "Entrevistas", value: `${completed.length} / ${sessions.length}` },
          aggregate && { label: "Pain confirmado", value: `${aggregate.result.pain_confirmed_count ?? "—"} / ${completed.length}`, color: "#712B13" },
          aggregate && { label: "Ya pagan", value: `${aggregate.result.already_paying_count ?? "—"} / ${completed.length}`, color: "#27500A" },
          aggregate?.result.avg_spend && { label: "Gasto promedio", value: aggregate.result.avg_spend },
        ].filter(Boolean).map((s, i) => (
          <div key={i} style={{ background: "#F3F2ED", borderRadius: 8, padding: "14px 16px" }}>
            <div style={{ fontSize: 10, color: "#A3A199", fontWeight: 700, textTransform: "uppercase", letterSpacing: ".05em", marginBottom: 6 }}>{s.label}</div>
            <div style={{ fontSize: 20, fontWeight: 700, color: s.color || "#1F1E1B" }}>{s.value}</div>
          </div>
        ))}
      </div>

      {/* Aggregate analysis */}
      {aggregate && (
        <div style={{ ...card, marginBottom: 14 }}>
          <div style={sectionLabel}>Análisis agregado · IA</div>

          {(() => {
            const s = HYPOTHESIS_STATUS[aggregate.result.hypothesis_status] || HYPOTHESIS_STATUS.pivot_needed;
            return (
              <div style={{ background: s.bg, borderRadius: 8, padding: "12px 16px", marginBottom: 16 }}>
                <div style={{ fontSize: 13, fontWeight: 700, color: s.color, marginBottom: 4 }}>{s.label}</div>
                <div style={{ fontSize: 13, color: s.color, lineHeight: 1.55 }}>{aggregate.result.hypothesis_evidence}</div>
                {aggregate.result.pivot_suggestion && (
                  <div style={{ fontSize: 12, color: s.color, marginTop: 6, opacity: .85 }}>Pivote sugerido: {aggregate.result.pivot_suggestion}</div>
                )}
              </div>
            );
          })()}

          <div style={{ marginBottom: 14 }}>
            <div style={sectionLabel}>Señales detectadas</div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
              {(aggregate.result.patterns || []).map((p, i) => {
                const st = SIGNAL_STYLES[p.signal_type] || SIGNAL_STYLES.warn;
                return (
                  <span key={i} style={{ background: st.bg, color: st.color, fontSize: 12, fontWeight: 600, padding: "5px 12px", borderRadius: 20 }}>
                    {st.emoji} {p.text}{p.count ? ` (${p.count}/${p.total})` : ""}
                  </span>
                );
              })}
            </div>
          </div>

          {aggregate.result.wtp_estimate && (
            <div style={{ background: "#EAF3DE", borderRadius: 8, padding: "10px 14px", marginBottom: 14 }}>
              <div style={{ fontSize: 11, fontWeight: 700, color: "#27500A", marginBottom: 3 }}>Willingness to pay estimado</div>
              <div style={{ fontSize: 13, color: "#27500A" }}>{aggregate.result.wtp_estimate}</div>
            </div>
          )}

          {(aggregate.result.next_actions || []).length > 0 && (
            <div>
              <div style={sectionLabel}>Próximas acciones</div>
              {aggregate.result.next_actions.map((a, i) => (
                <div key={i} style={{ display: "flex", gap: 10, fontSize: 13, color: "#1F1E1B", lineHeight: 1.55, marginBottom: 8 }}>
                  <span style={{ width: 20, height: 20, borderRadius: "50%", background: "#F3F2ED", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 11, fontWeight: 700, color: "#6B6A63", flexShrink: 0 }}>{i + 1}</span>
                  {a}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* CTA to run aggregate */}
      {!aggregate && completed.length >= 2 && (
        <div style={{ background: "#E6F1FB", border: "1px solid #C5DCED", borderRadius: 12, padding: "16px 20px", textAlign: "center", marginBottom: 14 }}>
          <p style={{ fontSize: 13, color: "#0C447C", marginBottom: 10 }}>
            Tienes {completed.length} entrevistas completadas — ya puedes ver el análisis agregado de patrones y validación.
          </p>
          <button onClick={runAggregate} disabled={analyzing} style={{ background: "#0C447C", color: "#fff", border: "none", borderRadius: 8, padding: "10px 20px", fontSize: 13, fontWeight: 600, cursor: "pointer", fontFamily: "inherit" }}>
            {analyzing ? "Analizando..." : "Ver análisis agregado →"}
          </button>
        </div>
      )}

      {/* Sessions */}
      <div style={card}>
        <div style={sectionLabel}>Entrevistas ({sessions.length})</div>
        {sessions.length === 0 && (
          <p style={{ fontSize: 13, color: "#A3A199" }}>
            Aún no hay respuestas. Comparte el link con tu segmento.
          </p>
        )}
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {sessions.map((s, i) => {
            const ind = individual.find(a => a.session_id === s.id);
            const expanded = expandedSession === s.id;
            return (
              <div key={s.id}>
                <div
                  onClick={() => setExpandedSession(expanded ? null : s.id)}
                  style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "10px 12px", background: "#F3F2ED", borderRadius: 8, cursor: "pointer" }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <div style={{ width: 28, height: 28, borderRadius: "50%", background: "#EEEDFE", color: "#3C3489", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 11, fontWeight: 700 }}>
                      {String(i + 1).padStart(2, "0")}
                    </div>
                    <div>
                      <div style={{ fontSize: 13, fontWeight: 600, color: "#1F1E1B" }}>Entrevistado {i + 1}</div>
                      <div style={{ fontSize: 11, color: "#A3A199" }}>{(s.responses || []).length} respuestas</div>
                    </div>
                  </div>
                  <span style={{ fontSize: 11, fontWeight: 600, padding: "3px 10px", borderRadius: 20, background: s.completed_at ? "#EAF3DE" : "#FAEEDA", color: s.completed_at ? "#27500A" : "#633806" }}>
                    {s.completed_at ? "Completada" : "En progreso"}
                  </span>
                </div>

                {expanded && ind && (
                  <div style={{ background: "#fff", border: "1px solid #E4E2D9", borderRadius: 8, padding: 16, marginTop: 4 }}>
                    <p style={{ fontSize: 13, color: "#1F1E1B", lineHeight: 1.65, marginBottom: 12 }}>{ind.result.summary}</p>
                    <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 10 }}>
                      {(ind.result.signals || []).map((sig, j) => {
                        const st = SIGNAL_STYLES[sig.type] || SIGNAL_STYLES.warn;
                        return (
                          <span key={j} style={{ fontSize: 11, padding: "4px 10px", borderRadius: 20, background: st.bg, color: st.color, fontWeight: 600 }}>
                            {st.emoji} {sig.text}
                          </span>
                        );
                      })}
                    </div>
                    {ind.result.wtp_estimate && (
                      <p style={{ fontSize: 12, color: "#27500A", background: "#EAF3DE", padding: "8px 12px", borderRadius: 8 }}>
                        WTP estimado: {ind.result.wtp_estimate}
                      </p>
                    )}
                  </div>
                )}

                {expanded && !ind && s.completed_at && (
                  <div style={{ padding: "12px 16px", fontSize: 13, color: "#A3A199", background: "#F3F2ED", borderRadius: 8, marginTop: 4 }}>
                    Análisis individual en proceso...
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

const card         = { background: "#fff", border: "1px solid #E4E2D9", borderRadius: 12, padding: "18px 20px" };
const sectionLabel = { fontSize: 11, fontWeight: 700, color: "#A3A199", textTransform: "uppercase", letterSpacing: ".06em", marginBottom: 12 };
const btnPrimary   = { background: "#1F1E1B", color: "#fff", border: "none", borderRadius: 8, padding: "9px 16px", fontSize: 13, fontWeight: 600, cursor: "pointer", fontFamily: "inherit" };
const btnSecondary = { background: "#F3F2ED", color: "#1F1E1B", border: "1px solid #E4E2D9", borderRadius: 8, padding: "9px 16px", fontSize: 13, fontWeight: 600, cursor: "pointer", fontFamily: "inherit" };
