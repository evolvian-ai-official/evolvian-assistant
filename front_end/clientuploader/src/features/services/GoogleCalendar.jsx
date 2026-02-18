// src/features/calendar/GoogleCalendarSettings.jsx
// Evolvian Premium Light — con control de activación calendar_status
import { useEffect, useState } from "react";
import { useClientId } from "../../hooks/useClientId";
import { toast } from "../../components/ui/use-toast";
import { authFetch } from "../../lib/authFetch";
import { useLanguage } from "../../contexts/LanguageContext";
import CreateAppointment from "./CreateAppointments";
import "../../components/ui/internal-admin-responsive.css";


export default function GoogleCalendarSettings() {
  const { t } = useLanguage();
  // --- Toggle principal (activar o no el calendario) ---
  const [calendarStatus, setCalendarStatus] = useState("inactive");

  // --- Toggle interno (Appointments | Calendar Setup) ---
  const [view, setView] = useState("appointments");
  const [isMobile, setIsMobile] = useState(false);
  useEffect(() => {
    const onResize = () => setIsMobile(window.innerWidth < 768);
    onResize();
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  const clientId = useClientId();

  // --- Settings (estado de UI) ---
  const [selectedDays, setSelectedDays] = useState(["Mon", "Tue", "Wed", "Thu", "Fri"]);
  const [timeRange, setTimeRange] = useState({ start: "09:00", end: "18:00" });
  const [slotDuration, setSlotDuration] = useState(30);
  const [minNoticeHours, setMinNoticeHours] = useState(4);
  const [maxDaysAhead, setMaxDaysAhead] = useState(14);
  const [bufferTime, setBufferTime] = useState(15);
  const [allowSameDay, setAllowSameDay] = useState(true);
  const [timezone, setTimezone] = useState("America/Mexico_City");
  const [showAgendaInChatWidget, setShowAgendaInChatWidget] = useState(false);
  const [aiSchedulingChatEnabled, setAiSchedulingChatEnabled] = useState(true);
  const [aiSchedulingWhatsappEnabled, setAiSchedulingWhatsappEnabled] = useState(true);
  const [loadingSettings, setLoadingSettings] = useState(false);
  const [togglingStatus, setTogglingStatus] = useState(false);
  const [saving, setSaving] = useState(false);
  const [lastSavedSnapshot, setLastSavedSnapshot] = useState(null);
  const [googleConnected, setGoogleConnected] = useState(false);
  const [googleConnectedEmail, setGoogleConnectedEmail] = useState("");
  const [loadingGoogleStatus, setLoadingGoogleStatus] = useState(false);
  const [disconnectingGoogle, setDisconnectingGoogle] = useState(false);

  const days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
  const parseBool = (value, fallback = true) => {
    if (value === null || value === undefined) return fallback;
    if (typeof value === "boolean") return value;
    if (typeof value === "string") {
      const normalized = value.trim().toLowerCase();
      if (["true", "1", "yes", "on"].includes(normalized)) return true;
      if (["false", "0", "no", "off"].includes(normalized)) return false;
    }
    return Boolean(value);
  };
  const normalizeDays = (value) => {
    const defaultDays = ["Mon", "Tue", "Wed", "Thu", "Fri"];
    if (Array.isArray(value)) {
      const cleaned = value.filter((d) => days.includes(String(d)));
      return cleaned.length ? cleaned : defaultDays;
    }
    if (typeof value === "string") {
      const stripped = value.replace(/[{}"]/g, "");
      const arr = stripped
        .split(",")
        .map((d) => d.trim())
        .filter(Boolean)
        .map((d) => {
          const key = d.toLowerCase();
          if (key.startsWith("mon")) return "Mon";
          if (key.startsWith("tue")) return "Tue";
          if (key.startsWith("wed")) return "Wed";
          if (key.startsWith("thu")) return "Thu";
          if (key.startsWith("fri")) return "Fri";
          if (key.startsWith("sat")) return "Sat";
          if (key.startsWith("sun")) return "Sun";
          return null;
        })
        .filter(Boolean);
      return arr.length ? arr : defaultDays;
    }
    return defaultDays;
  };
  const toggleDay = (day) =>
    setSelectedDays((prev) => (prev.includes(day) ? prev.filter((d) => d !== day) : [...prev, day]));

  const buildSnapshot = (source = null) => {
    if (source) {
      return {
        calendar_status: source.calendar_status || "inactive",
        selected_days: [...normalizeDays(source.selected_days)].sort(),
        start_time: source.start_time ?? "09:00",
        end_time: source.end_time ?? "18:00",
        slot_duration_minutes: Number(source.slot_duration_minutes ?? 30),
        min_notice_hours: Number(source.min_notice_hours ?? 4),
        max_days_ahead: Number(source.max_days_ahead ?? 14),
        buffer_minutes: Number(source.buffer_minutes ?? 15),
        allow_same_day: parseBool(source.allow_same_day, true),
        timezone: source.timezone ?? "America/Mexico_City",
        show_agenda_in_chat_widget: parseBool(source.show_agenda_in_chat_widget, false),
        ai_scheduling_chat_enabled: parseBool(source.ai_scheduling_chat_enabled, true),
        ai_scheduling_whatsapp_enabled: parseBool(source.ai_scheduling_whatsapp_enabled, true),
      };
    }

    return {
      calendar_status: calendarStatus,
      selected_days: [...normalizeDays(selectedDays)].sort(),
      start_time: timeRange.start,
      end_time: timeRange.end,
      slot_duration_minutes: Number(slotDuration),
      min_notice_hours: Number(minNoticeHours),
      max_days_ahead: Number(maxDaysAhead),
      buffer_minutes: Number(bufferTime),
      allow_same_day: parseBool(allowSameDay, true),
      timezone,
      show_agenda_in_chat_widget: parseBool(showAgendaInChatWidget, false),
      ai_scheduling_chat_enabled: parseBool(aiSchedulingChatEnabled, true),
      ai_scheduling_whatsapp_enabled: parseBool(aiSchedulingWhatsappEnabled, true),
    };
  };

  const applySettingsToState = (source = {}) => {
    setCalendarStatus(source.calendar_status || "inactive");
    setSelectedDays(normalizeDays(source.selected_days));
    setTimeRange({ start: source.start_time ?? "09:00", end: source.end_time ?? "18:00" });
    setSlotDuration(Number(source.slot_duration_minutes ?? 30));
    setMinNoticeHours(Number(source.min_notice_hours ?? 4));
    setMaxDaysAhead(Number(source.max_days_ahead ?? 14));
    setBufferTime(Number(source.buffer_minutes ?? 15));
    setAllowSameDay(parseBool(source.allow_same_day, true));
    setTimezone(source.timezone ?? "America/Mexico_City");
    setShowAgendaInChatWidget(parseBool(source.show_agenda_in_chat_widget, false));
    setAiSchedulingChatEnabled(parseBool(source.ai_scheduling_chat_enabled, true));
    setAiSchedulingWhatsappEnabled(parseBool(source.ai_scheduling_whatsapp_enabled, true));
    setLastSavedSnapshot(buildSnapshot(source));
  };

  // Forzar estilo claro
  useEffect(() => {
    const id = "evo-calendar-settings-style";
    if (!document.getElementById(id)) {
      const style = document.createElement("style");
      style.id = id;
      style.textContent = `
        @keyframes evoSkeletonPulse {
          0% { opacity: 0.55; }
          50% { opacity: 1; }
          100% { opacity: 0.55; }
        }

        #evo-calendar-settings select,
        #evo-calendar-settings input[type="time"],
        #evo-calendar-settings input[type="number"],
        #evo-calendar-settings input[type="text"] {
          background-color: #FFFFFF !important;
          color: #274472 !important;
          border: 1px solid #EDEDED;
          border-radius: 8px;
        }
        #evo-calendar-settings option {
          background-color: #FFFFFF;
          color: #274472;
        }
      `;
      document.head.appendChild(style);
    }
  }, []);

  // Cargar settings
  useEffect(() => {
    if (!clientId) return;
    const backendUrl =
    import.meta.env.VITE_API_URL ||
    (window.location.hostname === "localhost"
      ? "http://localhost:8001"
      : "https://evolvian-assistant.onrender.com");

    const loadSettings = async () => {
      try {
        setLoadingSettings(true);
        const res = await authFetch(`${backendUrl}/calendar/settings?client_id=${clientId}`);
        if (!res.ok) throw new Error(t("google_calendar_load_settings_error"));
        const s = await res.json();
        applySettingsToState(s);
      } catch {
        toast({ title: t("error"), description: t("google_calendar_load_settings_error"), variant: "destructive" });
      } finally {
        setLoadingSettings(false);
      }
    };

    loadSettings();
  }, [clientId, t]);

  // --- Cambiar estado del calendario ---
  const handleToggleCalendar = async () => {
    if (!clientId) return;
    const backendUrl =
    import.meta.env.VITE_API_URL ||
    (window.location.hostname === "localhost"
      ? "http://localhost:8001"
      : "https://evolvian-assistant.onrender.com");

    const newStatus = calendarStatus === "active" ? "inactive" : "active";

    try {
      setTogglingStatus(true);
      const res = await authFetch(`${backendUrl}/calendar/status?client_id=${clientId}&status=${newStatus}`, {
        method: "PATCH",
      });
      if (!res.ok) throw new Error(t("failed_toggle_status"));
      const data = await res.json();
      setCalendarStatus(data.calendar_status);

      const refreshed = await authFetch(`${backendUrl}/calendar/settings?client_id=${clientId}`);
      if (!refreshed.ok) throw new Error(t("google_calendar_load_settings_error"));
      const settings = await refreshed.json();
      applySettingsToState(settings);

      toast({
        title: t("calendar_updated"),
        description: `${t("calendar_is_now")} ${data.calendar_status === "active" ? t("enabled") : t("disabled")}.`,
      });
    } catch {
      toast({ title: t("error"), description: t("google_calendar_update_status_error"), variant: "destructive" });
    } finally {
      setTogglingStatus(false);
    }
  };

  const handleSave = async () => {
    if (!clientId) return;
    try {
      setSaving(true);
      const backendUrl =
      import.meta.env.VITE_API_URL ||
      (window.location.hostname === "localhost"
        ? "http://localhost:8001"
        : "https://evolvian-assistant.onrender.com");

      const payload = {
        client_id: clientId,
        calendar_status: calendarStatus,
        selected_days: normalizeDays(selectedDays),
        start_time: timeRange.start,
        end_time: timeRange.end,
        slot_duration_minutes: Number(slotDuration),
        min_notice_hours: Number(minNoticeHours),
        max_days_ahead: Number(maxDaysAhead),
        buffer_minutes: Number(bufferTime),
        allow_same_day: parseBool(allowSameDay, true),
        timezone,
        show_agenda_in_chat_widget: parseBool(showAgendaInChatWidget, false),
        ai_scheduling_chat_enabled: parseBool(aiSchedulingChatEnabled, true),
        ai_scheduling_whatsapp_enabled: parseBool(aiSchedulingWhatsappEnabled, true),
      };
      const res = await authFetch(`${backendUrl}/calendar/settings`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error(t("save_failed"));
      let postData = null;
      try {
        postData = await res.json();
      } catch {
        postData = null;
      }

      // Prefer POST response to update UI immediately and avoid transient blue/freeze states.
      const savedSettings = postData?.settings && typeof postData.settings === "object"
        ? postData.settings
        : payload;
      applySettingsToState(savedSettings);

      // Best-effort refresh from backend, without blocking the UI.
      try {
        const refreshed = await authFetch(`${backendUrl}/calendar/settings?client_id=${clientId}`);
        if (refreshed.ok) {
          const s = await refreshed.json();
          applySettingsToState(s);
        }
      } catch {
        // no-op
      }
      toast({ title: t("settings_saved_title"), description: t("google_calendar_settings_updated") });
    } catch {
      toast({ title: t("error"), description: t("google_calendar_save_settings_error"), variant: "destructive" });
    } finally {
      setSaving(false);
    }
  };

  const isDisabled = calendarStatus !== "active";
  const isDirty =
    Boolean(lastSavedSnapshot) &&
    JSON.stringify(buildSnapshot()) !== JSON.stringify(lastSavedSnapshot);

  const backendUrl =
    import.meta.env.VITE_API_URL ||
    (window.location.hostname === "localhost"
      ? "http://localhost:8001"
      : "https://evolvian-assistant.onrender.com");

  const fetchGoogleConnectionStatus = async () => {
    if (!clientId) return;
    try {
      setLoadingGoogleStatus(true);
      const res = await authFetch(`${backendUrl}/api/auth/google_calendar?client_id=${clientId}`);
      if (!res.ok) throw new Error("status_failed");
      const data = await res.json();
      setGoogleConnected(Boolean(data?.connected));
      setGoogleConnectedEmail(data?.connected_email || "");
    } catch {
      setGoogleConnected(false);
      setGoogleConnectedEmail("");
    } finally {
      setLoadingGoogleStatus(false);
    }
  };

  useEffect(() => {
    fetchGoogleConnectionStatus();
  }, [clientId]);

  const handleConnectGoogleCalendar = () => {
    if (!clientId) return;
    window.location.href = `${backendUrl}/api/auth/google_calendar/init?client_id=${encodeURIComponent(clientId)}`;
  };

  const handleDisconnectGoogleCalendar = async () => {
    if (!clientId) return;
    try {
      setDisconnectingGoogle(true);
      const res = await authFetch(
        `${backendUrl}/api/auth/google_calendar/disconnect?client_id=${encodeURIComponent(clientId)}`,
        { method: "POST" }
      );
      if (!res.ok) throw new Error("disconnect_failed");
      setGoogleConnected(false);
      setGoogleConnectedEmail("");
      toast({ title: "Google Calendar", description: "Sincronización desconectada." });
    } catch {
      toast({ title: t("error"), description: t("google_calendar_disconnect_failed"), variant: "destructive" });
    } finally {
      setDisconnectingGoogle(false);
      fetchGoogleConnectionStatus();
    }
  };

  return (
    <div id="evo-calendar-settings" className="ia-page" style={pageStyle}>
      <div className="ia-shell ia-services-shell" style={{ maxWidth: 1200 }}>
        {/* Header */}
        <div style={headerRow}>
          <img src="/logo-evolvian.svg" alt="Evolvian Logo" style={{ width: 56, height: 56, borderRadius: "50%" }} />
          <div>
            <h1 style={titleStyle}>🗓️ {t("easy_appointments_title")}</h1>
            <p style={subtitleStyle}>{t("easy_appointments_subtitle")}</p>
          </div>
        </div>


        

        {/* Toggle Appointments / Calendar Setup */}
        <div style={toggleContainer(isMobile)}>
          <button
            onClick={() => setView("appointments")}
            style={{
              ...toggleButton,
              backgroundColor: view === "appointments" ? "#A3D9B1" : "#FFFFFF",
              color: "#274472",
              borderColor: view === "appointments" ? "#A3D9B1" : "#EDEDED",
              boxShadow: view === "appointments" ? "0 4px 10px rgba(163, 217, 177, 0.25)" : "none",
            }}
          >
            {t("appointments_nav") || "Appointments"}
          </button>

          <button
            onClick={() => setView("settings")}
            style={{
              ...toggleButton,
              backgroundColor: view === "settings" ? "#FFF7EA" : "#FFFFFF",
              color: "#274472",
              borderColor: view === "settings" ? "#F5A623" : "#EDEDED",
            }}
          >
            Calendar Setup
          </button>
        </div>



       
        

        {/* ===== VIEWS ===== */}

          {view === "appointments" && (
            <div
              style={{
                opacity: isDisabled ? 0.5 : 1,
                pointerEvents: isDisabled ? "none" : "auto",
              }}
            >
              <CreateAppointment disabled={isDisabled} />
            </div>
          )}

          {view === "settings" && (
            <div>
              <section style={sectionStyle}>
                <h3 style={sectionTitle}>📅 {t("appointments_nav") || "Appointments"}</h3>
                <p style={sectionHint}>
                  {t("google_calendar_settings_updated") ||
                    "Set your booking limits so clients can only schedule inside your available window."}
                </p>
                <button
                  onClick={handleToggleCalendar}
                  disabled={togglingStatus}
                  style={{
                    ...primaryButton(togglingStatus),
                    backgroundColor: calendarStatus === "active" ? "#F6FBF9" : "#2EB39A",
                    color: calendarStatus === "active" ? "#2EB39A" : "#FFFFFF",
                    border: `1px solid ${calendarStatus === "active" ? "#2EB39A" : "#2EB39A"}`,
                  }}
                >
                  {togglingStatus
                    ? "Updating..."
                    : calendarStatus === "active"
                    ? "Disable Calendar"
                    : "Enable Calendar"}
                </button>
              </section>

              {isDirty && (
                <section style={dirtyWarningBox}>
                  <p style={{ margin: 0, color: "#7A4D00", fontWeight: 700 }}>
                    Tienes cambios sin guardar en Calendar Setup.
                  </p>
                  <p style={{ margin: "4px 0 0", color: "#7A4D00", fontSize: "0.9rem" }}>
                    Guarda antes de crear citas para que Appointments use estas reglas.
                  </p>
                </section>
              )}

              {(loadingSettings || togglingStatus) && (
                <section style={sectionStyle}>
                  <div style={skeletonTitle} />
                  <div style={skeletonRow}>
                    <div style={{ ...skeletonLine, width: "42%" }} />
                    <div style={{ ...skeletonLine, width: "28%" }} />
                  </div>
                  <div style={skeletonRow}>
                    <div style={{ ...skeletonLine, width: "35%" }} />
                    <div style={{ ...skeletonLine, width: "32%" }} />
                  </div>
                </section>
              )}

              <div
                style={{
                  opacity: isDisabled ? 0.5 : 1,
                  pointerEvents: isDisabled ? "none" : "auto",
                }}
              >
              {/* Google Calendar integration kept out of scope for now. */}

 


            {/* Available Days */}
            <section style={sectionStyle}>
              <h3 style={sectionTitle}>🕒 {t("available_days_hours")}</h3>

              <div style={daysContainer}>
                {days.map((day) => {
                  const active = selectedDays.includes(day);
                  return (
                    <button
                      key={day}
                      onClick={() => toggleDay(day)}
                      style={{
                        ...dayButton,
                        backgroundColor: active ? "#4A90E2" : "#FFFFFF",
                        color: active ? "#FFFFFF" : "#274472",
                        borderColor: active ? "#4A90E2" : "#EDEDED",
                      }}
                    >
                      {day}
                    </button>
                  );
                })}
              </div>

              <div style={timeRangeRow}>
                <label style={labelStyle}>{t("from")}</label>
                <input
                  type="time"
                  value={timeRange.start}
                  onChange={(e) =>
                    setTimeRange({ ...timeRange, start: e.target.value })
                  }
                  style={timeInput}
                />

                <label style={labelStyle}>{t("to")}</label>
                <input
                  type="time"
                  value={timeRange.end}
                  onChange={(e) =>
                    setTimeRange({ ...timeRange, end: e.target.value })
                  }
                  style={timeInput}
                />
              </div>
            </section>

            {/* Booking Rules */}
            <section style={sectionStyle}>
              <h3 style={sectionTitle}>⚙️ {t("booking_rules")}</h3>

              <div style={rulesGrid}>
                <RuleInput
                  label={t("minimum_notice_hours")}
                  value={minNoticeHours}
                  onChange={(v) => setMinNoticeHours(Number(v))}
                />
                <RuleInput
                  label={t("maximum_days_ahead")}
                  value={maxDaysAhead}
                  onChange={(v) => setMaxDaysAhead(Number(v))}
                />
                <RuleInput
                  label={t("buffer_between_slots")}
                  value={bufferTime}
                  onChange={(v) => setBufferTime(Number(v))}
                />
                <RuleSelect
                  label={t("slot_duration")}
                  value={slotDuration}
                  onChange={(v) => setSlotDuration(Number(v))}
                  options={[15, 30, 45, 60]}
                />
              </div>

              <div style={toggleRow}>
                <label style={labelStyle}>{t("allow_same_day_booking")}</label>
                <input
                  type="checkbox"
                  checked={allowSameDay}
                  onChange={(e) => setAllowSameDay(e.target.checked)}
                  style={checkboxStyle}
                />
              </div>
            </section>

            {/* Google -> Evolvian sync block */}
            <section style={sectionStyle}>
              <h3 style={sectionTitle}>🔄 Sincronizar con Google Calendar</h3>
              <p style={sectionHint}>
                Modo unidireccional: <strong>Google → Evolvian</strong>. Evolvian solo usa Google para detectar
                espacios ocupados y bloquear esos horarios al agendar.
              </p>
              <p style={sectionHint}>
                <strong>No se crean ni se modifican eventos en Google Calendar desde Evolvian.</strong>
              </p>

              {loadingGoogleStatus ? (
                <div style={connectedBox}>
                  <span style={{ color: "#7A7A7A" }}>Verificando conexión con Google Calendar...</span>
                </div>
              ) : (
                <div style={connectedBox}>
                  <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                    <strong style={{ color: "#274472" }}>
                      {googleConnected ? "Conectado" : "No conectado"}
                    </strong>
                    <span style={{ color: "#4A90E2", fontSize: "0.88rem" }}>
                      {googleConnected
                        ? `Cuenta: ${googleConnectedEmail || "Google Calendar activo"}`
                        : "Conecta Google para bloquear horarios ocupados automáticamente."}
                    </span>
                  </div>

                  {googleConnected ? (
                    <button
                      onClick={handleDisconnectGoogleCalendar}
                      disabled={disconnectingGoogle}
                      style={dangerGhostButton(disconnectingGoogle)}
                    >
                      {disconnectingGoogle ? "Desconectando..." : "Desconectar Google"}
                    </button>
                  ) : (
                    <button onClick={handleConnectGoogleCalendar} style={primaryButton(false)}>
                      Conectar Google Calendar
                    </button>
                  )}
                </div>
              )}
            </section>

            {/* Timezone (read-only, source of truth: My Profile) */}
            <section style={sectionStyle}>
              <h3 style={sectionTitle}>🌎 {t("timezone")}</h3>
              <div style={readonlyTimezone}>{timezone || "UTC"}</div>
              <p style={sectionHint}>
                Para cambiar tu zona horaria ve a <strong>Settings - My Profile</strong>.
              </p>
            </section>

            <section style={sectionStyle}>
              <h3 style={sectionTitle}>💬 Canales de agenda</h3>
              <p style={sectionHint}>
                Controla si los clientes ven y usan agendado con AI por canal.
              </p>

              <div style={toggleRow}>
                <label style={labelStyle}>Mostrar botón "Agendar" en Chat Widget</label>
                <input
                  type="checkbox"
                  checked={showAgendaInChatWidget}
                  onChange={(e) => setShowAgendaInChatWidget(e.target.checked)}
                  style={checkboxStyle}
                />
              </div>

              <div style={toggleRow}>
                <label style={labelStyle}>Agendar con AI en chat</label>
                <input
                  type="checkbox"
                  checked={aiSchedulingChatEnabled}
                  onChange={(e) => setAiSchedulingChatEnabled(e.target.checked)}
                  style={checkboxStyle}
                />
              </div>

              <div style={toggleRow}>
                <label style={labelStyle}>Agendar con AI en WhatsApp</label>
                <input
                  type="checkbox"
                  checked={aiSchedulingWhatsappEnabled}
                  onChange={(e) => setAiSchedulingWhatsappEnabled(e.target.checked)}
                  style={checkboxStyle}
                />
              </div>
            </section>

            <div style={{ textAlign: "right", marginTop: "2rem" }}>
              <button
                onClick={handleSave}
                disabled={saving || loadingSettings}
                style={{ ...saveButton, width: isMobile ? "100%" : "auto" }}
              >
                {saving ? t("saving") : t("save_settings")}
              </button>
            </div>
            </div>
          </div>
        )}
              </div>
    </div>
  );
}


/* Subcomponentes */
function RuleInput({ label, value, onChange }) {
  return (
    <div style={ruleBox}>
      <label style={labelStyle}>{label}</label>
      <input type="number" value={value} onChange={(e) => onChange?.(e.target.value)} style={numberInput} />
    </div>
  );
}

function RuleSelect({ label, value, onChange, options }) {
  const { t } = useLanguage();
  return (
    <div style={ruleBox}>
      <label style={labelStyle}>{label}</label>
      <select value={value} onChange={(e) => onChange?.(e.target.value)} style={selectStyle}>
        {options.map((opt) => (
          <option key={opt} value={opt}>
            {opt} {t("minutes_short")}
          </option>
        ))}
      </select>
    </div>
  );
}


/* Estilos */
const pageStyle = {
  padding: "clamp(0.85rem, 0.7rem + 0.8vw, 1.4rem)",
  backgroundColor: "#FFFFFF",
  color: "#274472",
  fontFamily: "system-ui, sans-serif",
  minHeight: "100%",
};
const headerRow = {
  display: "flex",
  alignItems: "flex-start",
  gap: "1rem",
  marginBottom: "1rem",
  flexWrap: "wrap",
};
const titleStyle = { fontSize: "clamp(1.35rem, 1.1rem + 1vw, 1.8rem)", fontWeight: "bold", color: "#F5A623", margin: 0 };
const subtitleStyle = { color: "#4A90E2", fontSize: "clamp(0.92rem, 0.86rem + 0.3vw, 1rem)", margin: 0 };

const toggleContainer = (isMobile) => ({ display: "flex", justifyContent: "center", gap: isMobile ? "0.5rem" : "0.75rem", margin: "1rem 0 1.5rem", flexWrap: "wrap" });
const toggleButton = { border: "1px solid #EDEDED", borderRadius: 10, padding: "0.6rem 1.2rem", fontWeight: "bold", cursor: "pointer", transition: "all 0.2s ease", fontSize: "0.95rem" };

const sectionStyle = {
  border: "1px solid #EDEDED",
  borderRadius: 14,
  backgroundColor: "#FFFFFF",
  padding: "clamp(0.9rem, 0.8rem + 0.8vw, 1.5rem)",
  marginBottom: "1.1rem",
  boxShadow: "0 2px 8px rgba(0,0,0,0.05)",
};
const sectionTitle = { fontSize: "1.2rem", color: "#274472", fontWeight: "bold", margin: 0, marginBottom: 6 };
const sectionHint = { color: "#7A7A7A", fontSize: "0.9rem", margin: "4px 0 12px" };
const readonlyTimezone = { border: "1px solid #EDEDED", borderRadius: 8, padding: "0.6rem 0.8rem", fontSize: "0.9rem", color: "#274472", backgroundColor: "#F9FAFB" };

const connectedBox = { display: "flex", justifyContent: "space-between", alignItems: "center", backgroundColor: "#F7FFF9", border: "1px solid #A3D9B1", padding: "0.8rem 1.2rem", borderRadius: 10 };
const primaryButton = (disabled) => ({ backgroundColor: disabled ? "#BDE9DF" : "#2EB39A", color: "#FFFFFF", border: "none", borderRadius: 10, padding: "0.7rem 1.2rem", fontWeight: "bold", cursor: disabled ? "not-allowed" : "pointer", fontSize: "0.95rem" });
const dangerGhostButton = (disabled) => ({ backgroundColor: "#FFFFFF", color: disabled ? "#A0A0A0" : "#B00020", border: `1px solid ${disabled ? "#E6E6E6" : "#FFD3D7"}`, borderRadius: 10, padding: "0.6rem 1rem", fontWeight: "bold", cursor: disabled ? "not-allowed" : "pointer" });

const daysContainer = { display: "flex", flexWrap: "wrap", gap: "0.5rem" };
const dayButton = { border: "1px solid #EDEDED", borderRadius: 8, padding: "0.5rem 1rem", fontWeight: "bold", cursor: "pointer", transition: "all 0.2s ease" };

const timeRangeRow = { display: "flex", alignItems: "center", gap: "1rem", marginTop: "1rem", flexWrap: "wrap" };
const labelStyle = { color: "#274472", fontSize: "0.9rem", fontWeight: 600 };
const timeInput = { border: "1px solid #EDEDED", borderRadius: 8, padding: "0.4rem 0.8rem", fontSize: "0.9rem", color: "#274472", width: "min(100%, 180px)" };

const rulesGrid = { display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "1rem", marginTop: "1rem" };
const ruleBox = { display: "flex", flexDirection: "column", gap: "0.3rem" };
const numberInput = { border: "1px solid #EDEDED", borderRadius: 8, padding: "0.5rem", fontSize: "0.9rem", color: "#274472" };
const selectStyle = { border: "1px solid #EDEDED", borderRadius: 8, padding: "0.5rem", fontSize: "0.9rem", color: "#274472", backgroundColor: "#FFFFFF" };

const toggleRow = { display: "flex", alignItems: "center", gap: "0.5rem", marginTop: "1rem" };
const checkboxStyle = { width: 18, height: 18, accentColor: "#4A90E2", cursor: "pointer" };

const saveButton = { backgroundColor: "#2EB39A", color: "#FFFFFF", border: "none", borderRadius: 10, padding: "0.8rem 1.6rem", fontWeight: "bold", fontSize: "0.95rem", cursor: "pointer", minHeight: 42 };
const dirtyWarningBox = { border: "1px solid #FFD8A8", borderRadius: 12, backgroundColor: "#FFF8ED", padding: "0.9rem 1rem", marginBottom: "1rem" };
const skeletonTitle = { height: 16, width: 180, borderRadius: 8, backgroundColor: "#DCE8F8", animation: "evoSkeletonPulse 1.1s ease-in-out infinite", marginBottom: 12 };
const skeletonRow = { display: "flex", gap: 12, marginBottom: 10 };
const skeletonLine = { height: 12, borderRadius: 8, backgroundColor: "#EAF3FC", animation: "evoSkeletonPulse 1.1s ease-in-out infinite" };
