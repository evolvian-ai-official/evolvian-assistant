// CreateAppointment.jsx — Evolvian Light (Page + Modal)
import { useEffect, useState } from "react";
import { useClientId } from "../../hooks/useClientId";
import { useLanguage } from "../../contexts/LanguageContext";
import ShowAppointments from "./ShowAppointments";
import AppointmentsFilter from "./AppointmentsFilter";
import { authFetch } from "../../lib/authFetch";


/* 🌐 API ENV */
const API_BASE_URL =
  import.meta.env.MODE === "development"
    ? "http://localhost:8001"
    : "https://evolvian-assistant.onrender.com";

/* =========================
   Validators (Meta-safe)
   ========================= */
const isValidEmail = (email) =>
  /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(email);

const isValidWhatsApp = (phone) =>
  /^\+[1-9]\d{9,14}$/.test(phone); // E.164 (Meta)

/* =========================
   Component
   ========================= */
export default function CreateAppointment({ disabled = false }) {
  const clientId = useClientId();
  const { t } = useLanguage();
  const [sessionId] = useState(() => crypto.randomUUID());

  const [showModal, setShowModal] = useState(false);
  const [appointments] = useState([]);
  const [appointmentsRefreshTick, setAppointmentsRefreshTick] = useState(0);
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [submitError, setSubmitError] = useState("");
  const [duplicateExistingAppt, setDuplicateExistingAppt] = useState(null);
  const [overlapExistingAppt, setOverlapExistingAppt] = useState(null);

  const [form, setForm] = useState({
    user_name: "",
    user_email: "",
    user_phone: "",
    scheduled_time: "",
    appointment_type: "general",
    channel: "chat",
  });

  /* 🔔 Reminder State */
  const [enableReminder, setEnableReminder] = useState(false);
  const [reminderEmail, setReminderEmail] = useState(false);
  const [reminderWhatsApp, setReminderWhatsApp] = useState(false);

  const [emailTemplateId, setEmailTemplateId] = useState("");
  const [whatsappTemplateId, setWhatsappTemplateId] = useState("");

  /* 🧠 Templates */
  const [templates, setTemplates] = useState([]);
  const [templatesLoading, setTemplatesLoading] = useState(false);
  const [calendarRules, setCalendarRules] = useState(null);
  const [rulesLoading, setRulesLoading] = useState(false);
  const [selectedDate, setSelectedDate] = useState("");
  const [selectedTime, setSelectedTime] = useState("");
  const [availableTimes, setAvailableTimes] = useState([]);
  const [availableDates, setAvailableDates] = useState([]);



  /* =========================
     Fetch templates
     ========================= */
  useEffect(() => {
    if (!showModal || !clientId) return;

    const fetchTemplates = async () => {
      setTemplatesLoading(true);
      try {
        const res = await fetch(
          `${API_BASE_URL}/message_templates?client_id=${clientId}&type=appointment_reminder`
        );
        const data = await res.json();
        setTemplates(Array.isArray(data) ? data : []);
      } catch (err) {
        console.error(t("templates_load_failed"), err);
        setTemplates([]);
      } finally {
        setTemplatesLoading(false);
      }
    };

    fetchTemplates();
  }, [showModal, clientId]);

  useEffect(() => {
    if (!showModal || !clientId) return;

    const fetchCalendarRules = async () => {
      setRulesLoading(true);
      try {
        const res = await authFetch(`${API_BASE_URL}/calendar/settings?client_id=${clientId}`);
        const data = await res.json();
        setCalendarRules(data || null);
      } catch (err) {
        console.error("Failed loading calendar settings", err);
        setCalendarRules(null);
      } finally {
        setRulesLoading(false);
      }
    };

    fetchCalendarRules();
  }, [showModal, clientId]);

  const normalizeSelectedDays = (rawDays) => {
    const dayMap = {
      mon: 0, monday: 0, lun: 0, lunes: 0,
      tue: 1, tuesday: 1, mar: 1, martes: 1,
      wed: 2, wednesday: 2, mie: 2, miercoles: 2, miércoles: 2,
      thu: 3, thursday: 3, jue: 3, jueves: 3,
      fri: 4, friday: 4, vie: 4, viernes: 4,
      sat: 5, saturday: 5, sab: 5, sabado: 5, sábado: 5,
      sun: 6, sunday: 6, dom: 6, domingo: 6,
    };
    const arr = Array.isArray(rawDays)
      ? rawDays
      : String(rawDays || "").split(",").map((v) => v.trim()).filter(Boolean);
    const out = new Set();
    arr.forEach((item) => {
      if (typeof item === "number" && item >= 0 && item <= 6) {
        out.add(item);
        return;
      }
      const key = String(item || "")
        .toLowerCase()
        .normalize("NFD")
        .replace(/\p{Diacritic}/gu, "");
      if (dayMap[key] !== undefined) out.add(dayMap[key]);
    });
    return out;
  };

  const toDateInputValue = (date) => {
    const y = date.getFullYear();
    const m = String(date.getMonth() + 1).padStart(2, "0");
    const d = String(date.getDate()).padStart(2, "0");
    return `${y}-${m}-${d}`;
  };

  const formatDateLabel = (dateStr) => {
    try {
      const d = new Date(`${dateStr}T00:00:00`);
      return d.toLocaleDateString("es-MX", {
        weekday: "short",
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
      });
    } catch {
      return dateStr;
    }
  };

  const computeAvailableTimes = (dateStr, rules) => {
    if (!dateStr || !rules) return [];
    const selected = new Date(`${dateStr}T00:00:00`);
    if (Number.isNaN(selected.getTime())) return [];

    const selectedDays = normalizeSelectedDays(rules.selected_days || ["Mon", "Tue", "Wed", "Thu", "Fri"]);
    const jsWeekday = selected.getDay(); // Sun=0
    const weekday = (jsWeekday + 6) % 7; // Mon=0
    if (!selectedDays.has(weekday)) return [];

    const startTime = String(rules.start_time || "09:00");
    const endTime = String(rules.end_time || "18:00");
    const [sH, sM] = startTime.split(":").map((v) => Number(v));
    const [eH, eM] = endTime.split(":").map((v) => Number(v));
    const slot = Number(rules.slot_duration_minutes || 30);
    const buffer = Number(rules.buffer_minutes || 0);
    const step = slot + buffer;
    const allowSameDay = Boolean(rules.allow_same_day ?? true);
    const minNoticeHours = Number(rules.min_notice_hours || 0);
    const maxDaysAhead = Number(rules.max_days_ahead || 365);

    const now = new Date();
    const minNoticeDate = new Date(now.getTime() + minNoticeHours * 60 * 60 * 1000);
    const todayStr = toDateInputValue(now);
    const maxDate = new Date(now);
    maxDate.setDate(maxDate.getDate() + maxDaysAhead);
    const maxDateStr = toDateInputValue(maxDate);

    if (dateStr > maxDateStr) return [];
    if (!allowSameDay && dateStr === todayStr) return [];

    const startTotal = sH * 60 + sM;
    const endTotal = eH * 60 + eM;
    const slots = [];
    for (let mins = startTotal; mins + slot <= endTotal; mins += step) {
      const hh = String(Math.floor(mins / 60)).padStart(2, "0");
      const mm = String(mins % 60).padStart(2, "0");
      const slotDate = new Date(`${dateStr}T${hh}:${mm}:00`);
      if (slotDate < minNoticeDate) continue;
      slots.push(`${hh}:${mm}`);
    }
    return slots;
  };

  const computeAvailableDates = (rules) => {
    if (!rules) return [];
    const maxDaysAhead = Number(rules.max_days_ahead || 365);
    const selectedDays = normalizeSelectedDays(rules.selected_days || ["Mon", "Tue", "Wed", "Thu", "Fri"]);
    const allowSameDay = Boolean(rules.allow_same_day ?? true);
    const dates = [];

    for (let i = 0; i <= maxDaysAhead; i += 1) {
      const d = new Date();
      d.setHours(0, 0, 0, 0);
      d.setDate(d.getDate() + i);

      if (i === 0 && !allowSameDay) continue;

      const weekday = (d.getDay() + 6) % 7; // Mon=0
      if (!selectedDays.has(weekday)) continue;

      const dateStr = toDateInputValue(d);
      const times = computeAvailableTimes(dateStr, rules);
      if (times.length > 0) {
        dates.push({ value: dateStr, label: formatDateLabel(dateStr) });
      }
    }

    return dates;
  };

  const getFriendlyRulesText = (rules) => {
    if (!rules) return "Cargando configuración de Calendar Setup...";
    const days = Array.isArray(rules.selected_days) ? rules.selected_days.join(", ") : "Mon, Tue, Wed, Thu, Fri";
    const start = rules.start_time || "09:00";
    const end = rules.end_time || "18:00";
    const slot = Number(rules.slot_duration_minutes ?? 30);
    const buffer = Number(rules.buffer_minutes ?? 0);
    return `Config activa: días ${days} | horario ${start}-${end} | duración ${slot} min | buffer ${buffer} min.`;
  };

  useEffect(() => {
    if (!showModal || !calendarRules) return;
    const nextDates = computeAvailableDates(calendarRules);
    setAvailableDates(nextDates);

    if (!nextDates.find((d) => d.value === selectedDate)) {
      const firstDate = nextDates[0]?.value || "";
      setSelectedDate(firstDate);
      setSelectedTime("");
      setForm((prev) => ({ ...prev, scheduled_time: "" }));
    }
  }, [showModal, calendarRules]);

  useEffect(() => {
    if (!showModal) return;
    if (!selectedDate) {
      setAvailableTimes([]);
      setSelectedTime("");
      setForm((prev) => ({ ...prev, scheduled_time: "" }));
      return;
    }
    const times = computeAvailableTimes(selectedDate, calendarRules);
    setAvailableTimes(times);
    if (!times.includes(selectedTime)) {
      setSelectedTime("");
      setForm((prev) => ({ ...prev, scheduled_time: "" }));
    }
  }, [showModal, selectedDate, calendarRules]);

  const emailTemplates = templates.filter((t) => t.channel === "email");
  const whatsappTemplates = templates.filter((t) => t.channel === "whatsapp");

  /* =========================
     Derived validation (SAFE)
     ========================= */
  const emailValid = isValidEmail(form.user_email);
  const phoneValid = isValidWhatsApp(form.user_phone);

  const canEnableReminder = emailValid || phoneValid;

  const canSubmit =
    form.user_name &&
    form.scheduled_time &&
    (!enableReminder ||
      ((reminderEmail ? emailValid && emailTemplateId : true) &&
        (reminderWhatsApp
          ? phoneValid && whatsappTemplateId
          : true)));

  /* =========================
     Handlers
     ========================= */
  const handleChange = (e) => {
    setForm({ ...form, [e.target.name]: e.target.value });
  };

  // 🔥 FIX CRÍTICO: sanitizar teléfono
  const handlePhoneChange = (e) => {
    let value = e.target.value.replace(/[^+\d]/g, "");

    // Solo un "+"
    if (value.indexOf("+") > 0) {
      value = "+" + value.replace(/\+/g, "");
    }

    setForm({ ...form, user_phone: value });
  };

  const resetForm = () => {
    setForm({
      user_name: "",
      user_email: "",
      user_phone: "",
      scheduled_time: "",
      appointment_type: "general",
      channel: "chat",
    });
    setEnableReminder(false);
    setReminderEmail(false);
    setReminderWhatsApp(false);
    setEmailTemplateId("");
    setWhatsappTemplateId("");
    setSuccess(false);
    setSubmitError("");
    setDuplicateExistingAppt(null);
    setOverlapExistingAppt(null);
    setSelectedDate("");
    setSelectedTime("");
    setAvailableTimes([]);
    setAvailableDates([]);
  };

  /* =========================
     Submit
     ========================= */
  const formatExistingSlot = (existing) => {
    const raw = existing?.formatted_time || existing?.scheduled_time;
    if (!raw) return "";
    if (existing?.formatted_time) return existing.formatted_time;
    try {
      const dt = new Date(raw);
      if (Number.isNaN(dt.getTime())) return raw;
      return dt.toLocaleString();
    } catch {
      return raw;
    }
  };

  const submit = async (replaceExisting = false) => {
    if (!canSubmit || !clientId) return;

    setLoading(true);
    setSubmitError("");
    setOverlapExistingAppt(null);
    if (!replaceExisting) setDuplicateExistingAppt(null);

    try {
      const res = await fetch(`${API_BASE_URL}/create_appointment`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          client_id: clientId,
          session_id: sessionId,
          scheduled_time: form.scheduled_time,
          user_name: form.user_name,
          user_email: emailValid ? form.user_email : undefined,
          user_phone: phoneValid ? form.user_phone : undefined,
          appointment_type: form.appointment_type,
          send_reminders: enableReminder,
          replace_existing: replaceExisting,
          reminders: enableReminder

            ? {
                email: reminderEmail ? emailTemplateId : null,
                whatsapp: reminderWhatsApp ? whatsappTemplateId : null,
              }
            : null,
        }),
      });

      const data = await res.json();
      if (data?.duplicate_active) {
        setDuplicateExistingAppt(data?.existing_appointment || {});
        return;
      }
      if (data?.overlap_conflict) {
        setOverlapExistingAppt(data?.existing_appointment || {});
        setSubmitError(data?.message || "Ese horario ya no está disponible.");
        return;
      }
      if (data?.invalid_time) {
        setSubmitError(data?.message || "Horario inválido.");
        return;
      }
      if (data?.success) {
        setSuccess(true);
        setAppointmentsRefreshTick((v) => v + 1);
        setTimeout(() => {
          setShowModal(false);
          resetForm();
        }, 1200);
      } else {
        setSubmitError(data?.message || t("appointment_create_failed"));
      }
    } catch (e) {
      console.error(t("appointment_create_failed"), e);
      setSubmitError(t("appointment_create_failed"));
    } finally {
      setLoading(false);
    }
  };

  /* =========================
     UI
     ========================= */
  return (
    <div style={pageStyle}>
      {/* Header */}
      <div style={headerRow}>
        <h2 style={titleStyle}>{t("appointments_nav")}</h2>
        <button
          style={primaryButton(disabled)}
          onClick={() => {
            if (!disabled) setShowModal(true);
          }}
          disabled={disabled}
        >
          + {t("create_appointment")}
        </button>
      </div>
      {disabled && (
        <p style={reminderHint}>
          Appointments está desactivado. Actívalo en <strong>Calendar Setup</strong> para crear nuevas citas.
        </p>
      )}


      <ShowAppointments refreshKey={appointmentsRefreshTick} />


      {/* Modal */}
      {showModal && (
        <div style={modalOverlay}>
          <div style={modalBox}>
            <h3 style={modalTitle}>{t("new_appointment")}</h3>

            <input
              style={inputStyle}
              placeholder={t("appointment_user_name_required")}
              name="user_name"
              value={form.user_name}
              onChange={handleChange}
            />

            <input
              style={inputStyle}
              placeholder={t("appointment_email_optional")}
              name="user_email"
              value={form.user_email}
              onChange={handleChange}
            />
            {form.user_email && !emailValid && (
              <p style={reminderHint}>{t("invalid_email_format")}</p>
            )}

            <input
              style={inputStyle}
              placeholder={t("appointment_phone_placeholder")}
              value={form.user_phone}
              onChange={handlePhoneChange}
            />
            {form.user_phone && !phoneValid && (
              <p style={reminderHint}>
                {t("use_international_phone_format")}
              </p>
            )}

            <select
              style={inputStyle}
              value={selectedDate}
              onChange={(e) => setSelectedDate(e.target.value)}
              disabled={rulesLoading}
            >
              <option value="">
                {rulesLoading ? "Cargando fechas..." : "Selecciona una fecha disponible"}
              </option>
              {availableDates.map((date) => (
                <option key={date.value} value={date.value}>
                  {date.label}
                </option>
              ))}
            </select>
            <select
              style={inputStyle}
              value={selectedTime}
              onChange={(e) => {
                const time = e.target.value;
                setSelectedTime(time);
                setForm((prev) => ({
                  ...prev,
                  scheduled_time: selectedDate && time ? `${selectedDate}T${time}` : "",
                }));
              }}
              disabled={!selectedDate || rulesLoading}
            >
              <option value="">
                {!selectedDate
                  ? "Selecciona una fecha"
                  : rulesLoading
                  ? "Cargando horarios..."
                  : "Selecciona una hora"}
              </option>
              {availableTimes.map((time) => (
                <option key={time} value={time}>
                  {time}
                </option>
              ))}
            </select>
            {selectedDate && !rulesLoading && availableTimes.length === 0 && (
              <p style={reminderHint}>
                No hay horarios disponibles para esa fecha según tu configuración de Calendar Setup.
              </p>
            )}
            {!rulesLoading && availableDates.length === 0 && (
              <p style={reminderHint}>
                No hay fechas disponibles con tu configuración actual de Calendar Setup.
              </p>
            )}
            <p style={timezoneNoticeStyle}>
              ⚠️ {t("appointment_timezone_notice")} <strong>{t("settings_my_profile_path")}</strong> {t("appointment_timezone_notice_end")}
            </p>
            <p style={timezoneNoticeStyle}>
              ⏱️ Selecciona una fecha y hora disponibles según tu <strong>Calendar Setup</strong>. {getFriendlyRulesText(calendarRules)}
            </p>


            {/* 🔔 REMINDERS */}
            <div style={reminderBox}>
              <label
                style={{
                  ...checkboxRow,
                  opacity: canEnableReminder ? 1 : 0.5,
                }}
              >
                <input
                  type="checkbox"
                  checked={enableReminder}
                  disabled={!canEnableReminder}
                  onChange={(e) =>
                    setEnableReminder(e.target.checked)
                  }
                />
                <span style={{ marginLeft: 8 }}>
                  {t("send_reminder_for_appointment")}
                </span>
              </label>

              {!canEnableReminder && (
                <p style={reminderHint}>
                  {t("add_valid_contact_enable_reminders")}
                </p>
              )}

              {enableReminder && (
                <>
                  {/* WhatsApp */}
                  <div style={reminderBlock}>
                    <label
                      style={{
                        ...checkboxRow,
                        opacity:
                          phoneValid &&
                          whatsappTemplates.length
                            ? 1
                            : 0.5,
                      }}
                    >
                      <input
                        type="checkbox"
                        checked={reminderWhatsApp}
                        disabled={
                          !phoneValid ||
                          whatsappTemplates.length === 0
                        }
                        onChange={(e) =>
                          setReminderWhatsApp(e.target.checked)
                        }
                      />
                      <span style={{ marginLeft: 8 }}>
                        {t("whatsapp")}
                      </span>
                    </label>

                    {reminderWhatsApp &&
                      whatsappTemplates.length > 0 && (
                        <select
                          style={inputStyle}
                          value={whatsappTemplateId}
                          onChange={(e) =>
                            setWhatsappTemplateId(e.target.value)
                          }
                        >
                          <option value="">
                            {t("select_whatsapp_template")}
                          </option>
                          {whatsappTemplates.map((tpl) => (
                            <option key={tpl.id} value={tpl.id}>
                              
                              {tpl.meta_template_name || tpl.template_name || t("template")} — {tpl.label}

                            </option>
                          ))}
                        </select>
                      )}
                  </div>

                  {/* Email 
                  <div style={reminderBlock}>
                    <label
                      style={{
                        ...checkboxRow,
                        opacity:
                          emailValid &&
                          emailTemplates.length
                            ? 1
                            : 0.5,
                      }}
                    >
                      <input
                        type="checkbox"
                        checked={reminderEmail}
                        disabled={
                          !emailValid ||
                          emailTemplates.length === 0
                        }
                        onChange={(e) =>
                          setReminderEmail(e.target.checked)
                        }
                      />
                      <span style={{ marginLeft: 8 }}>
                        Email
                      </span>
                    </label>

                    {reminderEmail &&
                      emailTemplates.length > 0 && (
                        <select
                          style={inputStyle}
                          value={emailTemplateId}
                          onChange={(e) =>
                            setEmailTemplateId(e.target.value)
                          }
                        >
                          <option value="">
                            Select Email template
                          </option>
                          {emailTemplates.map((t) => (
                            <option key={t.id} value={t.id}>
                              {t.template_name} — {t.label}
                            </option>
                          ))}
                        </select>
                      )}
                  </div>*/}
                </>
              )}
            </div>

            {/* Actions */}
            <div style={modalActions}>
              <button
                style={secondaryButton}
                onClick={() => {
                  setShowModal(false);
                  resetForm();
                }}
              >
                {t("cancel")}
              </button>

              <button
                style={primaryButton(!canSubmit || loading)}
                disabled={!canSubmit || loading}
                onClick={() => submit(false)}
              >
                {loading ? t("creating") : t("create")}
              </button>
            </div>

            {!!submitError && (
              <p style={errorMsg}>{submitError}</p>
            )}

            {duplicateExistingAppt && (
              <div style={duplicateBox}>
                <p style={duplicateText}>
                  Ya existe una cita activa para este contacto ({formatExistingSlot(duplicateExistingAppt)}).
                </p>
                <button
                  style={replaceButton}
                  disabled={loading}
                  onClick={() => submit(true)}
                >
                  {loading ? "Procesando..." : "Cancelar actual y crear nueva"}
                </button>
              </div>
            )}

            {overlapExistingAppt && (
              <p style={errorMsg}>
                Ya hay una cita confirmada en ese horario ({formatExistingSlot(overlapExistingAppt)}). Elige otro horario.
              </p>
            )}

            {success && (
              <p style={successMsg}>
                ✅ {t("appointment_created_success")}
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

/* 🎨 Styles (SIN CAMBIOS) */
const pageStyle = {
  padding: "2rem 3rem",
  backgroundColor: "#FFFFFF",
  minHeight: "100vh",
  fontFamily: "system-ui, sans-serif",
  color: "#274472",
};

const headerRow = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  marginBottom: "2rem",
};

const titleStyle = {
  fontSize: "1.8rem",
  color: "#F5A623",
  fontWeight: "bold",
};

const modalOverlay = {
  position: "fixed",
  inset: 0,
  backgroundColor: "rgba(0,0,0,0.4)",
  display: "flex",
  justifyContent: "center",
  alignItems: "center",
  zIndex: 1000,
};

const modalBox = {
  backgroundColor: "#FFFFFF",
  borderRadius: 16,
  padding: "2rem",
  width: 440,
};

const modalTitle = {
  fontSize: "1.4rem",
  fontWeight: "bold",
  marginBottom: "1rem",
};

const inputStyle = {
  width: "100%",
  padding: "0.65rem",
  marginBottom: "0.75rem",
  borderRadius: 10,
  border: "1px solid #EDEDED",
};

const reminderBox = {
  borderTop: "1px solid #EDEDED",
  paddingTop: "1rem",
  marginTop: "1rem",
};

const reminderBlock = {
  marginTop: "0.75rem",
};

const checkboxRow = {
  display: "flex",
  alignItems: "center",
  fontSize: "0.9rem",
};

const reminderHint = {
  fontSize: "0.8rem",
  color: "#7A7A7A",
  marginTop: "0.25rem",
};

const modalActions = {
  display: "flex",
  justifyContent: "flex-end",
  gap: "0.75rem",
  marginTop: "1.25rem",
};

const primaryButton = (disabled) => ({
  backgroundColor: disabled ? "#BDE9DF" : "#2EB39A",
  color: "#FFFFFF",
  border: "none",
  borderRadius: 10,
  padding: "0.6rem 1.2rem",
  cursor: disabled ? "not-allowed" : "pointer",
});

const secondaryButton = {
  backgroundColor: "#EDEDED",
  border: "none",
  borderRadius: 10,
  padding: "0.6rem 1.2rem",
  cursor: "pointer",
};

const successMsg = {
  marginTop: "0.75rem",
  color: "#2EB39A",
  fontWeight: "bold",
};

const errorMsg = {
  marginTop: "0.75rem",
  color: "#d7263d",
  fontWeight: 600,
  fontSize: "0.9rem",
};

const duplicateBox = {
  marginTop: "0.75rem",
  padding: "0.75rem",
  borderRadius: 10,
  border: "1px solid #ffd8a8",
  backgroundColor: "#fff8ed",
};

const duplicateText = {
  margin: 0,
  color: "#7a4d00",
  fontSize: "0.9rem",
};

const replaceButton = {
  marginTop: "0.65rem",
  backgroundColor: "#f5a623",
  color: "#fff",
  border: "none",
  borderRadius: 8,
  padding: "0.5rem 0.75rem",
  cursor: "pointer",
};


const timezoneNoticeStyle = {
  marginTop: "1rem",
  fontSize: "0.85rem",
  color: "#7A7A7A",
  backgroundColor: "#F9F9F9",
  padding: "0.75rem 1rem",
  borderRadius: 10,
  border: "1px solid #EDEDED",
};
