// src/features/calendar/GoogleCalendarSettings.jsx
// Evolvian Premium Light — con control de activación calendar_status
import { useEffect, useState } from "react";
import { useClientId } from "../../hooks/useClientId";
import { toast } from "../../components/ui/use-toast";
import { authFetch } from "../../lib/authFetch";
import { useLanguage } from "../../contexts/LanguageContext";
import CreateAppointment from "./CreateAppointments";


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
  const [loadingSettings, setLoadingSettings] = useState(false);
  const [togglingStatus, setTogglingStatus] = useState(false);
  const [saving, setSaving] = useState(false);
  const [lastSavedSnapshot, setLastSavedSnapshot] = useState(null);

  const days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
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
        allow_same_day: Boolean(source.allow_same_day ?? true),
        timezone: source.timezone ?? "America/Mexico_City",
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
      allow_same_day: Boolean(allowSameDay),
      timezone,
    };
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
        const s = await res.json();
        setCalendarStatus(s.calendar_status || "inactive");
        setSelectedDays(normalizeDays(s.selected_days));
        setTimeRange({ start: s.start_time ?? "09:00", end: s.end_time ?? "18:00" });
        setSlotDuration(s.slot_duration_minutes ?? 30);
        setMinNoticeHours(s.min_notice_hours ?? 4);
        setMaxDaysAhead(s.max_days_ahead ?? 14);
        setBufferTime(s.buffer_minutes ?? 15);
        setAllowSameDay(s.allow_same_day ?? true);
        setTimezone(s.timezone ?? "America/Mexico_City");
        setLastSavedSnapshot(buildSnapshot(s));
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
      const settings = await refreshed.json();
      setSelectedDays(normalizeDays(settings.selected_days));
      setTimeRange({ start: settings.start_time ?? "09:00", end: settings.end_time ?? "18:00" });
      setSlotDuration(settings.slot_duration_minutes ?? 30);
      setMinNoticeHours(settings.min_notice_hours ?? 4);
      setMaxDaysAhead(settings.max_days_ahead ?? 14);
      setBufferTime(settings.buffer_minutes ?? 15);
      setAllowSameDay(settings.allow_same_day ?? true);
      setTimezone(settings.timezone ?? "America/Mexico_City");
      setLastSavedSnapshot(buildSnapshot(settings));

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
        allow_same_day: Boolean(allowSameDay),
        timezone,
      };
      const res = await authFetch(`${backendUrl}/calendar/settings`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error(t("save_failed"));

      // Reload persisted settings to avoid stale/local mismatches and UI freezes.
      const refreshed = await authFetch(`${backendUrl}/calendar/settings?client_id=${clientId}`);
      if (!refreshed.ok) throw new Error(t("google_calendar_load_settings_error"));
      const s = await refreshed.json();
      setCalendarStatus(s.calendar_status || "inactive");
      setSelectedDays(normalizeDays(s.selected_days));
      setTimeRange({ start: s.start_time ?? "09:00", end: s.end_time ?? "18:00" });
      setSlotDuration(Number(s.slot_duration_minutes ?? 30));
      setMinNoticeHours(Number(s.min_notice_hours ?? 4));
      setMaxDaysAhead(Number(s.max_days_ahead ?? 14));
      setBufferTime(Number(s.buffer_minutes ?? 15));
      setAllowSameDay(Boolean(s.allow_same_day ?? true));
      setTimezone(s.timezone ?? "America/Mexico_City");
      setLastSavedSnapshot(buildSnapshot(s));
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

  return (
    <div id="evo-calendar-settings" style={pageStyle}>
      <div style={{ maxWidth: 1200, margin: "0 auto" }}>
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

            {/* Timezone (read-only, source of truth: My Profile) */}
            <section style={sectionStyle}>
              <h3 style={sectionTitle}>🌎 {t("timezone")}</h3>
              <div style={readonlyTimezone}>{timezone || "UTC"}</div>
              <p style={sectionHint}>
                Para cambiar tu zona horaria ve a <strong>Settings - My Profile</strong>.
              </p>
            </section>

            <div style={{ textAlign: "right", marginTop: "2rem" }}>
              <button
                onClick={handleSave}
                disabled={saving || loadingSettings}
                style={saveButton}
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
const pageStyle = { padding: "2rem 3rem", backgroundColor: "#FFFFFF", color: "#274472", fontFamily: "system-ui, sans-serif", minHeight: "100vh" };
const headerRow = { display: "flex", alignItems: "center", gap: "1rem", marginBottom: "1rem" };
const titleStyle = { fontSize: "1.8rem", fontWeight: "bold", color: "#F5A623", margin: 0 };
const subtitleStyle = { color: "#4A90E2", fontSize: "1rem", margin: 0 };

const toggleContainer = (isMobile) => ({ display: "flex", justifyContent: "center", gap: isMobile ? "0.5rem" : "0.75rem", margin: "1rem 0 1.5rem", flexWrap: "wrap" });
const toggleButton = { border: "1px solid #EDEDED", borderRadius: 10, padding: "0.6rem 1.2rem", fontWeight: "bold", cursor: "pointer", transition: "all 0.2s ease", fontSize: "0.95rem" };

const sectionStyle = { border: "1px solid #EDEDED", borderRadius: 14, backgroundColor: "#FFFFFF", padding: "1.5rem 2rem", marginBottom: "1.25rem", boxShadow: "0 2px 8px rgba(0,0,0,0.05)" };
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
const timeInput = { border: "1px solid #EDEDED", borderRadius: 8, padding: "0.4rem 0.8rem", fontSize: "0.9rem", color: "#274472" };

const rulesGrid = { display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "1rem", marginTop: "1rem" };
const ruleBox = { display: "flex", flexDirection: "column", gap: "0.3rem" };
const numberInput = { border: "1px solid #EDEDED", borderRadius: 8, padding: "0.5rem", fontSize: "0.9rem", color: "#274472" };
const selectStyle = { border: "1px solid #EDEDED", borderRadius: 8, padding: "0.5rem", fontSize: "0.9rem", color: "#274472", backgroundColor: "#FFFFFF" };

const toggleRow = { display: "flex", alignItems: "center", gap: "0.5rem", marginTop: "1rem" };
const checkboxStyle = { width: 18, height: 18, accentColor: "#4A90E2", cursor: "pointer" };

const saveButton = { backgroundColor: "#2EB39A", color: "#FFFFFF", border: "none", borderRadius: 10, padding: "0.8rem 1.6rem", fontWeight: "bold", fontSize: "0.95rem", cursor: "pointer" };
const dirtyWarningBox = { border: "1px solid #FFD8A8", borderRadius: 12, backgroundColor: "#FFF8ED", padding: "0.9rem 1rem", marginBottom: "1rem" };
const skeletonTitle = { height: 16, width: 180, borderRadius: 8, backgroundColor: "#DCE8F8", animation: "evoSkeletonPulse 1.1s ease-in-out infinite", marginBottom: 12 };
const skeletonRow = { display: "flex", gap: 12, marginBottom: 10 };
const skeletonLine = { height: 12, borderRadius: 8, backgroundColor: "#EAF3FC", animation: "evoSkeletonPulse 1.1s ease-in-out infinite" };
