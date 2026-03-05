import { useEffect, useMemo, useState } from "react";
import { useClientId } from "../hooks/useClientId";
import { authFetch } from "../lib/authFetch";
import { useLanguage } from "../contexts/LanguageContext";
import "../components/ui/internal-admin-responsive.css";

const FILTER_OPTIONS = ["open", "prospects", "acknowledged", "resolved", "all"];

const prettyStatus = (value) => {
  const raw = String(value || "").trim().toLowerCase();
  if (raw === "prospects") return "Prospects";
  return raw
    .replace(/_/g, " ")
    .replace(/\b\w/g, (m) => m.toUpperCase());
};

const fmtDate = (value) => {
  if (!value) return "";
  try {
    return new Date(value).toLocaleString();
  } catch {
    return String(value);
  }
};

const channelLabel = (channel) => {
  const ch = String(channel || "").toLowerCase();
  if (ch === "whatsapp") return "WhatsApp";
  if (ch === "email" || ch === "gmail") return "Email";
  if (ch === "widget" || ch === "chat") return "Widget";
  return ch || "Unknown";
};

const normalizeChannel = (channel) => {
  const ch = String(channel || "").toLowerCase();
  if (ch === "gmail") return "email";
  if (ch === "chat") return "widget";
  return ch;
};

const getReplyChannelOptions = (handoff) => {
  const origin = normalizeChannel(handoff?.channel);
  const hasEmail = Boolean(String(handoff?.contact_email || "").trim());
  const hasPhone = Boolean(String(handoff?.contact_phone || "").trim());
  const options = [];

  if (hasEmail) options.push("email");
  if (hasPhone) options.push("whatsapp");

  if (options.length === 0 && (origin === "email" || origin === "whatsapp")) {
    options.push(origin);
  }

  return options;
};

const getDefaultReplyChannel = (handoff) => {
  const origin = normalizeChannel(handoff?.channel);
  const options = getReplyChannelOptions(handoff);
  if (origin === "email" && options.includes("email")) return "email";
  if (origin === "whatsapp" && options.includes("whatsapp")) return "whatsapp";
  if (options.includes("email")) return "email";
  if (options.includes("whatsapp")) return "whatsapp";
  return origin || "";
};

const resolveWhatsappTemplateLanguage = (handoff) => {
  const raw = String(handoff?.metadata?.language || "").trim().toLowerCase();
  return raw.startsWith("en") ? "en_US" : "es_MX";
};

const resolveWhatsappTemplateName = (languageCode) => {
  const normalized = String(languageCode || "").trim().toLowerCase();
  const shared = String(import.meta.env.VITE_WHATSAPP_HANDOFF_REPLY_TEMPLATE_NAME || "").trim();
  if (normalized.startsWith("en")) {
    return (
      String(import.meta.env.VITE_WHATSAPP_HANDOFF_REPLY_TEMPLATE_NAME_EN || "").trim() ||
      shared ||
      "human_handoff_followup_text_en"
    );
  }
  return (
    String(import.meta.env.VITE_WHATSAPP_HANDOFF_REPLY_TEMPLATE_NAME_ES || "").trim() ||
    shared ||
    "human_handoff_followup_text_es"
  );
};

const getHumanDeliveryMode = (message) => {
  const metadataRaw = message?.metadata;
  let metadata = metadataRaw;
  if (typeof metadataRaw === "string") {
    try {
      metadata = JSON.parse(metadataRaw);
    } catch {
      metadata = null;
    }
  }
  if (!metadata || typeof metadata !== "object") return "";
  const delivery = metadata.delivery;
  if (!delivery || typeof delivery !== "object") return "";
  return String(delivery.delivery_mode || "").trim().toLowerCase();
};

const humanDeliveryModeLabel = (mode, isEs) => {
  if (mode === "template") return isEs ? "enviado con template" : "sent via template";
  if (mode === "free_text") return isEs ? "enviado como texto directo" : "sent as direct text";
  if (mode === "free_text_fallback_to_template") {
    return isEs ? "texto directo falló, enviado con template" : "direct text failed, sent via template";
  }
  return "";
};

const parseHandoffMetadata = (handoff) => {
  const raw = handoff?.metadata;
  if (!raw) return {};
  if (typeof raw === "string") {
    try {
      const parsed = JSON.parse(raw);
      return parsed && typeof parsed === "object" ? parsed : {};
    } catch {
      return {};
    }
  }
  return raw && typeof raw === "object" ? raw : {};
};

const isConvertedProspect = (alert) => {
  const metadata = parseHandoffMetadata(alert?.handoff || {});
  if (metadata?.converted_to_client) return true;
  return String(metadata?.lifecycle_stage || "").trim().toLowerCase() === "client";
};

const isProspectAlert = (alert) => {
  const handoff = alert?.handoff || {};
  const reason = String(handoff?.reason || "").trim().toLowerCase();
  const trigger = String(handoff?.trigger || "").trim().toLowerCase();
  if (isConvertedProspect(alert)) return false;
  return reason === "campaign_interest" || trigger === "campaign_interest_button";
};

export default function InboxHandoff() {
  const clientId = useClientId();
  const { lang } = useLanguage();
  const isEs = lang === "es";

  const [filter, setFilter] = useState("open");
  const [alertsData, setAlertsData] = useState({ items: [], counts: {} });
  const [assignees, setAssignees] = useState([]);
  const [assigneesError, setAssigneesError] = useState("");
  const [selectedAssigneeId, setSelectedAssigneeId] = useState("");
  const [loadingAlerts, setLoadingAlerts] = useState(false);
  const [alertsError, setAlertsError] = useState("");
  const [selectedAlertId, setSelectedAlertId] = useState(null);
  const [detailHistory, setDetailHistory] = useState([]);
  const [detailNotes, setDetailNotes] = useState([]);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState("");
  const [noteDraft, setNoteDraft] = useState("");
  const [savingNote, setSavingNote] = useState(false);
  const [suggestedReply, setSuggestedReply] = useState("");
  const [suggestedReplyProvider, setSuggestedReplyProvider] = useState("");
  const [suggestingReply, setSuggestingReply] = useState(false);
  const [suggestedReplyError, setSuggestedReplyError] = useState("");
  const [emailReplySubject, setEmailReplySubject] = useState("");
  const [replyChannelOverride, setReplyChannelOverride] = useState("");
  const [markResolvedOnSend, setMarkResolvedOnSend] = useState(false);
  const [sendingReply, setSendingReply] = useState(false);
  const [sendReplyError, setSendReplyError] = useState("");
  const [sendReplySuccess, setSendReplySuccess] = useState("");
  const [updatingAlertId, setUpdatingAlertId] = useState(null);
  const [updatingHandoffId, setUpdatingHandoffId] = useState(null);
  const [convertingProspect, setConvertingProspect] = useState(false);
  const [prospectActionSuccess, setProspectActionSuccess] = useState("");

  const selectedAlert = useMemo(
    () => (alertsData.items || []).find((item) => item.id === selectedAlertId) || null,
    [alertsData.items, selectedAlertId]
  );

  const loadAlerts = async (nextFilter = filter) => {
    if (!clientId) return;
    setLoadingAlerts(true);
    setAlertsError("");
    try {
      const params = new URLSearchParams({
        client_id: clientId,
        status: nextFilter,
        limit: "50",
      });
      const res = await authFetch(`${import.meta.env.VITE_API_URL}/conversation_alerts?${params.toString()}`);
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail || "Could not load alerts");

      const items = Array.isArray(data?.items) ? data.items : [];
      setAlertsData({ items, counts: data?.counts || {} });
      setSelectedAlertId((current) => {
        if (current && items.some((it) => it.id === current)) return current;
        return items[0]?.id || null;
      });
    } catch (err) {
      setAlertsError(err?.message || "Could not load alerts");
      setAlertsData({ items: [], counts: {} });
      setSelectedAlertId(null);
    } finally {
      setLoadingAlerts(false);
    }
  };

  const loadAssignees = async () => {
    if (!clientId) return;
    setAssigneesError("");
    try {
      const params = new URLSearchParams({ client_id: clientId });
      const res = await authFetch(`${import.meta.env.VITE_API_URL}/conversation_assignees?${params.toString()}`);
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail || "Could not load assignees");
      const items = Array.isArray(data?.items) ? data.items : [];
      setAssignees(items);
      setSelectedAssigneeId((current) => current || items[0]?.id || "");
    } catch (err) {
      setAssignees([]);
      setAssigneesError(err?.message || "Could not load assignees");
    }
  };

  useEffect(() => {
    loadAlerts(filter);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clientId, filter]);

  useEffect(() => {
    loadAssignees();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clientId]);

  const loadDetail = async (alertItem) => {
    if (!clientId || !alertItem) {
      setDetailHistory([]);
      setDetailNotes([]);
      return;
    }
    const handoff = alertItem.handoff || {};
    const sessionId = handoff.session_id;
    const conversationId = alertItem.conversation_id;
    setDetailLoading(true);
    setDetailError("");
    try {
      const requests = [];
      if (sessionId) {
        const historyParams = new URLSearchParams({
          client_id: clientId,
          session_id: String(sessionId),
          limit: "100",
        });
        requests.push(
          authFetch(`${import.meta.env.VITE_API_URL}/history?${historyParams.toString()}`).then(async (res) => {
            const data = await res.json();
            if (!res.ok) throw new Error(data?.detail || data?.error || "Could not load history");
            return data;
          })
        );
      } else {
        requests.push(Promise.resolve({ history: [] }));
      }

      if (conversationId) {
        const notesParams = new URLSearchParams({
          client_id: clientId,
          conversation_id: String(conversationId),
          limit: "100",
        });
        requests.push(
          authFetch(`${import.meta.env.VITE_API_URL}/conversation_internal_notes?${notesParams.toString()}`).then(
            async (res) => {
              const data = await res.json();
              if (!res.ok) throw new Error(data?.detail || "Could not load notes");
              return data;
            }
          )
        );
      } else {
        requests.push(Promise.resolve({ items: [] }));
      }

      const [historyPayload, notesPayload] = await Promise.all(requests);
      const historyRows = Array.isArray(historyPayload?.history) ? historyPayload.history : [];
      historyRows.sort(
        (a, b) => new Date(a.created_at || 0).getTime() - new Date(b.created_at || 0).getTime()
      );
      setDetailHistory(historyRows);
      setDetailNotes(Array.isArray(notesPayload?.items) ? notesPayload.items : []);
    } catch (err) {
      setDetailError(err?.message || "Could not load conversation detail");
      setDetailHistory([]);
      setDetailNotes([]);
    } finally {
      setDetailLoading(false);
    }
  };

  useEffect(() => {
    if (!selectedAlert) {
      setDetailHistory([]);
      setDetailNotes([]);
      setSuggestedReply("");
      setSuggestedReplyProvider("");
      setSuggestedReplyError("");
      return;
    }
    setSelectedAssigneeId(
      String(
        selectedAlert?.handoff?.assigned_user_id ||
          selectedAlert?.assigned_user_id ||
          assignees[0]?.id ||
          ""
      )
    );
    setSuggestedReply("");
    setSuggestedReplyProvider("");
    setSuggestedReplyError("");
    setSendReplyError("");
    setSendReplySuccess("");
    setProspectActionSuccess("");
    const defaultReplyChannel = getDefaultReplyChannel(selectedAlert?.handoff || {});
    setReplyChannelOverride(defaultReplyChannel);
    setEmailReplySubject(
      defaultReplyChannel === "email"
        ? (isEs ? "Re: Seguimiento de tu solicitud" : "Re: Follow-up on your request")
        : ""
    );
    setMarkResolvedOnSend(false);
    loadDetail(selectedAlert);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedAlertId, clientId]);

  const updateAlertStatus = async (alertId, status) => {
    if (!clientId || !alertId) return;
    setUpdatingAlertId(alertId);
    try {
      const res = await authFetch(`${import.meta.env.VITE_API_URL}/conversation_alerts/${alertId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ client_id: clientId, status }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail || "Could not update alert");
      await loadAlerts(filter);
    } catch (err) {
      setDetailError(err?.message || "Could not update alert");
    } finally {
      setUpdatingAlertId(null);
    }
  };

  const updateHandoff = async (handoffId, payload) => {
    if (!clientId || !handoffId) return;
    setUpdatingHandoffId(handoffId);
    setDetailError("");
    try {
      const res = await authFetch(`${import.meta.env.VITE_API_URL}/conversation_handoff_requests/${handoffId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ client_id: clientId, ...payload }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail || "Could not update handoff");
      await loadAlerts(filter);
    } catch (err) {
      setDetailError(err?.message || "Could not update handoff");
    } finally {
      setUpdatingHandoffId(null);
    }
  };

  const submitNote = async () => {
    if (!clientId || !selectedAlert?.conversation_id) return;
    const note = noteDraft.trim();
    if (!note) return;
    setSavingNote(true);
    setDetailError("");
    try {
      const res = await authFetch(`${import.meta.env.VITE_API_URL}/conversation_internal_notes`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          client_id: clientId,
          conversation_id: selectedAlert.conversation_id,
          handoff_request_id: selectedAlert.source_handoff_request_id || null,
          note,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail || "Could not save note");
      setNoteDraft("");
      await loadDetail(selectedAlert);
    } catch (err) {
      setDetailError(err?.message || "Could not save note");
    } finally {
      setSavingNote(false);
    }
  };

  const generateSuggestedReply = async () => {
    const handoffId = selectedAlert?.source_handoff_request_id || selectedAlert?.handoff?.id;
    if (!clientId || !handoffId) return;
    setSuggestingReply(true);
    setSuggestedReplyError("");
    try {
      const res = await authFetch(
        `${import.meta.env.VITE_API_URL}/conversation_handoff_requests/${handoffId}/suggest_reply`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            client_id: clientId,
            language: isEs ? "es" : "en",
            tone: "professional",
          }),
        }
      );
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail || "Could not generate suggested reply");
      setSuggestedReply(String(data?.suggested_reply || ""));
      setSuggestedReplyProvider(String(data?.provider || ""));
    } catch (err) {
      setSuggestedReplyError(err?.message || "Could not generate suggested reply");
    } finally {
      setSuggestingReply(false);
    }
  };

  const sendHandoffReply = async () => {
    const handoffId = selectedAlert?.source_handoff_request_id || selectedAlert?.handoff?.id;
    const handoff = selectedAlert?.handoff || {};
    const originChannel = normalizeChannel(handoff.channel);
    const replyChannel = normalizeChannel(replyChannelOverride) || originChannel;
    const message = String(suggestedReply || "").trim();
    if (!clientId || !handoffId) return;
    if (!message) {
      setSendReplyError(isEs ? "Escribe o genera una respuesta antes de enviarla." : "Write or generate a reply before sending.");
      return;
    }

    setSendingReply(true);
    setSendReplyError("");
    setSendReplySuccess("");
    try {
      const payload = {
        client_id: clientId,
        message,
        reply_channel: replyChannel || null,
        mark_resolved: markResolvedOnSend,
      };
      if (replyChannel === "email") {
        payload.subject = String(emailReplySubject || "").trim() || "Re: Follow-up from support";
      }

      const res = await authFetch(
        `${import.meta.env.VITE_API_URL}/conversation_handoff_requests/${handoffId}/send_reply`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        }
      );
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail || "Could not send reply");

      const sentToEmail =
        replyChannel === "email"
          ? String(data?.delivery?.to_email || handoff?.contact_email || "").trim()
          : "";
      setSendReplySuccess(
        isEs
          ? `Respuesta enviada por ${channelLabel(replyChannel)}${sentToEmail ? ` a ${sentToEmail}` : ""}.`
          : `Reply sent via ${channelLabel(replyChannel)}${sentToEmail ? ` to ${sentToEmail}` : ""}.`
      );
      await loadAlerts(filter);
      await loadDetail(selectedAlert);
    } catch (err) {
      setSendReplyError(err?.message || "Could not send reply");
    } finally {
      setSendingReply(false);
    }
  };

  const convertProspectToClient = async () => {
    const handoffId = selectedAlert?.source_handoff_request_id || selectedAlert?.handoff?.id;
    if (!clientId || !handoffId) return;
    setConvertingProspect(true);
    setDetailError("");
    setProspectActionSuccess("");
    try {
      const res = await authFetch(
        `${import.meta.env.VITE_API_URL}/conversation_handoff_requests/${handoffId}/convert_to_client`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ client_id: clientId }),
        }
      );
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail || "Could not convert prospect");

      setProspectActionSuccess(
        isEs ? "Prospect convertido a cliente exitosamente." : "Prospect converted to client successfully."
      );
      await loadAlerts(filter);
    } catch (err) {
      setDetailError(err?.message || "Could not convert prospect");
    } finally {
      setConvertingProspect(false);
    }
  };

  const counts = alertsData.counts || {};

  return (
    <div className="ia-page">
      <div className="ia-shell" style={{ display: "grid", gap: "1rem" }}>
        <section className="ia-card" style={{ paddingBottom: "0.9rem" }}>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: "0.75rem",
              flexWrap: "wrap",
            }}
          >
            <div>
              <h2 className="ia-card-title" style={{ marginBottom: "0.2rem" }}>
                {isEs ? "Inbox / Handoff" : "Inbox / Handoff"}
              </h2>
              <p className="ia-dashboard-subtext" style={{ margin: 0 }}>
                {isEs
                  ? "Gestiona conversaciones escaladas por IA y seguimiento humano."
                  : "Review AI-escalated conversations and human follow-up."}
              </p>
            </div>
            <button
              type="button"
              className="ia-button"
              onClick={() => loadAlerts(filter)}
              style={{
                border: "1px solid #EDEDED",
                background: "#FFFFFF",
                color: "#274472",
                borderRadius: "10px",
                padding: "0.45rem 0.75rem",
              }}
            >
              {isEs ? "Actualizar" : "Refresh"}
            </button>
          </div>
        </section>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
            gap: "1rem",
          }}
        >
          <section className="ia-card" style={{ marginBottom: 0 }}>
            <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", marginBottom: "0.8rem" }}>
              {FILTER_OPTIONS.map((opt) => {
                const active = filter === opt;
                const count =
                  opt === "all"
                    ? (counts.open || 0) + (counts.acknowledged || 0) + (counts.resolved || 0)
                    : counts[opt];
                return (
                  <button
                    key={opt}
                    type="button"
                    onClick={() => setFilter(opt)}
                    style={{
                      borderRadius: "999px",
                      border: active ? "1px solid #2EB39A" : "1px solid #EDEDED",
                      background: active ? "#ECFAF5" : "#FFFFFF",
                      color: active ? "#1F7C67" : "#274472",
                      padding: "0.35rem 0.65rem",
                      fontWeight: 600,
                      cursor: "pointer",
                    }}
                  >
                    {prettyStatus(opt)}{typeof count === "number" ? ` (${count})` : ""}
                  </button>
                );
              })}
            </div>

            {alertsError ? (
              <div style={{ color: "#9F2D2D", marginBottom: "0.8rem" }}>{alertsError}</div>
            ) : null}

            {loadingAlerts ? (
              <p>{isEs ? "Cargando alertas..." : "Loading alerts..."}</p>
            ) : (alertsData.items || []).length === 0 ? (
              <p>{isEs ? "No hay alertas para este filtro." : "No alerts for this filter."}</p>
            ) : (
              <div style={{ display: "grid", gap: "0.6rem", maxHeight: "70vh", overflowY: "auto", paddingRight: "0.2rem" }}>
                {(alertsData.items || []).map((alert) => {
                  const handoff = alert.handoff || {};
                  const selected = alert.id === selectedAlertId;
                  return (
                    <button
                      key={alert.id}
                      type="button"
                      onClick={() => setSelectedAlertId(alert.id)}
                      style={{
                        textAlign: "left",
                        width: "100%",
                        border: selected ? "1px solid #4A90E2" : "1px solid #EDEDED",
                        background: selected ? "#F7FBFF" : "#FFFFFF",
                        borderRadius: "12px",
                        padding: "0.75rem",
                        cursor: "pointer",
                      }}
                    >
                      <div style={{ display: "flex", justifyContent: "space-between", gap: "0.5rem", marginBottom: "0.25rem" }}>
                        <strong style={{ color: "#274472" }}>{alert.title || "Human intervention"}</strong>
                        <span style={{ color: "#6B7280", fontSize: "0.8rem" }}>
                          {prettyStatus(alert.status)}
                        </span>
                      </div>
                      <div className="ia-break-anywhere" style={{ color: "#274472", fontSize: "0.9rem" }}>
                        {alert.body || handoff.last_user_message || (isEs ? "Sin mensaje" : "No message")}
                      </div>
                      <div
                        style={{
                          marginTop: "0.35rem",
                          color: "#6B7280",
                          fontSize: "0.78rem",
                          display: "flex",
                          gap: "0.35rem",
                          flexWrap: "wrap",
                        }}
                      >
                        {isProspectAlert(alert) ? (
                          <span
                            style={{
                              border: "1px solid #FCD34D",
                              background: "#FFFBEB",
                              color: "#92400E",
                              borderRadius: "999px",
                              padding: "0.08rem 0.45rem",
                              fontWeight: 700,
                            }}
                          >
                            Prospect
                          </span>
                        ) : null}
                        {isConvertedProspect(alert) ? (
                          <span
                            style={{
                              border: "1px solid #86EFAC",
                              background: "#F0FDF4",
                              color: "#166534",
                              borderRadius: "999px",
                              padding: "0.08rem 0.45rem",
                              fontWeight: 700,
                            }}
                          >
                            Client
                          </span>
                        ) : null}
                        <span>{channelLabel(handoff.channel)}</span>
                        {handoff.status ? <span>· handoff {prettyStatus(handoff.status)}</span> : null}
                        {handoff.assigned_user_id ? <span>· owner {handoff.assigned_user_id.slice(0, 8)}</span> : null}
                        {handoff.contact_name ? <span>· {handoff.contact_name}</span> : null}
                        {handoff.contact_email ? <span>· {handoff.contact_email}</span> : null}
                        {alert.created_at ? <span>· {fmtDate(alert.created_at)}</span> : null}
                      </div>
                    </button>
                  );
                })}
              </div>
            )}
          </section>

          <section className="ia-card" style={{ marginBottom: 0 }}>
            {!selectedAlert ? (
              <p>{isEs ? "Selecciona una alerta para ver detalle." : "Select an alert to view details."}</p>
            ) : (
              <>
                <InboxDetailHeader
                  alert={selectedAlert}
                  isEs={isEs}
                  onUpdateStatus={updateAlertStatus}
                  updating={updatingAlertId === selectedAlert.id}
                  onUpdateHandoff={updateHandoff}
                  updatingHandoff={updatingHandoffId === selectedAlert?.source_handoff_request_id}
                  onConvertProspect={convertProspectToClient}
                  convertingProspect={convertingProspect}
                />

                {detailError ? (
                  <div style={{ color: "#9F2D2D", marginBottom: "0.75rem" }}>{detailError}</div>
                ) : null}
                {prospectActionSuccess ? (
                  <div style={{ color: "#166534", marginBottom: "0.75rem" }}>{prospectActionSuccess}</div>
                ) : null}
                {assigneesError ? (
                  <div style={{ color: "#9F2D2D", marginBottom: "0.75rem" }}>{assigneesError}</div>
                ) : null}

                {detailLoading ? (
                  <p>{isEs ? "Cargando detalle..." : "Loading detail..."}</p>
                ) : (
                  <div style={{ display: "grid", gap: "1rem" }}>
                    <DetailInfoCard alert={selectedAlert} isEs={isEs} />
                    <AssigneeCard
                      assignees={assignees}
                      selectedAssigneeId={selectedAssigneeId}
                      setSelectedAssigneeId={setSelectedAssigneeId}
                      onAssign={() =>
                        updateHandoff(selectedAlert?.source_handoff_request_id || selectedAlert?.handoff?.id, {
                          assigned_user_id: selectedAssigneeId || null,
                        })
                      }
                      onClear={() =>
                        updateHandoff(selectedAlert?.source_handoff_request_id || selectedAlert?.handoff?.id, {
                          clear_assignee: true,
                        })
                      }
                      loading={updatingHandoffId === (selectedAlert?.source_handoff_request_id || selectedAlert?.handoff?.id)}
                      isEs={isEs}
                      disabled={!selectedAlert?.source_handoff_request_id}
                    />
                    <SuggestedReplyCard
                      handoff={selectedAlert?.handoff || {}}
                      suggestedReply={suggestedReply}
                      setSuggestedReply={setSuggestedReply}
                      provider={suggestedReplyProvider}
                      loading={suggestingReply}
                      error={suggestedReplyError}
                      onGenerate={generateSuggestedReply}
                      onSend={sendHandoffReply}
                      sending={sendingReply}
                      sendError={sendReplyError}
                      sendSuccess={sendReplySuccess}
                      replyChannelOverride={replyChannelOverride}
                      setReplyChannelOverride={setReplyChannelOverride}
                      emailSubject={emailReplySubject}
                      setEmailSubject={setEmailReplySubject}
                      markResolvedOnSend={markResolvedOnSend}
                      setMarkResolvedOnSend={setMarkResolvedOnSend}
                      isEs={isEs}
                      disabled={!selectedAlert?.source_handoff_request_id}
                    />
                    <TimelineCard messages={detailHistory} isEs={isEs} />
                    <InternalNotesCard
                      notes={detailNotes}
                      noteDraft={noteDraft}
                      setNoteDraft={setNoteDraft}
                      onSubmit={submitNote}
                      saving={savingNote}
                      disabled={!selectedAlert.conversation_id}
                      isEs={isEs}
                    />
                  </div>
                )}
              </>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}

function AssigneeCard({
  assignees,
  selectedAssigneeId,
  setSelectedAssigneeId,
  onAssign,
  onClear,
  loading,
  isEs,
  disabled,
}) {
  return (
    <div style={{ border: "1px solid #EDEDED", borderRadius: "12px", padding: "0.85rem" }}>
      <div style={{ fontWeight: 700, color: "#274472", marginBottom: "0.55rem" }}>
        {isEs ? "Asignación" : "Assignment"}
      </div>
      <div style={{ display: "grid", gap: "0.55rem" }}>
        <select
          value={selectedAssigneeId}
          onChange={(e) => setSelectedAssigneeId(e.target.value)}
          disabled={disabled || loading || (assignees || []).length === 0}
          style={{
            width: "100%",
            borderRadius: "10px",
            border: "1px solid #DCE7F5",
            padding: "0.6rem",
            color: "#274472",
            background: disabled ? "#F9FAFB" : "#FFFFFF",
          }}
        >
          {(assignees || []).length === 0 ? (
            <option value="">{isEs ? "Sin usuarios disponibles" : "No assignees available"}</option>
          ) : (
            (assignees || []).map((assignee) => (
              <option key={assignee.id} value={assignee.id}>
                {assignee.email || assignee.id}
                {assignee.is_current_user ? (isEs ? " (yo)" : " (me)") : ""}
              </option>
            ))
          )}
        </select>
        <div style={{ display: "flex", gap: "0.45rem", flexWrap: "wrap" }}>
          <button
            type="button"
            className="ia-button"
            onClick={onAssign}
            disabled={disabled || loading || !selectedAssigneeId}
            style={{
              borderRadius: "10px",
              border: "1px solid #DCE7F5",
              background: "#F5F8FC",
              color: "#274472",
              padding: "0.45rem 0.7rem",
            }}
          >
            {loading ? (isEs ? "Guardando..." : "Saving...") : isEs ? "Asignar usuario" : "Assign user"}
          </button>
          <button
            type="button"
            className="ia-button"
            onClick={onClear}
            disabled={disabled || loading}
            style={{
              borderRadius: "10px",
              border: "1px solid #EDEDED",
              background: "#FFFFFF",
              color: "#274472",
              padding: "0.45rem 0.7rem",
            }}
          >
            {loading ? (isEs ? "Guardando..." : "Saving...") : isEs ? "Limpiar asignación" : "Clear assignee"}
          </button>
        </div>
      </div>
    </div>
  );
}

function InboxDetailHeader({
  alert,
  isEs,
  onUpdateStatus,
  updating,
  onUpdateHandoff,
  updatingHandoff,
  onConvertProspect,
  convertingProspect,
}) {
  const currentStatus = String(alert?.status || "").toLowerCase();
  const handoff = alert?.handoff || {};
  const handoffStatus = String(handoff.status || "").toLowerCase();
  const handoffId = alert?.source_handoff_request_id || handoff?.id || null;
  const canConvertProspect = isProspectAlert(alert);
  return (
    <div
      style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "flex-start",
        gap: "0.75rem",
        flexWrap: "wrap",
        marginBottom: "0.9rem",
      }}
    >
      <div>
        <h2 className="ia-card-title" style={{ marginBottom: "0.15rem" }}>
          {alert?.title || (isEs ? "Intervención humana" : "Human intervention")}
        </h2>
        <p className="ia-dashboard-subtext" style={{ margin: 0 }}>
          {prettyStatus(alert?.status)} · {fmtDate(alert?.created_at)}
          {handoffStatus ? ` · Handoff: ${prettyStatus(handoffStatus)}` : ""}
        </p>
      </div>
      <div style={{ display: "flex", gap: "0.45rem", flexWrap: "wrap" }}>
        {handoffId && (
          <button
            type="button"
            className="ia-button"
            disabled={updatingHandoff}
            onClick={() => onUpdateHandoff(handoffId, { assign_to_me: true })}
            style={{
              borderRadius: "10px",
              border: "1px solid #EDEDED",
              background: "#FFFFFF",
              color: "#274472",
              padding: "0.45rem 0.7rem",
            }}
          >
            {updatingHandoff ? (isEs ? "Guardando..." : "Saving...") : isEs ? "Asignarme" : "Assign to me"}
          </button>
        )}
        {handoffId && handoffStatus !== "in_progress" && handoffStatus !== "resolved" && (
          <button
            type="button"
            className="ia-button"
            disabled={updatingHandoff}
            onClick={() => onUpdateHandoff(handoffId, { status: "in_progress", assign_to_me: true })}
            style={{
              borderRadius: "10px",
              border: "1px solid #DCE7F5",
              background: "#F5F8FC",
              color: "#274472",
              padding: "0.45rem 0.7rem",
            }}
          >
            {updatingHandoff ? (isEs ? "Guardando..." : "Saving...") : isEs ? "Iniciar" : "Start work"}
          </button>
        )}
        {handoffId && handoffStatus !== "resolved" && (
          <button
            type="button"
            className="ia-button ia-button-primary"
            disabled={updatingHandoff}
            onClick={() => onUpdateHandoff(handoffId, { status: "resolved" })}
            style={{ borderRadius: "10px", padding: "0.45rem 0.7rem" }}
          >
            {updatingHandoff ? (isEs ? "Guardando..." : "Saving...") : isEs ? "Resolver handoff" : "Resolve handoff"}
          </button>
        )}
        {handoffId && canConvertProspect && (
          <button
            type="button"
            className="ia-button"
            disabled={convertingProspect}
            onClick={onConvertProspect}
            style={{
              borderRadius: "10px",
              border: "1px solid #86EFAC",
              background: "#F0FDF4",
              color: "#166534",
              padding: "0.45rem 0.7rem",
            }}
          >
            {convertingProspect ? (isEs ? "Convirtiendo..." : "Converting...") : isEs ? "Convertir a cliente" : "Convert to client"}
          </button>
        )}
        {currentStatus !== "acknowledged" && currentStatus !== "resolved" && (
          <button
            type="button"
            className="ia-button"
            disabled={updating}
            onClick={() => onUpdateStatus(alert.id, "acknowledged")}
            style={{
              borderRadius: "10px",
              border: "1px solid #DCE7F5",
              background: "#F5F8FC",
              color: "#274472",
              padding: "0.45rem 0.7rem",
            }}
          >
            {updating ? (isEs ? "Guardando..." : "Saving...") : isEs ? "En revisión" : "Acknowledge"}
          </button>
        )}
        {currentStatus !== "resolved" && (
          <button
            type="button"
            className="ia-button ia-button-primary"
            disabled={updating}
            onClick={() => onUpdateStatus(alert.id, "resolved")}
            style={{ borderRadius: "10px", padding: "0.45rem 0.7rem" }}
          >
            {updating ? (isEs ? "Guardando..." : "Saving...") : isEs ? "Resolver" : "Resolve"}
          </button>
        )}
      </div>
    </div>
  );
}

function DetailInfoCard({ alert, isEs }) {
  const handoff = alert?.handoff || {};
  const rows = [
    [isEs ? "Canal" : "Channel", channelLabel(handoff.channel)],
    [isEs ? "Estado handoff" : "Handoff status", handoff.status || "-"],
    [isEs ? "Asignado a" : "Assigned to", handoff.assigned_user_id || alert?.assigned_user_id || "-"],
    [isEs ? "Trigger" : "Trigger", handoff.trigger || "-"],
    [isEs ? "Razón" : "Reason", handoff.reason || "-"],
    [isEs ? "Confianza" : "Confidence", handoff.confidence_score ?? "-"],
    [isEs ? "Contacto" : "Contact", handoff.contact_name || "-"],
    [isEs ? "Email" : "Email", handoff.contact_email || "-"],
    [isEs ? "Teléfono" : "Phone", handoff.contact_phone || "-"],
    [isEs ? "Sesión" : "Session", handoff.session_id || "-"],
    [isEs ? "Conversation ID" : "Conversation ID", alert?.conversation_id || "-"],
    [isEs ? "Resuelto" : "Resolved at", handoff.resolved_at || alert?.resolved_at || "-"],
  ];
  return (
    <div style={{ border: "1px solid #EDEDED", borderRadius: "12px", padding: "0.85rem" }}>
      <div style={{ fontWeight: 700, color: "#274472", marginBottom: "0.55rem" }}>
        {isEs ? "Detalle de handoff" : "Handoff detail"}
      </div>
      <div style={{ display: "grid", gap: "0.35rem" }}>
        {rows.map(([label, value]) => (
          <div key={label} style={{ display: "grid", gridTemplateColumns: "140px 1fr", gap: "0.5rem" }}>
            <div style={{ color: "#6B7280", fontSize: "0.85rem" }}>{label}</div>
            <div className="ia-break-anywhere" style={{ color: "#274472", fontSize: "0.9rem" }}>
              {String(value ?? "-")}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function TimelineCard({ messages, isEs }) {
  return (
    <div style={{ border: "1px solid #EDEDED", borderRadius: "12px", padding: "0.85rem" }}>
      <div style={{ fontWeight: 700, color: "#274472", marginBottom: "0.55rem" }}>
        {isEs ? "Timeline de conversación" : "Conversation timeline"}
      </div>
      {!messages || messages.length === 0 ? (
        <p style={{ margin: 0, color: "#6B7280" }}>
          {isEs ? "Sin historial disponible para esta sesión." : "No session history available for this alert."}
        </p>
      ) : (
        <div style={{ display: "grid", gap: "0.6rem", maxHeight: "280px", overflowY: "auto", paddingRight: "0.2rem" }}>
          {messages.map((msg, idx) => {
            const role = String(msg.role || "").toLowerCase();
            const sourceType = String(msg.source_type || "").toLowerCase();
            const isUser = role === "user";
            const isHumanAgent = sourceType === "human_agent";
            const deliveryMode = isHumanAgent ? getHumanDeliveryMode(msg) : "";
            const deliveryModeLabel = humanDeliveryModeLabel(deliveryMode, isEs);
            return (
              <div
                key={`${msg.created_at || idx}-${idx}`}
                style={{
                  border: isUser
                    ? "1px solid #DCE7F5"
                    : isHumanAgent
                      ? "1px solid #D7F0E8"
                      : "1px solid #EDEDED",
                  background: isUser ? "#F7FBFF" : isHumanAgent ? "#F3FCF8" : "#FFFFFF",
                  borderRadius: "10px",
                  padding: "0.65rem",
                }}
              >
                <div
                  style={{
                    color: "#6B7280",
                    fontSize: "0.78rem",
                    marginBottom: "0.25rem",
                    display: "flex",
                    gap: "0.35rem",
                    flexWrap: "wrap",
                  }}
                >
                  <span>
                    {isUser ? (isEs ? "Usuario" : "User") : isHumanAgent ? (isEs ? "Agente" : "Agent") : "AI"}
                  </span>
                  {msg.channel ? <span>· {channelLabel(msg.channel)}</span> : null}
                  {isHumanAgent ? <span>· {isEs ? "humano" : "human"}</span> : null}
                  {deliveryModeLabel ? (
                    <span
                      style={{
                        background: "#ECFAF5",
                        color: "#1F7C67",
                        border: "1px solid #A3D9B1",
                        borderRadius: "999px",
                        padding: "0.1rem 0.4rem",
                        fontSize: "0.72rem",
                        fontWeight: 700,
                        lineHeight: 1.2,
                      }}
                    >
                      {deliveryModeLabel}
                    </span>
                  ) : null}
                  {msg.created_at ? <span>· {fmtDate(msg.created_at)}</span> : null}
                </div>
                <div className="ia-break-anywhere" style={{ color: "#274472", whiteSpace: "pre-wrap" }}>
                  {msg.content || "(empty)"}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function SuggestedReplyCard({
  handoff,
  suggestedReply,
  setSuggestedReply,
  provider,
  loading,
  error,
  onGenerate,
  onSend,
  sending,
  sendError,
  sendSuccess,
  replyChannelOverride,
  setReplyChannelOverride,
  emailSubject,
  setEmailSubject,
  markResolvedOnSend,
  setMarkResolvedOnSend,
  isEs,
  disabled,
}) {
  const canCopy = Boolean(String(suggestedReply || "").trim());
  const originChannel = normalizeChannel(handoff?.channel);
  const replyOptions = getReplyChannelOptions(handoff);
  const normalizedChannel = normalizeChannel(replyChannelOverride) || getDefaultReplyChannel(handoff);
  const sendSupported = normalizedChannel === "email" || normalizedChannel === "whatsapp";
  const sendDisabled = disabled || sending || !sendSupported || !String(suggestedReply || "").trim();
  const whatsappTemplateLanguage = resolveWhatsappTemplateLanguage(handoff);
  const whatsappTemplateName = resolveWhatsappTemplateName(whatsappTemplateLanguage);
  const contactMissing =
    normalizedChannel === "email"
      ? !String(handoff?.contact_email || "").trim()
      : normalizedChannel === "whatsapp"
        ? !String(handoff?.contact_phone || "").trim()
        : false;

  const copyDraft = async () => {
    if (!canCopy || typeof navigator === "undefined" || !navigator.clipboard?.writeText) return;
    try {
      await navigator.clipboard.writeText(suggestedReply);
    } catch {
      // silent fallback; user can copy manually
    }
  };

  return (
    <div style={{ border: "1px solid #EDEDED", borderRadius: "12px", padding: "0.85rem" }}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          gap: "0.5rem",
          flexWrap: "wrap",
          marginBottom: "0.55rem",
        }}
      >
        <div style={{ fontWeight: 700, color: "#274472" }}>
          {isEs ? "Respuesta sugerida (draft)" : "Suggested reply (draft)"}
        </div>
        <div style={{ display: "flex", gap: "0.45rem", flexWrap: "wrap" }}>
          {provider ? (
            <span
              style={{
                fontSize: "0.72rem",
                lineHeight: 1,
                padding: "0.2rem 0.45rem",
                borderRadius: "999px",
                background: provider === "openai" ? "#ECFAF5" : "#FFF7E8",
                border: provider === "openai" ? "1px solid #A3D9B1" : "1px solid #F6D58A",
                color: provider === "openai" ? "#1F7C67" : "#8A6400",
                fontWeight: 700,
              }}
            >
              {provider}
            </span>
          ) : null}
          <button
            type="button"
            className="ia-button"
            onClick={onGenerate}
            disabled={disabled || loading}
            style={{
              borderRadius: "10px",
              border: "1px solid #DCE7F5",
              background: "#F5F8FC",
              color: "#274472",
              padding: "0.4rem 0.65rem",
            }}
          >
            {loading ? (isEs ? "Generando..." : "Generating...") : isEs ? "Generar sugerencia" : "Generate draft"}
          </button>
          <button
            type="button"
            className="ia-button"
            onClick={copyDraft}
            disabled={!canCopy}
            style={{
              borderRadius: "10px",
              border: "1px solid #EDEDED",
              background: "#FFFFFF",
              color: "#274472",
              padding: "0.4rem 0.65rem",
            }}
          >
            {isEs ? "Copiar" : "Copy"}
          </button>
        </div>
      </div>

      {error ? <div style={{ color: "#9F2D2D", marginBottom: "0.55rem" }}>{error}</div> : null}
      {sendError ? <div style={{ color: "#9F2D2D", marginBottom: "0.55rem" }}>{sendError}</div> : null}
      {sendSuccess ? <div style={{ color: "#1F7C67", marginBottom: "0.55rem" }}>{sendSuccess}</div> : null}

      <textarea
        value={suggestedReply}
        onChange={(e) => setSuggestedReply(e.target.value)}
        rows={6}
        placeholder={
          disabled
            ? (isEs ? "No disponible: la alerta no tiene handoff asociado" : "Unavailable: alert has no linked handoff")
            : (isEs ? "Genera una sugerencia y ajústala antes de responder al cliente." : "Generate a draft and edit it before replying to the customer.")
        }
        disabled={disabled}
        style={{
          width: "100%",
          borderRadius: "10px",
          border: "1px solid #DCE7F5",
          padding: "0.65rem",
          resize: "vertical",
          color: "#274472",
          background: disabled ? "#F9FAFB" : "#FFFFFF",
          whiteSpace: "pre-wrap",
        }}
      />
      <p className="ia-dashboard-subtext" style={{ margin: "0.45rem 0 0" }}>
        {isEs
          ? "Borrador para agente humano. Revísalo antes de enviarlo por el canal correspondiente."
          : "Draft for a human agent. Review before sending through the appropriate channel."}
      </p>

      <div style={{ marginTop: "0.75rem", display: "grid", gap: "0.55rem" }}>
        <div style={{ color: "#6B7280", fontSize: "0.82rem" }}>
          {isEs ? "Canal origen" : "Origin channel"}: <strong style={{ color: "#274472" }}>{channelLabel(originChannel)}</strong>
        </div>

        <div style={{ color: "#6B7280", fontSize: "0.82rem" }}>
          {isEs ? "Responder por" : "Reply via"}: <strong style={{ color: "#274472" }}>{channelLabel(normalizedChannel)}</strong>
          {normalizedChannel === "email" && handoff?.contact_email ? ` · ${handoff.contact_email}` : ""}
          {normalizedChannel === "whatsapp" && handoff?.contact_phone ? ` · ${handoff.contact_phone}` : ""}
        </div>

        {replyOptions.length > 1 ? (
          <select
            value={normalizedChannel}
            onChange={(e) => setReplyChannelOverride(e.target.value)}
            disabled={disabled || sending}
            style={{
              width: "100%",
              borderRadius: "10px",
              border: "1px solid #DCE7F5",
              padding: "0.6rem",
              color: "#274472",
              background: disabled ? "#F9FAFB" : "#FFFFFF",
            }}
          >
            {replyOptions.map((opt) => (
              <option key={opt} value={opt}>
                {isEs ? `Responder por ${channelLabel(opt)}` : `Reply via ${channelLabel(opt)}`}
              </option>
            ))}
          </select>
        ) : null}

        {normalizedChannel === "email" ? (
          <input
            type="text"
            value={emailSubject}
            onChange={(e) => setEmailSubject(e.target.value)}
            placeholder={isEs ? "Asunto del correo" : "Email subject"}
            disabled={disabled || sending}
            style={{
              width: "100%",
              borderRadius: "10px",
              border: "1px solid #DCE7F5",
              padding: "0.6rem",
              color: "#274472",
              background: disabled ? "#F9FAFB" : "#FFFFFF",
            }}
          />
        ) : null}

        {normalizedChannel === "widget" || normalizedChannel === "chat" ? (
          <div style={{ color: "#8A6400", fontSize: "0.82rem" }}>
            {isEs
              ? "Envío directo para widget/chat aún no disponible desde Inbox. Usa handoffs por email o WhatsApp."
              : "Direct sending for widget/chat is not available from Inbox yet. Use email or WhatsApp handoffs."}
          </div>
        ) : null}

        {normalizedChannel === "whatsapp" ? (
          <div style={{ color: "#8A6400", fontSize: "0.82rem" }}>
            {originChannel === "whatsapp"
              ? (
                isEs
                  ? `Origen WhatsApp: primero intentamos enviar texto directo (sin template). Si WhatsApp no lo permite (ventana cerrada), enviamos template con variable libre (ej. {{1}}). Template configurado: ${whatsappTemplateName} · Idioma: ${whatsappTemplateLanguage}`
                  : `WhatsApp origin: we first try direct text (no template). If WhatsApp does not allow it (closed window), we send a template with a free-text variable (e.g. {{1}}). Configured template: ${whatsappTemplateName} · Language: ${whatsappTemplateLanguage}`
              )
              : (
                isEs
                  ? `Origen ${channelLabel(originChannel)}: enviamos template de WhatsApp directamente (no intentamos texto libre). Template configurado: ${whatsappTemplateName} · Idioma: ${whatsappTemplateLanguage}`
                  : `Origin ${channelLabel(originChannel)}: we send a WhatsApp template directly (we do not attempt free text). Configured template: ${whatsappTemplateName} · Language: ${whatsappTemplateLanguage}`
              )}
          </div>
        ) : null}

        {sendSupported && contactMissing ? (
          <div style={{ color: "#9F2D2D", fontSize: "0.82rem" }}>
            {isEs
              ? "Falta dato de contacto para enviar esta respuesta."
              : "Missing contact data required to send this reply."}
          </div>
        ) : null}

        <label style={{ display: "flex", alignItems: "center", gap: "0.45rem", color: "#274472", fontSize: "0.85rem" }}>
          <input
            type="checkbox"
            checked={markResolvedOnSend}
            onChange={(e) => setMarkResolvedOnSend(e.target.checked)}
            disabled={disabled || sending}
          />
          {isEs ? "Resolver handoff después de enviar" : "Resolve handoff after send"}
        </label>

        <div style={{ display: "flex", justifyContent: "flex-end" }}>
          <button
            type="button"
            className="ia-button ia-button-primary"
            onClick={onSend}
            disabled={sendDisabled || contactMissing}
            style={{ borderRadius: "10px", padding: "0.45rem 0.7rem" }}
          >
            {sending ? (isEs ? "Enviando..." : "Sending...") : isEs ? "Enviar respuesta" : "Send reply"}
          </button>
        </div>
      </div>
    </div>
  );
}

function InternalNotesCard({
  notes,
  noteDraft,
  setNoteDraft,
  onSubmit,
  saving,
  disabled,
  isEs,
}) {
  return (
    <div style={{ border: "1px solid #EDEDED", borderRadius: "12px", padding: "0.85rem" }}>
      <div style={{ fontWeight: 700, color: "#274472", marginBottom: "0.55rem" }}>
        {isEs ? "Notas internas" : "Internal notes"}
      </div>
      <div style={{ display: "grid", gap: "0.55rem" }}>
        <textarea
          value={noteDraft}
          onChange={(e) => setNoteDraft(e.target.value)}
          rows={3}
          placeholder={
            disabled
              ? (isEs ? "No disponible: la alerta no tiene conversation_id" : "Unavailable: alert has no conversation_id")
              : (isEs ? "Agregar nota interna para el equipo..." : "Add internal note for the team...")
          }
          disabled={disabled || saving}
          style={{
            width: "100%",
            borderRadius: "10px",
            border: "1px solid #DCE7F5",
            padding: "0.65rem",
            resize: "vertical",
            color: "#274472",
            background: disabled ? "#F9FAFB" : "#FFFFFF",
          }}
        />
        <div style={{ display: "flex", justifyContent: "flex-end" }}>
          <button
            type="button"
            className="ia-button ia-button-primary"
            onClick={onSubmit}
            disabled={disabled || saving || !String(noteDraft || "").trim()}
            style={{ borderRadius: "10px", padding: "0.45rem 0.7rem" }}
          >
            {saving ? (isEs ? "Guardando..." : "Saving...") : isEs ? "Guardar nota" : "Save note"}
          </button>
        </div>
      </div>

      <div style={{ display: "grid", gap: "0.55rem", marginTop: "0.85rem" }}>
        {!notes || notes.length === 0 ? (
          <p style={{ margin: 0, color: "#6B7280" }}>
            {isEs ? "No hay notas internas todavía." : "No internal notes yet."}
          </p>
        ) : (
          notes.map((note) => (
            <div
              key={note.id}
              style={{
                border: "1px solid #EDEDED",
                borderRadius: "10px",
                padding: "0.6rem",
                background: "#FFFFFF",
              }}
            >
              <div style={{ color: "#6B7280", fontSize: "0.76rem", marginBottom: "0.25rem" }}>
                {fmtDate(note.created_at)}
                {note.author_user_id ? ` · ${note.author_user_id}` : ""}
              </div>
              <div className="ia-break-anywhere" style={{ color: "#274472", whiteSpace: "pre-wrap" }}>
                {note.note}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
