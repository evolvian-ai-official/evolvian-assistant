import { useEffect, useRef, useState } from "react";
import { supabase } from "../../lib/supabaseClient";
import axios from "axios";
import { useClientId } from "../../hooks/useClientId";
import { useLanguage } from "../../contexts/LanguageContext";
import { trackClientEvent } from "../../lib/tracking";
import { getAuthHeaders } from "../../lib/authFetch";
import "../../components/ui/internal-admin-responsive.css";

const API = import.meta.env.VITE_API_URL;

const isValidPhone = (phone) => /^\+\d{11,15}$/.test(phone);
const isValidPhoneId = (id) => /^\d{10,20}$/.test(id);
const isValidToken = (token) => /^EA[A-Za-z0-9]{16,}$/.test(token);
const isValidWabaId = (id) => /^\d{8,24}$/.test(id);
const isValidMetaRecipientId = (id) => /^[A-Za-z0-9_.:-]{5,100}$/.test(String(id || "").trim());
const WA_SETUP_TIMEOUT_MS = 120000;
const WA_SETUP_POLL_MS = 5000;

const emptySetupProgress = () => ({
  active: false,
  complete: false,
  timedOut: false,
  steps: [],
  suggestions: [],
  phoneStatus: null,
  lastError: "",
});

const maskSensitive = (value, visibleStart = 3, visibleEnd = 3) => {
  const raw = String(value || "").trim();
  if (!raw) return "";
  if (raw.length <= visibleStart + visibleEnd) return "•".repeat(Math.max(raw.length, 4));
  const maskedLength = Math.max(4, raw.length - visibleStart - visibleEnd);
  return `${raw.slice(0, visibleStart)}${"•".repeat(maskedLength)}${raw.slice(-visibleEnd)}`;
};

const normalizeChannelRows = (value) => {
  if (Array.isArray(value)) return value;
  if (value && Array.isArray(value.data)) return value.data;
  return [];
};

async function fetchMetaChannel(clientId, channelType, headers) {
  const res = await axios.get(
    `${API}/channels?client_id=${clientId}&type=${channelType}&provider=meta`,
    { headers }
  );
  const rows = normalizeChannelRows(res.data);
  return rows.find((r) => (r.is_active ?? r.active) !== false) || rows[0] || null;
}

export default function WhatsAppSetup() {
  const { t } = useLanguage();
  const clientId = useClientId();

  const [session, setSession] = useState(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState("");

  const [provider, setProvider] = useState("meta");
  const [waConnectionMethod, setWaConnectionMethod] = useState("meta_embedded");
  const [phone, setPhone] = useState("");
  const [waPhoneId, setWaPhoneId] = useState("");
  const [waToken, setWaToken] = useState("");
  const [waBusinessAccountId, setWaBusinessAccountId] = useState("");
  const [waConnected, setWaConnected] = useState(false);

  const [metaPageToken, setMetaPageToken] = useState("");
  const [messengerRecipientId, setMessengerRecipientId] = useState("");
  const [instagramRecipientId, setInstagramRecipientId] = useState("");
  const [messengerConnected, setMessengerConnected] = useState(false);
  const [instagramConnected, setInstagramConnected] = useState(false);

  const [status, setStatus] = useState({ message: "", type: "" });
  const [waSetupProgress, setWaSetupProgress] = useState(emptySetupProgress);
  const [metaSelectionToken, setMetaSelectionToken] = useState("");
  const [metaSelectionOptions, setMetaSelectionOptions] = useState([]);
  const [metaSelectedPhoneId, setMetaSelectedPhoneId] = useState("");
  const setupRunRef = useRef(0);

  const [touched, setTouched] = useState({
    phone: false,
    waPhoneId: false,
    waToken: false,
    waBusinessAccountId: false,
    metaPageToken: false,
    messengerRecipientId: false,
    instagramRecipientId: false,
  });

  const loadingAction = (key) => submitting === key;

  const consumeMetaCallbackQuery = () => {
    if (typeof window === "undefined") return { status: "", reason: "", selectionToken: "" };
    const queryParams = new URLSearchParams(window.location.search || "");
    const hashRaw = String(window.location.hash || "").replace(/^#/, "");
    const hashParams = new URLSearchParams(hashRaw);

    const getParam = (key) => String(queryParams.get(key) || hashParams.get(key) || "").trim();
    const status = getParam("meta_setup");
    const reason = getParam("meta_reason");
    const selectionToken = getParam("meta_selection_token");
    if (!status && !selectionToken) return { status: "", reason: "", selectionToken: "" };

    const cleanupKeys = ["meta_setup", "meta_reason", "meta_connected", "meta_setup_complete", "meta_selection_token"];
    cleanupKeys.forEach((key) => {
      queryParams.delete(key);
      hashParams.delete(key);
    });

    const nextQuery = queryParams.toString();
    const nextHash = hashParams.toString();
    const nextUrl = `${window.location.pathname}${nextQuery ? `?${nextQuery}` : ""}${nextHash ? `#${nextHash}` : ""}`;
    window.history.replaceState({}, "", nextUrl);
    return { status, reason, selectionToken };
  };

  useEffect(() => {
    return () => {
      setupRunRef.current += 1;
    };
  }, []);

  useEffect(() => {
    const init = async () => {
      try {
        const callbackState = consumeMetaCallbackQuery();

        const {
          data: { session: userSession },
        } = await supabase.auth.getSession();
        if (!userSession || !clientId) {
          setLoading(false);
          return;
        }
        setSession(userSession);

        const headers = await getAuthHeaders();
        if (callbackState.status === "success") {
          setWaConnectionMethod("meta_embedded");
          setSuccess(t("meta_embedded_callback_success"));
          resetMetaSelection();
        } else if (callbackState.status === "error") {
          resetMetaSelection();
          setError(
            callbackState.reason
              ? `${t("meta_embedded_callback_error")}: ${callbackState.reason}`
              : t("meta_embedded_callback_error")
          );
        } else if (callbackState.status === "select_phone" && callbackState.selectionToken) {
          try {
            setWaConnectionMethod("meta_embedded");
            await loadMetaSelectionOptions(callbackState.selectionToken, headers);
            setSuccess(t("meta_embedded_select_phone_prompt"));
          } catch (selectionErr) {
            const detail = selectionErr?.response?.data?.detail;
            setError(detail || t("meta_embedded_select_phone_error"));
          }
        }

        const [waRes, messengerRes, instagramRes] = await Promise.all([
          axios.get(`${API}/whatsapp_status`, { headers }).catch(() => ({ data: { connected: false } })),
          fetchMetaChannel(clientId, "messenger", headers).catch(() => null),
          fetchMetaChannel(clientId, "instagram", headers).catch(() => null),
        ]);

        if (waRes?.data?.connected) {
          setPhone(waRes.data.phone || "");
          setWaPhoneId(waRes.data.wa_phone_id || "");
          setWaBusinessAccountId(waRes.data.wa_business_account_id || "");
          setProvider(waRes.data.provider || "meta");
          setWaConnected(true);

          const progressRes = await axios.get(`${API}/whatsapp_setup_progress`, { headers }).catch(() => null);
          if (progressRes?.data) {
            setWaSetupProgress({
              active: !Boolean(progressRes.data.setup_complete),
              complete: Boolean(progressRes.data.setup_complete),
              timedOut: false,
              steps: Array.isArray(progressRes.data.steps) ? progressRes.data.steps : [],
              suggestions: Array.isArray(progressRes.data.suggestions) ? progressRes.data.suggestions : [],
              phoneStatus: progressRes.data.phone_status || null,
              lastError: "",
            });
          }
        }

        if (messengerRes) {
          setMessengerConnected(Boolean((messengerRes.is_active ?? messengerRes.active) !== false));
          setMessengerRecipientId(String(messengerRes.value || ""));
        }
        if (instagramRes) {
          setInstagramConnected(Boolean((instagramRes.is_active ?? instagramRes.active) !== false));
          setInstagramRecipientId(String(instagramRes.value || ""));
        }
      } finally {
        setLoading(false);
      }
    };

    init();
  }, [clientId]);

  const setError = (message) => setStatus({ message, type: "error" });
  const setSuccess = (message) => setStatus({ message, type: "success" });
  const resetSetupProgress = () => setWaSetupProgress(emptySetupProgress());
  const resetMetaSelection = () => {
    setMetaSelectionToken("");
    setMetaSelectionOptions([]);
    setMetaSelectedPhoneId("");
  };

  const loadMetaSelectionOptions = async (selectionToken, headers) => {
    const token = String(selectionToken || "").trim();
    if (!token) return;
    const res = await axios.post(
      `${API}/meta_embedded_signup/selection_options`,
      { selection_token: token },
      { headers }
    );
    const options = Array.isArray(res?.data?.candidates) ? res.data.candidates : [];
    const suggested = String(res?.data?.suggested_phone_id || "").trim();
    setMetaSelectionToken(token);
    setMetaSelectionOptions(options);
    setMetaSelectedPhoneId(suggested || String(options?.[0]?.phone_id || ""));
  };

  const startMetaEmbeddedSignup = async () => {
    if (!session || loadingAction("meta_embedded_start")) return;
    try {
      setSubmitting("meta_embedded_start");
      setStatus({ message: "", type: "" });
      resetMetaSelection();
      const headers = await getAuthHeaders();
      const uiReturnUrl = typeof window !== "undefined"
        ? `${window.location.origin}${window.location.pathname}`
        : "";
      const res = await axios.post(
        `${API}/meta_embedded_signup/start`,
        {
          ui_return_url: uiReturnUrl,
          preferred_phone: isValidPhone(phone) ? phone : null,
        },
        { headers }
      );
      const authUrl = res?.data?.auth_url;
      if (!authUrl) {
        throw new Error("missing_auth_url");
      }
      if (typeof window !== "undefined") {
        window.location.assign(authUrl);
      }
    } catch (err) {
      console.error(err);
      const detail = err?.response?.data?.detail;
      setError(detail || t("meta_embedded_error_start"));
    } finally {
      setSubmitting("");
    }
  };

  const completeMetaEmbeddedSelection = async () => {
    if (!session || loadingAction("meta_embedded_complete_selection")) return;
    if (!metaSelectionToken || !metaSelectedPhoneId) {
      return setError(t("meta_embedded_select_phone_required"));
    }

    try {
      setSubmitting("meta_embedded_complete_selection");
      setStatus({ message: "", type: "" });
      resetSetupProgress();

      const runId = setupRunRef.current + 1;
      setupRunRef.current = runId;
      setWaSetupProgress((prev) => ({ ...prev, active: true, complete: false, timedOut: false }));

      const headers = await getAuthHeaders();
      const res = await axios.post(
        `${API}/meta_embedded_signup/complete_selection`,
        {
          selection_token: metaSelectionToken,
          wa_phone_id: metaSelectedPhoneId,
        },
        { headers }
      );
      const payload = res?.data || {};
      setWaConnected(true);
      setPhone(String(payload?.phone || phone || ""));
      setWaPhoneId(String(payload?.wa_phone_id || metaSelectedPhoneId || ""));
      setWaBusinessAccountId(String(payload?.wa_business_account_id || waBusinessAccountId || ""));
      resetMetaSelection();

      if (payload?.setup_progress) {
        applySetupProgressPayload(payload.setup_progress);
      }

      if (Boolean(payload?.setup_complete)) {
        setSuccess(t("wa_setup_success_ready"));
      } else {
        setSuccess(t("wa_setup_connected_waiting"));
        const pollResult = await pollSetupProgress(headers, runId);
        if (pollResult?.completed) {
          setSuccess(t("wa_setup_success_ready"));
        } else if (pollResult?.cancelled) {
          return;
        } else if (pollResult?.timeout) {
          const fallbackSuggestion = t("wa_setup_timeout_suggestion_retry");
          const firstSuggestion = Array.isArray(pollResult?.payload?.suggestions)
            ? pollResult.payload.suggestions[0]
            : "";
          setWaSetupProgress((prev) => ({ ...prev, active: false, timedOut: true }));
          setError(`${t("wa_setup_timeout")} ${firstSuggestion || fallbackSuggestion}`);
        } else if (pollResult?.error) {
          setError(`${t("wa_setup_error_progress")}: ${pollResult.error}`);
        } else {
          setError(t("wa_setup_error_progress"));
        }
      }
    } catch (err) {
      console.error(err);
      const detail = err?.response?.data?.detail;
      setWaSetupProgress((prev) => ({ ...prev, active: false, lastError: detail || "" }));
      setError(detail || t("meta_embedded_select_phone_error"));
    } finally {
      setSubmitting("");
    }
  };

  const applySetupProgressPayload = (payload, options = {}) => {
    const setupComplete = Boolean(payload?.setup_complete);
    setWaSetupProgress({
      active: options.forceActive === true ? true : !setupComplete,
      complete: setupComplete,
      timedOut: Boolean(options.timedOut),
      steps: Array.isArray(payload?.steps) ? payload.steps : [],
      suggestions: Array.isArray(payload?.suggestions) ? payload.suggestions : [],
      phoneStatus: payload?.phone_status || null,
      lastError: options.lastError || "",
    });
  };

  const pollSetupProgress = async (headers, runId) => {
    const deadline = Date.now() + WA_SETUP_TIMEOUT_MS;
    let latestPayload = null;

    while (Date.now() < deadline && runId === setupRunRef.current) {
      await new Promise((resolve) => setTimeout(resolve, WA_SETUP_POLL_MS));
      if (runId !== setupRunRef.current) break;

      try {
        const progressRes = await axios.get(`${API}/whatsapp_setup_progress`, { headers });
        latestPayload = progressRes?.data || null;
        applySetupProgressPayload(latestPayload);

        if (Boolean(latestPayload?.setup_complete)) {
          return { completed: true, payload: latestPayload };
        }
      } catch (err) {
        const detail = err?.response?.data?.detail || t("wa_setup_error_progress");
        setWaSetupProgress((prev) => ({ ...prev, active: false, lastError: detail }));
        return { completed: false, error: detail, payload: latestPayload };
      }
    }

    if (runId !== setupRunRef.current) {
      return { completed: false, cancelled: true, payload: latestPayload };
    }

    return { completed: false, timeout: true, payload: latestPayload };
  };

  const getProgressStepTitle = (key) => {
    if (key === "channel_ready") return t("wa_setup_step_channel_ready");
    if (key === "waba_phone_binding") return t("wa_setup_step_binding");
    if (key === "waba_subscription") return t("wa_setup_step_subscription");
    if (key === "phone_approval") return t("wa_setup_step_phone_status");
    return key;
  };

  const handleConnectWhatsApp = async () => {
    if (!session || loadingAction("wa_connect")) return;

    if (!isValidPhone(phone)) return setError(t("wa_error_phone"));
    if (!isValidPhoneId(waPhoneId)) return setError(t("wa_error_phone_id"));
    if (!isValidToken(waToken)) return setError(t("wa_error_token"));
    if (!isValidWabaId(waBusinessAccountId)) return setError(t("wa_error_waba_id"));

    try {
      setSubmitting("wa_connect");
      setStatus({ message: "", type: "" });
      resetSetupProgress();

      const runId = setupRunRef.current + 1;
      setupRunRef.current = runId;
      setWaSetupProgress((prev) => ({ ...prev, active: true, complete: false, timedOut: false }));

      const headers = await getAuthHeaders();
      const linkRes = await axios.post(
        `${API}/link_whatsapp`,
        {
          email: session.user.email,
          phone,
          provider,
          wa_phone_id: waPhoneId,
          wa_token: waToken,
          wa_business_account_id: waBusinessAccountId || null,
        },
        { headers }
      );
      const linkData = linkRes?.data || {};

      setWaConnected(true);
      setWaToken("");

      if (linkData?.setup_progress) {
        applySetupProgressPayload(linkData.setup_progress);
      }

      if (Boolean(linkData?.setup_complete)) {
        setSuccess(t("wa_setup_success_ready"));
      } else {
        setSuccess(t("wa_setup_connected_waiting"));
        const pollResult = await pollSetupProgress(headers, runId);
        if (pollResult?.completed) {
          setSuccess(t("wa_setup_success_ready"));
        } else if (pollResult?.cancelled) {
          return;
        } else if (pollResult?.timeout) {
          const fallbackSuggestion = t("wa_setup_timeout_suggestion_retry");
          const firstSuggestion = Array.isArray(pollResult?.payload?.suggestions)
            ? pollResult.payload.suggestions[0]
            : "";
          setWaSetupProgress((prev) => ({ ...prev, active: false, timedOut: true }));
          setError(`${t("wa_setup_timeout")} ${firstSuggestion || fallbackSuggestion}`);
        } else if (pollResult?.error) {
          setError(`${t("wa_setup_error_progress")}: ${pollResult.error}`);
        } else {
          setError(t("wa_setup_error_progress"));
        }
      }

      if (clientId) {
        void trackClientEvent({
          clientId,
          name: "Funnel_Channel_Connected",
          category: "funnel",
          label: "meta_apps_whatsapp",
          value: provider,
          eventKey: "funnel_channel_connected:meta_apps_whatsapp",
          metadata: { channel: "whatsapp", provider: "meta" },
          dedupeLocal: true,
        });
      }
    } catch (err) {
      console.error(err);
      const detail = err?.response?.data?.detail;
      setWaSetupProgress((prev) => ({ ...prev, active: false, lastError: detail || "" }));
      setError(detail || t("wa_error_linking"));
    } finally {
      setSubmitting("");
    }
  };

  const handleDisconnectWhatsApp = async () => {
    if (!session || loadingAction("wa_disconnect")) return;
    if (!window.confirm(t("wa_confirm_disconnect"))) return;

    try {
      setSubmitting("wa_disconnect");
      setStatus({ message: "", type: "" });
      const headers = await getAuthHeaders();
      await axios.post(
        `${API}/unlink_whatsapp`,
        { auth_user_id: session.user.id },
        { headers }
      );
      setupRunRef.current += 1;
      setPhone("");
      setWaPhoneId("");
      setWaToken("");
      setWaBusinessAccountId("");
      setWaConnected(false);
      setWaConnectionMethod("meta_embedded");
      resetSetupProgress();
      setSuccess(t("wa_disconnected"));
    } catch (err) {
      console.error(err);
      setError(t("wa_error_unlinking"));
    } finally {
      setSubmitting("");
    }
  };

  const connectSocialChannel = async (channelType) => {
    if (!clientId) return;
    const recipientId = channelType === "messenger" ? messengerRecipientId : instagramRecipientId;
    const isConnected = channelType === "messenger" ? messengerConnected : instagramConnected;

    if (!isValidMetaRecipientId(recipientId)) {
      return setError(t("meta_apps_error_recipient"));
    }

    if (!isConnected && !isValidToken(metaPageToken)) {
      return setError(t("meta_apps_error_token"));
    }

    try {
      setSubmitting(`${channelType}_connect`);
      setStatus({ message: "", type: "" });
      const headers = await getAuthHeaders();
      await axios.post(
        `${API}/channels/meta_app_channel`,
        {
          client_id: clientId,
          channel_type: channelType,
          recipient_id: recipientId.trim(),
          access_token: metaPageToken.trim() || null,
          provider: "meta",
        },
        { headers }
      );

      if (channelType === "messenger") setMessengerConnected(true);
      if (channelType === "instagram") setInstagramConnected(true);
      setMetaPageToken("");
      setSuccess(channelType === "messenger" ? t("meta_apps_messenger_connected") : t("meta_apps_instagram_connected"));

      if (clientId) {
        void trackClientEvent({
          clientId,
          name: "Funnel_Channel_Connected",
          category: "funnel",
          label: `meta_apps_${channelType}`,
          value: "meta",
          eventKey: `funnel_channel_connected:meta_apps_${channelType}`,
          metadata: { channel: channelType, provider: "meta" },
          dedupeLocal: true,
        });
      }
    } catch (err) {
      console.error(err);
      const detail = err?.response?.data?.detail;
      setError(detail || t("meta_apps_error_linking"));
    } finally {
      setSubmitting("");
    }
  };

  const disconnectSocialChannel = async (channelType) => {
    if (!clientId) return;
    const key = `${channelType}_disconnect`;
    const confirmCopy = channelType === "messenger"
      ? t("meta_apps_confirm_disconnect_messenger")
      : t("meta_apps_confirm_disconnect_instagram");
    if (!window.confirm(confirmCopy)) return;

    try {
      setSubmitting(key);
      setStatus({ message: "", type: "" });
      const headers = await getAuthHeaders();
      await axios.post(
        `${API}/channels/meta_app_channel/disconnect`,
        {
          client_id: clientId,
          channel_type: channelType,
          provider: "meta",
        },
        { headers }
      );
      if (channelType === "messenger") setMessengerConnected(false);
      if (channelType === "instagram") setInstagramConnected(false);
      setSuccess(channelType === "messenger" ? t("meta_apps_messenger_disconnected") : t("meta_apps_instagram_disconnected"));
    } catch (err) {
      console.error(err);
      const detail = err?.response?.data?.detail;
      setError(detail || t("meta_apps_error_unlinking"));
    } finally {
      setSubmitting("");
    }
  };

  const showError = (field, value) => {
    if (!touched[field]) return null;
    if (field === "phone" && !isValidPhone(value)) return <p className="ia-help-error">{t("wa_error_phone")}</p>;
    if (field === "waPhoneId" && !isValidPhoneId(value)) return <p className="ia-help-error">{t("wa_error_phone_id")}</p>;
    if (field === "waToken" && !waConnected && !isValidToken(value)) return <p className="ia-help-error">{t("wa_error_token")}</p>;
    if (field === "waBusinessAccountId" && !isValidWabaId(value)) return <p className="ia-help-error">{t("wa_error_waba_id")}</p>;
    if (field === "metaPageToken" && value && !isValidToken(value)) return <p className="ia-help-error">{t("meta_apps_error_token")}</p>;
    if (field === "messengerRecipientId" && value && !isValidMetaRecipientId(value)) return <p className="ia-help-error">{t("meta_apps_error_recipient")}</p>;
    if (field === "instagramRecipientId" && value && !isValidMetaRecipientId(value)) return <p className="ia-help-error">{t("meta_apps_error_recipient")}</p>;
    return null;
  };

  if (loading) {
    return (
      <div className="ia-page">
        <div className="ia-loader">
          <div className="ia-spinner" />
          <p style={{ color: "#274472", marginTop: "1rem" }}>{t("loading")}</p>
        </div>
      </div>
    );
  }

  const disableConnectWa =
    loadingAction("wa_connect") ||
    !isValidPhone(phone) ||
    !isValidPhoneId(waPhoneId) ||
    !isValidToken(waToken) ||
    !isValidWabaId(waBusinessAccountId);

  const displayedPhone = waConnected ? maskSensitive(phone, 4, 3) : phone;
  const displayedWaPhoneId = waConnected ? maskSensitive(waPhoneId, 3, 3) : waPhoneId;
  const displayedWabaId = waConnected ? maskSensitive(waBusinessAccountId, 3, 3) : waBusinessAccountId;
  const showEmbeddedWhatsAppFlow = !waConnected && waConnectionMethod === "meta_embedded";
  const showManualWhatsAppFlow = waConnected || waConnectionMethod === "manual";
  const showSetupProgressCard =
    waSetupProgress.active
    || waSetupProgress.complete
    || waSetupProgress.timedOut
    || Boolean(waSetupProgress.lastError)
    || (waSetupProgress.steps || []).length > 0;

  return (
    <div className="ia-page">
      <div className="ia-shell ia-whatsapp-shell">
        <section className="ia-card" style={{ marginBottom: "1rem" }}>
          <h2 className="ia-header-title">{t("meta_apps_integration_title")}</h2>
          <p className="ia-help-text">{t("meta_apps_integration_subtitle")}</p>
          <div className="ia-note" style={{ marginTop: "0.9rem" }}>
            <strong>{t("meta_apps_required_data_title")}</strong>
            <ul className="ia-list" style={{ marginTop: "0.35rem" }}>
              <li>{t("meta_apps_required_whatsapp")}</li>
              <li>{t("meta_apps_required_messenger")}</li>
              <li>{t("meta_apps_required_instagram")}</li>
            </ul>
          </div>
        </section>

        <section className="ia-card" style={{ marginBottom: "1rem" }}>
          <div style={{ display: "flex", justifyContent: "space-between", gap: "0.75rem", flexWrap: "wrap" }}>
            <h3 className="ia-header-title">{t("whatsapp")}</h3>
            {waConnected ? <span className="ia-badge success">{t("connected")}</span> : null}
          </div>

          {!waConnected ? (
            <div className="ia-form-field" style={{ marginTop: "0.9rem" }}>
              <label className="ia-form-label">{t("wa_connection_method_label")}</label>
              <select
                className="ia-form-input"
                value={waConnectionMethod}
                onChange={(e) => setWaConnectionMethod(e.target.value)}
              >
                <option value="meta_embedded">{t("wa_connection_method_meta_embedded")}</option>
                <option value="manual">{t("wa_connection_method_manual")}</option>
              </select>
              <p className="ia-help-text" style={{ marginTop: "0.45rem", marginBottom: 0 }}>
                {waConnectionMethod === "meta_embedded"
                  ? t("wa_connection_method_meta_embedded_help")
                  : t("wa_connection_method_manual_help")}
              </p>
            </div>
          ) : null}

          {showEmbeddedWhatsAppFlow ? (
            <div className="ia-note" style={{ marginTop: "0.65rem" }}>
              <p style={{ marginTop: 0, marginBottom: "0.55rem" }}>{t("meta_embedded_connect_subtitle")}</p>
              <button
                type="button"
                className="ia-button"
                style={{ backgroundColor: "#4a90e2", color: "#fff" }}
                onClick={startMetaEmbeddedSignup}
                disabled={loadingAction("meta_embedded_start")}
              >
                {loadingAction("meta_embedded_start") ? t("meta_embedded_connecting") : t("meta_embedded_connect")}
              </button>
            </div>
          ) : null}

          {showEmbeddedWhatsAppFlow && metaSelectionOptions.length ? (
            <div className="ia-note" style={{ marginTop: "0.75rem" }}>
              <p style={{ marginTop: 0, marginBottom: "0.55rem" }}>{t("meta_embedded_select_phone_prompt")}</p>
              <div className="ia-form-field" style={{ marginBottom: "0.65rem" }}>
                <label className="ia-form-label">{t("meta_embedded_select_phone_label")}</label>
                <select
                  className="ia-form-input"
                  value={metaSelectedPhoneId}
                  onChange={(e) => setMetaSelectedPhoneId(e.target.value)}
                >
                  {metaSelectionOptions.map((option) => {
                    const phoneLabel = option?.display_phone_number || option?.phone_id;
                    const verifiedName = option?.verified_name ? ` · ${option.verified_name}` : "";
                    const quality = option?.quality_rating ? ` · ${option.quality_rating}` : "";
                    return (
                      <option key={option?.phone_id || ""} value={option?.phone_id || ""}>
                        {`${phoneLabel}${verifiedName}${quality}`}
                      </option>
                    );
                  })}
                </select>
              </div>
              <button
                type="button"
                className="ia-button"
                style={{ backgroundColor: "#2eb39a", color: "#fff" }}
                onClick={completeMetaEmbeddedSelection}
                disabled={loadingAction("meta_embedded_complete_selection") || !metaSelectedPhoneId}
              >
                {loadingAction("meta_embedded_complete_selection")
                  ? t("meta_embedded_select_phone_processing")
                  : t("meta_embedded_select_phone_confirm")}
              </button>
            </div>
          ) : null}

          {showManualWhatsAppFlow ? (
            <>
              {!waConnected ? (
                <div className="ia-note" style={{ marginTop: "0.75rem" }}>
                  <p style={{ margin: 0 }}>{t("wa_manual_setup_subtitle")}</p>
                </div>
              ) : null}

              <div className="ia-form-grid" style={{ marginTop: "0.9rem" }}>
                <div className="ia-form-field">
                  <label className="ia-form-label">{t("wa_label_phone")}</label>
                  <input
                    className="ia-form-input"
                    type="text"
                    value={displayedPhone}
                    placeholder="+5215512345678"
                    disabled={waConnected}
                    onChange={(e) => setPhone(e.target.value)}
                    onBlur={() => setTouched((prev) => ({ ...prev, phone: true }))}
                  />
                  {showError("phone", phone)}
                </div>

                <div className="ia-form-field">
                  <label className="ia-form-label">{t("whatsapp_phone_number_id")}</label>
                  <input
                    className="ia-form-input"
                    type="text"
                    value={displayedWaPhoneId}
                    disabled={waConnected}
                    onChange={(e) => setWaPhoneId(e.target.value)}
                    onBlur={() => setTouched((prev) => ({ ...prev, waPhoneId: true }))}
                  />
                  {showError("waPhoneId", waPhoneId)}
                </div>

                <div className="ia-form-field">
                  <label className="ia-form-label">{t("whatsapp_business_account_id")}</label>
                  <input
                    className="ia-form-input"
                    type="text"
                    value={displayedWabaId}
                    placeholder={t("wa_placeholder_waba_id")}
                    disabled={waConnected}
                    onChange={(e) => setWaBusinessAccountId(e.target.value)}
                    onBlur={() => setTouched((prev) => ({ ...prev, waBusinessAccountId: true }))}
                  />
                  {showError("waBusinessAccountId", waBusinessAccountId)}
                </div>

                {!waConnected ? (
                  <div className="ia-form-field">
                    <label className="ia-form-label">{t("permanent_access_token")}</label>
                    <input
                      className="ia-form-input"
                      type="password"
                      value={waToken}
                      onChange={(e) => setWaToken(e.target.value)}
                      onBlur={() => setTouched((prev) => ({ ...prev, waToken: true }))}
                    />
                    {showError("waToken", waToken)}
                  </div>
                ) : null}
              </div>
            </>
          ) : null}

          <div className="ia-inline-actions" style={{ marginTop: "1rem" }}>
            {!waConnected && showManualWhatsAppFlow ? (
              <button
                type="button"
                className="ia-button"
                style={{ backgroundColor: "#2eb39a", color: "#fff", opacity: disableConnectWa ? 0.6 : 1 }}
                onClick={handleConnectWhatsApp}
                disabled={disableConnectWa}
              >
                {loadingAction("wa_connect") ? t("connecting") : t("connect_whatsapp")}
              </button>
            ) : null}

            {waConnected ? (
              <button
                type="button"
                className="ia-button ia-button-ghost"
                onClick={handleDisconnectWhatsApp}
                disabled={loadingAction("wa_disconnect")}
              >
                {loadingAction("wa_disconnect") ? t("processing") : t("disconnect_whatsapp")}
              </button>
            ) : null}
          </div>
        </section>

        {showSetupProgressCard ? (
          <section className="ia-card ia-setup-progress-card" style={{ marginBottom: "1rem" }}>
            <div className="ia-setup-progress-header">
              <h3 className="ia-header-title" style={{ marginBottom: 0 }}>{t("wa_setup_progress_title")}</h3>
              {waSetupProgress.active ? <div className="ia-spinner ia-spinner-sm" /> : null}
            </div>
            <p className="ia-help-text" style={{ marginTop: "0.5rem" }}>
              {waSetupProgress.active ? t("wa_setup_progress_subtitle") : t("wa_setup_progress_snapshot")}
            </p>

            {(waSetupProgress.steps || []).length ? (
              <ul className="ia-setup-steps">
                {waSetupProgress.steps.map((step, index) => (
                  <li key={`${step?.key || "step"}-${index}`} className="ia-setup-step-row">
                    <span className={`ia-setup-step-dot ia-setup-step-${step?.state || "pending"}`} />
                    <div>
                      <p className="ia-setup-step-title">{getProgressStepTitle(step?.key)}</p>
                      <p className="ia-setup-step-detail">{step?.detail || ""}</p>
                    </div>
                  </li>
                ))}
              </ul>
            ) : null}

            {waSetupProgress?.phoneStatus?.status ? (
              <p className="ia-help-text" style={{ marginTop: "0.7rem" }}>
                {waSetupProgress.phoneStatus.approved
                  ? t("wa_setup_phone_status_approved").replace("{status}", waSetupProgress.phoneStatus.status)
                  : t("wa_setup_phone_status_pending").replace("{status}", waSetupProgress.phoneStatus.status)}
              </p>
            ) : null}

            {(waSetupProgress.timedOut || waSetupProgress.lastError || (waSetupProgress.suggestions || []).length) ? (
              <div className="ia-note ia-setup-progress-warning" style={{ marginTop: "0.7rem" }}>
                <strong>{waSetupProgress.timedOut ? t("wa_setup_timeout_title") : t("wa_setup_recommendations_title")}</strong>
                {(waSetupProgress.suggestions || []).length ? (
                  <ul className="ia-list" style={{ marginTop: "0.4rem" }}>
                    {waSetupProgress.suggestions.map((suggestion, index) => (
                      <li key={`suggestion-${index}`}>{suggestion}</li>
                    ))}
                  </ul>
                ) : (
                  <p style={{ marginTop: "0.4rem", marginBottom: 0 }}>
                    {waSetupProgress.lastError || t("wa_setup_timeout_suggestion_retry")}
                  </p>
                )}
              </div>
            ) : null}
          </section>
        ) : null}

        <section className="ia-card">
          <div style={{ display: "flex", justifyContent: "space-between", gap: "0.75rem", flexWrap: "wrap" }}>
            <h3 className="ia-header-title">{t("meta_apps_social_title")}</h3>
          </div>
          <p className="ia-help-text">{t("meta_apps_social_subtitle")}</p>

          <details className="ia-note" style={{ marginTop: "0.9rem" }}>
            <summary style={{ cursor: "pointer", fontWeight: 600 }}>
              {t("meta_apps_messenger_coming_soon_title")}
            </summary>
            <p className="ia-help-text" style={{ marginTop: "0.55rem", marginBottom: 0 }}>
              {t("meta_apps_messenger_coming_soon_body")}
            </p>
          </details>

          <details className="ia-note" style={{ marginTop: "0.9rem" }}>
            <summary style={{ cursor: "pointer", fontWeight: 600 }}>
              {t("meta_apps_instagram_coming_soon_title")}
            </summary>
            <p className="ia-help-text" style={{ marginTop: "0.55rem", marginBottom: 0 }}>
              {t("meta_apps_instagram_coming_soon_body")}
            </p>
          </details>
        </section>

        {status.message ? (
          <p
            className="ia-status-line"
            style={{ color: status.type === "error" ? "#f87171" : "#2eb39a", marginTop: "0.9rem", marginBottom: 0 }}
          >
            {status.message}
          </p>
        ) : null}
      </div>
    </div>
  );
}
