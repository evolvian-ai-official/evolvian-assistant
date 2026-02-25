// CreateAppointment.jsx — Evolvian Light (Page + Modal)
import { useEffect, useMemo, useRef, useState } from "react";
import { useClientId } from "../../hooks/useClientId";
import { useLanguage } from "../../contexts/LanguageContext";
import ShowAppointments from "./ShowAppointments";
import { authFetch } from "../../lib/authFetch";
import {
  PHONE_COUNTRY_OPTIONS,
  composeE164Phone,
  inferPhoneCountryCode,
  isValidAppointmentEmail,
  isValidAppointmentPhone,
  normalizeAppointmentEmail,
  normalizeAppointmentName,
  sanitizePhoneLocalInput,
  splitE164Phone,
} from "./appointmentContactUtils";
import "../../components/ui/internal-admin-responsive.css";


/* 🌐 API ENV */
const API_BASE_URL =
  import.meta.env.MODE === "development"
    ? "http://localhost:8001"
    : "https://evolvian-assistant.onrender.com";

/* =========================
   Validators (Meta-safe)
   ========================= */
const isValidEmail = isValidAppointmentEmail;
const isValidWhatsApp = isValidAppointmentPhone;

const isChannelEnabled = (channel) => Boolean(channel?.is_active ?? channel?.active);

const READY_WHATSAPP_TEMPLATE_STATUSES = new Set(["ready", "active", "approved"]);

const isSelectableWhatsAppTemplate = (template) => {
  if (template?.channel !== "whatsapp") return false;

  const status = String(template?.whatsapp_template_status || "").trim().toLowerCase();
  if (!READY_WHATSAPP_TEMPLATE_STATUSES.has(status)) return false;

  if (template?.whatsapp_template_active !== true) return false;

  return true;
};

const isTemplateActive = (template) => {
  if (!template || typeof template !== "object") return false;
  if (template.is_active === false || template.active === false) return false;
  if (typeof template.is_active === "boolean") return template.is_active;
  if (typeof template.active === "boolean") return template.active;
  return true;
};

/* =========================
   Component
   ========================= */
export default function CreateAppointment({ disabled = false }) {
  const clientId = useClientId();
  const { t, lang } = useLanguage();
  const isEs = lang === "es";
  const uiLocale = isEs ? "es-MX" : "en-US";
  const ui = {
    clientsLabel: isEs ? "Clientes" : "Clients",
    clientsSearchPlaceholder: isEs
      ? "Buscar cliente por nombre, email o teléfono"
      : "Search client by name, email or phone",
    loadingClients: isEs ? "Cargando clients..." : "Loading clients...",
    selectOptionalClient: isEs ? "Selecciona un cliente (opcional)" : "Select a client (optional)",
    newClientShort: isEs ? "Nuevo" : "New",
    selectedClientPrefix: isEs ? "Cliente seleccionado" : "Selected client",
    selectedClientFallback: isEs ? "Cliente" : "Client",
    creatingNewClientHint: isEs
      ? 'Estás creando un cliente nuevo. Llena nombre, email y/o teléfono y usa "Guardar cliente".'
      : 'You are creating a new client. Fill name, email and/or phone, then click "Save client".',
    saveClient: isEs ? "Guardar cliente" : "Save client",
    createNewClientOption: isEs ? "+ Crear cliente nuevo" : "+ Create new client",
    saving: isEs ? "Guardando..." : "Saving...",
    appointmentsCountSuffix: isEs ? "cita(s)" : "appointment(s)",
    phoneWithoutPrefixSuffix: isEs ? "(sin prefijo)" : "(without country code)",
    suggestedPrefixText: isEs
      ? "Prefijo sugerido"
      : "Suggested prefix",
    suggestedPrefixReason: isEs
      ? "según el país configurado del usuario en Evolvian."
      : "based on the Evolvian user's configured country.",
    clientsDirectoryUnavailable: isEs
      ? "El directorio editable de clients aún no está disponible (falta migración), pero puedes seleccionar clientes del histórico."
      : "The editable clients directory is not available yet (missing migration), but you can select clients from appointment history.",
    clientsLoadError: isEs
      ? "No se pudo cargar la lista de clientes."
      : "Could not load the clients list.",
    invalidEmail: isEs ? "Email inválido." : "Invalid email.",
    invalidPhone: isEs ? "Teléfono inválido. Usa prefijo internacional." : "Invalid phone. Use international format.",
    addEmailOrPhone: isEs ? "Agrega email o teléfono." : "Add email or phone.",
    timeNoLongerAvailable: isEs ? "Ese horario ya no está disponible." : "That time is no longer available.",
    invalidTime: isEs ? "Horario inválido." : "Invalid time.",
  };
  const [sessionId] = useState(() => {
    if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
      return crypto.randomUUID();
    }
    return `sess_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`;
  });
  const [isMobile, setIsMobile] = useState(
    typeof window !== "undefined" ? window.innerWidth < 768 : false
  );

  const [showModal, setShowModal] = useState(false);
  const [_appointments] = useState([]);
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
  const [appointmentClients, setAppointmentClients] = useState([]);
  const [appointmentClientsLoading, setAppointmentClientsLoading] = useState(false);
  const [appointmentClientsError, setAppointmentClientsError] = useState("");
  const [appointmentClientSearch, setAppointmentClientSearch] = useState("");
  const [selectedAppointmentClientKey, setSelectedAppointmentClientKey] = useState("");
  const [showCreateClientInline, setShowCreateClientInline] = useState(false);
  const [savingClientInline, setSavingClientInline] = useState(false);
  const [inlineClientSaveError, setInlineClientSaveError] = useState("");
  const [ownerPhoneCountryCode, setOwnerPhoneCountryCode] = useState("+1");
  const [phoneCountryCode, setPhoneCountryCode] = useState("+1");
  const [phoneLocalNumber, setPhoneLocalNumber] = useState("");

  /* 🔔 Reminder State */
  const [enableReminder, setEnableReminder] = useState(false);
  const [reminderEmail, setReminderEmail] = useState(false);
  const [reminderWhatsApp, setReminderWhatsApp] = useState(false);

  const [emailTemplateId, setEmailTemplateId] = useState("");
  const [whatsappTemplateId, setWhatsappTemplateId] = useState("");

  /* 🧠 Templates */
  const [templates, setTemplates] = useState([]);
  const [_templatesLoading, setTemplatesLoading] = useState(false);
  const [calendarRules, setCalendarRules] = useState(null);
  const [rulesLoading, setRulesLoading] = useState(false);
  const [googleBusyLoading, setGoogleBusyLoading] = useState(false);
  const [googleBusyRanges, setGoogleBusyRanges] = useState([]);
  const [appointmentsBusyLoading, setAppointmentsBusyLoading] = useState(false);
  const [confirmedAppointments, setConfirmedAppointments] = useState([]);
  const [selectedDate, setSelectedDate] = useState("");
  const [selectedTime, setSelectedTime] = useState("");
  const [availableTimes, setAvailableTimes] = useState([]);
  const [availableDates, setAvailableDates] = useState([]);
  const [channelsLoading, setChannelsLoading] = useState(false);
  const [gmailConnected, setGmailConnected] = useState(false);
  const [gmailEnabled, setGmailEnabled] = useState(false);
  const [gmailAddress, setGmailAddress] = useState("");
  const [whatsAppMetaConnected, setWhatsAppMetaConnected] = useState(false);
  const prevEmailValidRef = useRef(false);

  useEffect(() => {
    const onResize = () => setIsMobile(window.innerWidth < 768);
    onResize();
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  useEffect(() => {
    const nextPhone = composeE164Phone(phoneCountryCode, phoneLocalNumber);
    setForm((prev) => (prev.user_phone === nextPhone ? prev : { ...prev, user_phone: nextPhone }));
  }, [phoneCountryCode, phoneLocalNumber]);

  const filteredAppointmentClients = useMemo(() => {
    const q = appointmentClientSearch.trim().toLowerCase();
    const list = Array.isArray(appointmentClients) ? appointmentClients : [];
    if (!q) return list;
    return list.filter((row) =>
      String(row?.user_name || "").toLowerCase().includes(q) ||
      String(row?.user_email || "").toLowerCase().includes(q) ||
      String(row?.user_phone || "").toLowerCase().includes(q)
    );
  }, [appointmentClients, appointmentClientSearch]);

  const selectedAppointmentClient = useMemo(
    () => filteredAppointmentClients.find((row) => row?.match_key === selectedAppointmentClientKey) ||
      (appointmentClients || []).find((row) => row?.match_key === selectedAppointmentClientKey) ||
      null,
    [filteredAppointmentClients, appointmentClients, selectedAppointmentClientKey]
  );


  /* =========================
     Fetch templates
     ========================= */
  useEffect(() => {
    if (!showModal || !clientId) return;

    const fetchTemplates = async () => {
      setTemplatesLoading(true);
      try {
        const res = await authFetch(
          `${API_BASE_URL}/message_templates?client_id=${clientId}&type=appointment_reminder`
        );
        const data = await res.json();
        const filtered = (Array.isArray(data) ? data : []).filter(
          (tpl) => tpl?.type === "appointment_reminder" && isTemplateActive(tpl)
        );
        setTemplates(filtered);
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

  useEffect(() => {
    if (!showModal || !clientId || !calendarRules) return;

    const fetchGoogleBusyRanges = async () => {
      setGoogleBusyLoading(true);
      try {
        const fromDate = toDateInputValue(new Date());
        const to = new Date();
        to.setDate(to.getDate() + Number(calendarRules?.max_days_ahead || 365));
        const toDate = toDateInputValue(to);

        const res = await authFetch(
          `${API_BASE_URL}/calendar/google_busy_slots?client_id=${clientId}&from_date=${fromDate}&to_date=${toDate}`
        );
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const payload = await res.json();
        setGoogleBusyRanges(Array.isArray(payload?.busy_ranges) ? payload.busy_ranges : []);
      } catch (err) {
        console.error("Failed loading Google busy ranges", err);
        setGoogleBusyRanges([]);
      } finally {
        setGoogleBusyLoading(false);
      }
    };

    fetchGoogleBusyRanges();
  }, [showModal, clientId, calendarRules, appointmentsRefreshTick]);

  useEffect(() => {
    if (!showModal || !clientId) return;

    const fetchConfirmedAppointments = async () => {
      setAppointmentsBusyLoading(true);
      try {
        const res = await authFetch(`${API_BASE_URL}/appointments/show?client_id=${clientId}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        const rows = Array.isArray(data) ? data : [];
        const confirmed = rows.filter((appt) => String(appt?.status || "").toLowerCase() === "confirmed");
        setConfirmedAppointments(confirmed);
      } catch (err) {
        console.error("Failed loading confirmed appointments", err);
        setConfirmedAppointments([]);
      } finally {
        setAppointmentsBusyLoading(false);
      }
    };

    fetchConfirmedAppointments();
  }, [showModal, clientId, appointmentsRefreshTick]);

  useEffect(() => {
    if (!showModal || !clientId) return;
    let mounted = true;

    const fetchAppointmentClients = async () => {
      setAppointmentClientsLoading(true);
      setAppointmentClientsError("");
      try {
        const [clientsRes, profileRes] = await Promise.all([
          authFetch(`${API_BASE_URL}/appointments/clients?client_id=${clientId}`),
          authFetch(`${API_BASE_URL}/profile/${clientId}`),
        ]);

        const clientsPayload = await clientsRes.json().catch(() => ({}));
        const profilePayload = await profileRes.json().catch(() => ({}));
        if (!mounted) return;

        if (!clientsRes.ok && clientsRes.status !== 503) {
          throw new Error("clients_failed");
        }

        const nextClients = Array.isArray(clientsPayload?.clients) ? clientsPayload.clients : [];
        setAppointmentClients(nextClients);
        if (clientsRes.status === 503 || clientsPayload?.directory_available === false) {
          setAppointmentClientsError(ui.clientsDirectoryUnavailable);
        }

        const inferredCode = inferPhoneCountryCode({
          country: profilePayload?.profile?.country || "",
          timezone: profilePayload?.timezone || "",
        });
        setOwnerPhoneCountryCode(inferredCode);
        setPhoneCountryCode(inferredCode);
      } catch (err) {
        console.error("Failed loading appointment clients/profile", err);
        if (!mounted) return;
        setAppointmentClients([]);
        setAppointmentClientsError(ui.clientsLoadError);
      } finally {
        if (mounted) setAppointmentClientsLoading(false);
      }
    };

    fetchAppointmentClients();
    return () => {
      mounted = false;
    };
  }, [showModal, clientId, appointmentsRefreshTick]);

  useEffect(() => {
    if (!showModal || !clientId) return;
    let mounted = true;

    const readChannels = async (type, provider) => {
      try {
        const res = await authFetch(
          `${API_BASE_URL}/channels?client_id=${clientId}&type=${type}&provider=${provider}`
        );
        if (res.status === 404) return [];
        if (!res.ok) return [];
        const data = await res.json();
        return Array.isArray(data) ? data : [];
      } catch {
        return [];
      }
    };

    const fetchChannelStatus = async () => {
      setChannelsLoading(true);
      const [gmailRows, whatsRows] = await Promise.all([
        readChannels("email", "gmail"),
        readChannels("whatsapp", "meta"),
      ]);

      if (!mounted) return;

      const gmailPreferred = gmailRows.find((row) => isChannelEnabled(row)) || gmailRows[0];
      setGmailConnected(gmailRows.length > 0);
      setGmailEnabled(gmailRows.some((row) => isChannelEnabled(row)));
      setGmailAddress(gmailPreferred?.value || "");

      const hasActiveMeta = whatsRows.some(
        (row) => isChannelEnabled(row) && (row?.wa_phone_id || "").trim() !== ""
      );
      setWhatsAppMetaConnected(hasActiveMeta);
      setChannelsLoading(false);
    };

    fetchChannelStatus();
    return () => {
      mounted = false;
    };
  }, [showModal, clientId]);

  useEffect(() => {
    if (!whatsAppMetaConnected) {
      setReminderWhatsApp(false);
    }
  }, [whatsAppMetaConnected]);

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
      return d.toLocaleDateString(uiLocale, {
        weekday: "short",
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
      });
    } catch {
      return dateStr;
    }
  };

  const isBlockedByGoogle = (slotDate, slotDurationMinutes) => {
    const slotEnd = new Date(slotDate.getTime() + slotDurationMinutes * 60 * 1000);
    return (googleBusyRanges || []).some((range) => {
      const busyStart = new Date(range.start);
      const busyEnd = new Date(range.end);
      if (Number.isNaN(busyStart.getTime()) || Number.isNaN(busyEnd.getTime())) return false;
      return slotDate < busyEnd && slotEnd > busyStart;
    });
  };

  const isBlockedByConfirmedAppointment = (slotDate, slotDurationMinutes) => {
    const slotEnd = new Date(slotDate.getTime() + slotDurationMinutes * 60 * 1000);
    return (confirmedAppointments || []).some((appointment) => {
      const appointmentStart = new Date(appointment.scheduled_time);
      if (Number.isNaN(appointmentStart.getTime())) return false;
      const appointmentEnd = new Date(
        appointmentStart.getTime() + slotDurationMinutes * 60 * 1000
      );
      return slotDate < appointmentEnd && slotEnd > appointmentStart;
    });
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
      if (isBlockedByGoogle(slotDate, slot)) continue;
      if (isBlockedByConfirmedAppointment(slotDate, slot)) continue;
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
    if (!rules) return t("create_appointment_rules_loading");
    const days = Array.isArray(rules.selected_days) ? rules.selected_days.join(", ") : "Mon, Tue, Wed, Thu, Fri";
    const start = rules.start_time || "09:00";
    const end = rules.end_time || "18:00";
    const slot = Number(rules.slot_duration_minutes ?? 30);
    const buffer = Number(rules.buffer_minutes ?? 0);
    return `${t("create_appointment_rules_summary_prefix")} ${days} | ${t("create_appointment_rules_hours_label")} ${start}-${end} | ${t("create_appointment_rules_duration_label")} ${slot} min | ${t("create_appointment_rules_buffer_label")} ${buffer} min.`;
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
  }, [showModal, calendarRules, googleBusyRanges, confirmedAppointments]);

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
  }, [showModal, selectedDate, calendarRules, googleBusyRanges, confirmedAppointments]);

  const emailTemplates = templates.filter(
    (tpl) => tpl?.channel === "email" && tpl?.type === "appointment_reminder" && isTemplateActive(tpl)
  );
  const whatsappTemplates = templates.filter(isSelectableWhatsAppTemplate);

  /* =========================
     Derived validation (SAFE)
     ========================= */
  const hasEmail = Boolean(String(form.user_email || "").trim());
  const hasPhone = Boolean(String(form.user_phone || "").trim());
  const emailValid = !hasEmail || isValidEmail(form.user_email);
  const phoneValid = !hasPhone || isValidWhatsApp(form.user_phone);
  const hasValidEmail = hasEmail && emailValid;
  const hasValidPhone = hasPhone && phoneValid;

  const canEnableReminder = hasValidEmail || hasValidPhone;

  const canSubmit =
    normalizeAppointmentName(form.user_name) &&
    form.scheduled_time &&
    emailValid &&
    phoneValid &&
    (!enableReminder ||
      ((reminderEmail ? hasValidEmail && emailTemplateId : true) &&
        (reminderWhatsApp
          ? hasValidPhone && whatsappTemplateId
          : true)));

  useEffect(() => {
    if (!showModal) {
      prevEmailValidRef.current = false;
      return;
    }

    const becameValidEmail = !prevEmailValidRef.current && hasValidEmail;
    const hasEmailReminderTemplate = emailTemplates.length > 0;

    if (becameValidEmail && hasEmailReminderTemplate) {
      setEnableReminder(true);
      setReminderEmail(true);
      setEmailTemplateId((prev) => prev || emailTemplates[0]?.id || "");
    }

    if (hasValidEmail && reminderEmail && !emailTemplateId && hasEmailReminderTemplate) {
      setEmailTemplateId(emailTemplates[0]?.id || "");
    }

    if ((!hasValidEmail || !hasEmailReminderTemplate) && reminderEmail) {
      setReminderEmail(false);
    }

    if ((!hasValidEmail || !hasEmailReminderTemplate) && emailTemplateId) {
      setEmailTemplateId("");
    }

    prevEmailValidRef.current = hasValidEmail;
  }, [showModal, hasValidEmail, reminderEmail, emailTemplateId, emailTemplates]);

  /* =========================
     Handlers
     ========================= */
  const handleChange = (e) => {
    setForm({ ...form, [e.target.name]: e.target.value });
  };

  const handleSelectAppointmentClient = (matchKey) => {
    setSelectedAppointmentClientKey(matchKey);
    setInlineClientSaveError("");
    if (matchKey === "__new__") {
      setShowCreateClientInline(true);
      setForm((prev) => ({
        ...prev,
        user_name: "",
        user_email: "",
        user_phone: "",
      }));
      setPhoneCountryCode(ownerPhoneCountryCode || "+1");
      setPhoneLocalNumber("");
      return;
    }

    const selected = (appointmentClients || []).find((row) => row?.match_key === matchKey);
    if (!selected) return;
    const split = splitE164Phone(selected?.user_phone || "");
    setShowCreateClientInline(false);
    setForm((prev) => ({
      ...prev,
      user_name: selected?.user_name || "",
      user_email: selected?.user_email || "",
      user_phone: selected?.user_phone || "",
    }));
    setPhoneCountryCode(split.countryCode || ownerPhoneCountryCode || "+1");
    setPhoneLocalNumber(split.localNumber || "");
  };

  const handlePhoneLocalChange = (e) => {
    setPhoneLocalNumber(sanitizePhoneLocalInput(e.target.value));
  };

  const saveInlineClient = async () => {
    if (!clientId || savingClientInline) return;

    const normalizedName = normalizeAppointmentName(form.user_name);
    const normalizedEmail = normalizeAppointmentEmail(form.user_email);
    const fullPhone = composeE164Phone(phoneCountryCode, phoneLocalNumber);

    if (normalizedName.length < 2) {
      setInlineClientSaveError("El nombre debe tener al menos 2 caracteres.");
      return;
    }
    if (!isValidEmail(normalizedEmail)) {
      setInlineClientSaveError(ui.invalidEmail);
      return;
    }
    if (!isValidWhatsApp(fullPhone)) {
      setInlineClientSaveError(ui.invalidPhone);
      return;
    }
    if (!normalizedEmail && !fullPhone) {
      setInlineClientSaveError(ui.addEmailOrPhone);
      return;
    }

    setSavingClientInline(true);
    setInlineClientSaveError("");
    try {
      const res = await authFetch(`${API_BASE_URL}/appointments/clients`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          client_id: clientId,
          user_name: normalizedName,
          user_email: normalizedEmail || null,
          user_phone: fullPhone || null,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data?.detail || "No se pudo guardar el cliente.");
      }
      setShowCreateClientInline(false);
      setSelectedAppointmentClientKey("");
      setAppointmentClientSearch("");
      setAppointmentsRefreshTick((v) => v + 1);
    } catch (err) {
      setInlineClientSaveError(err.message || "No se pudo guardar el cliente.");
    } finally {
      setSavingClientInline(false);
    }
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
    setGoogleBusyRanges([]);
    setConfirmedAppointments([]);
    setAppointmentClientSearch("");
    setSelectedAppointmentClientKey("");
    setShowCreateClientInline(false);
    setInlineClientSaveError("");
    setPhoneCountryCode(ownerPhoneCountryCode || "+1");
    setPhoneLocalNumber("");
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
    const normalizedName = normalizeAppointmentName(form.user_name);
    const normalizedEmail = normalizeAppointmentEmail(form.user_email);
    const normalizedPhone = composeE164Phone(phoneCountryCode, phoneLocalNumber);

    setLoading(true);
    setSubmitError("");
    setOverlapExistingAppt(null);
    if (!replaceExisting) setDuplicateExistingAppt(null);

    try {
      const res = await authFetch(`${API_BASE_URL}/create_appointment`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          client_id: clientId,
          session_id: sessionId,
          scheduled_time: form.scheduled_time,
          user_name: normalizedName,
          user_email: hasValidEmail ? normalizedEmail : undefined,
          user_phone: hasValidPhone ? normalizedPhone : undefined,
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
        setSubmitError(data?.message || ui.timeNoLongerAvailable);
        return;
      }
      if (data?.invalid_time) {
        setSubmitError(data?.message || ui.invalidTime);
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
    <div className="ia-page" style={pageStyle}>
      {/* Header */}
      <div style={headerRow}>
        <h2 style={titleStyle}>{t("appointments_nav")}</h2>
        <button
          style={{
            ...primaryButton(disabled),
            width: isMobile ? "100%" : "auto",
          }}
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
          {t("create_appointment_disabled_message_prefix")} <strong>{t("create_appointment_calendar_setup_label")}</strong> {t("create_appointment_disabled_message_suffix")}
        </p>
      )}


      <ShowAppointments refreshKey={appointmentsRefreshTick} />


      {/* Modal */}
      {showModal && (
        <div style={modalOverlay}>
          <div
            style={{
              ...modalBox,
              width: isMobile ? "92vw" : modalBox.width,
              maxHeight: isMobile ? "88dvh" : "90dvh",
              overflowY: "auto",
            }}
          >
            <h3 style={modalTitle}>{t("new_appointment")}</h3>

            <div style={clientPickerBox}>
              <p style={clientPickerTitle}>{ui.clientsLabel}</p>
              <input
                style={inputStyle}
                placeholder={ui.clientsSearchPlaceholder}
                value={appointmentClientSearch}
                onChange={(e) => setAppointmentClientSearch(e.target.value)}
              />
              <div style={inlineRow}>
                <select
                  style={{ ...inputStyle, marginBottom: 0, flex: 1 }}
                  value={selectedAppointmentClientKey}
                  onChange={(e) => handleSelectAppointmentClient(e.target.value)}
                  disabled={appointmentClientsLoading}
                >
                  <option value="">
                    {appointmentClientsLoading ? ui.loadingClients : ui.selectOptionalClient}
                  </option>
                  {filteredAppointmentClients.map((row) => (
                    <option key={row.match_key || row.id} value={row.match_key}>
                      {row.user_name || "Cliente"}{row.user_email ? ` • ${row.user_email}` : ""}{row.user_phone ? ` • ${row.user_phone}` : ""}
                    </option>
                  ))}
                  <option value="__new__">{ui.createNewClientOption}</option>
                </select>
                <button
                  type="button"
                  style={ghostActionButton}
                  onClick={() => handleSelectAppointmentClient("__new__")}
                >
                  {ui.newClientShort}
                </button>
              </div>
              {appointmentClientsError && (
                <p style={reminderHint}>{appointmentClientsError}</p>
              )}
              {selectedAppointmentClient && (
                <p style={reminderHint}>
                  {ui.selectedClientPrefix}: <strong>{selectedAppointmentClient.user_name || ui.selectedClientFallback}</strong>
                  {selectedAppointmentClient.appointments_count ? ` • ${selectedAppointmentClient.appointments_count} ${ui.appointmentsCountSuffix}` : ""}
                </p>
              )}
              {showCreateClientInline && (
                <div style={inlineClientBox}>
                  <p style={{ ...reminderHint, marginTop: 0 }}>
                    {ui.creatingNewClientHint}
                  </p>
                  <button
                    type="button"
                    style={linkButton}
                    disabled={savingClientInline}
                    onClick={saveInlineClient}
                  >
                    {savingClientInline ? ui.saving : ui.saveClient}
                  </button>
                  {!!inlineClientSaveError && (
                    <p style={errorMsg}>{inlineClientSaveError}</p>
                  )}
                </div>
              )}
            </div>

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
            {!form.user_email && (
              <p style={reminderHint}>
                {t("create_appointment_no_email_notice")}
              </p>
            )}

            <div style={phoneInputRow}>
              <select
                style={{ ...inputStyle, marginBottom: 0, flex: "0 0 180px" }}
                value={phoneCountryCode}
                onChange={(e) => setPhoneCountryCode(e.target.value)}
              >
                {PHONE_COUNTRY_OPTIONS.map((opt) => (
                  <option key={opt.code} value={opt.code}>
                    {opt.label}
                  </option>
                ))}
              </select>
              <input
                style={{ ...inputStyle, marginBottom: 0, flex: 1 }}
                placeholder={`${t("appointment_phone_placeholder")} ${ui.phoneWithoutPrefixSuffix}`}
                value={phoneLocalNumber}
                onChange={handlePhoneLocalChange}
                inputMode="tel"
              />
            </div>
            {!phoneLocalNumber && (
              <p style={reminderHint}>
                {ui.suggestedPrefixText}: <strong>{phoneCountryCode || ownerPhoneCountryCode}</strong> {ui.suggestedPrefixReason}
              </p>
            )}
            {form.user_phone && !phoneValid && (
              <p style={reminderHint}>
                {t("use_international_phone_format")}
              </p>
            )}

            <select
              style={inputStyle}
              value={selectedDate}
              onChange={(e) => setSelectedDate(e.target.value)}
              disabled={rulesLoading || googleBusyLoading || appointmentsBusyLoading}
            >
              <option value="">
                {rulesLoading || googleBusyLoading || appointmentsBusyLoading
                  ? t("create_appointment_loading_dates")
                  : t("create_appointment_select_available_date")}
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
              disabled={!selectedDate || rulesLoading || googleBusyLoading || appointmentsBusyLoading}
            >
              <option value="">
                {!selectedDate
                  ? t("create_appointment_select_date")
                  : rulesLoading || googleBusyLoading || appointmentsBusyLoading
                  ? t("create_appointment_loading_times")
                  : t("create_appointment_select_time")}
              </option>
              {availableTimes.map((time) => (
                <option key={time} value={time}>
                  {time}
                </option>
              ))}
            </select>
            {googleBusyLoading && (
              <p style={reminderHint}>{t("create_appointment_syncing_google_busy_slots")}</p>
            )}
            {appointmentsBusyLoading && (
              <p style={reminderHint}>{t("create_appointment_validating_confirmed_busy_slots")}</p>
            )}
            {!googleBusyLoading && googleBusyRanges.length > 0 && (
              <p style={reminderHint}>
                {t("create_appointment_google_busy_slots_hidden")}
              </p>
            )}
            {!appointmentsBusyLoading && confirmedAppointments.length > 0 && (
              <p style={reminderHint}>
                {t("create_appointment_confirmed_busy_slots_hidden")}
              </p>
            )}
            {selectedDate && !rulesLoading && availableTimes.length === 0 && (
              <p style={reminderHint}>
                {t("create_appointment_no_times_for_date")}
              </p>
            )}
            {!rulesLoading && availableDates.length === 0 && (
              <p style={reminderHint}>
                {t("create_appointment_no_dates_available")}
              </p>
            )}
            <p style={timezoneNoticeStyle}>
              ⚠️ {t("appointment_timezone_notice")} <strong>{t("settings_my_profile_path")}</strong> {t("appointment_timezone_notice_end")}
            </p>
            <p style={timezoneNoticeStyle}>
              ⏱️ {t("create_appointment_select_datetime_notice_prefix")} <strong>{t("create_appointment_calendar_setup_label")}</strong>. {getFriendlyRulesText(calendarRules)}
            </p>

            <div style={integrationPanel}>
              {channelsLoading ? (
                <p style={reminderHint}>{t("create_appointment_checking_channels")}</p>
              ) : (
                <>
                  {!gmailConnected || !gmailEnabled ? (
                    <div style={warningPanel}>
                      <p style={panelTitle}>📧 {t("create_appointment_email_inactive_title")}</p>
                      <p style={panelText}>
                        {t("create_appointment_email_inactive_body_prefix")}
                        (<strong>noreply@notifications.evolvianai.com</strong>).
                      </p>
                      <button
                        type="button"
                        style={linkButton}
                        onClick={() => (window.location.href = "/services/email")}
                      >
                        {t("create_appointment_configure_email")}
                      </button>
                    </div>
                  ) : (
                    <div style={okPanel}>
                      <p style={panelTitle}>✅ {t("create_appointment_email_active_title")}</p>
                      <p style={panelText}>
                        {t("create_appointment_email_active_body_prefix")}{" "}
                        <strong>{gmailAddress || t("create_appointment_gmail_connected_fallback")}</strong>.
                      </p>
                    </div>
                  )}

                  {!whatsAppMetaConnected && (
                    <div style={dangerPanel}>
                      <p style={panelTitle}>💬 {t("create_appointment_whatsapp_unavailable_title")}</p>
                      <p style={panelText}>
                        {t("create_appointment_whatsapp_unavailable_body")}
                      </p>
                      <button
                        type="button"
                        style={linkButton}
                        onClick={() => (window.location.href = "/services/whatsapp")}
                      >
                        {t("connect_whatsapp")}
                      </button>
                    </div>
                  )}
                </>
              )}
            </div>


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
                          hasValidPhone &&
                          whatsappTemplates.length
                            ? 1
                            : 0.5,
                      }}
                    >
                      <input
                        type="checkbox"
                        checked={reminderWhatsApp}
                        disabled={
                          !hasValidPhone ||
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
                    {reminderWhatsApp && whatsappTemplates.length > 0 && (
                      <p style={{ ...reminderHint, marginTop: "0.35rem" }}>
                        {(() => {
                          const selected = whatsappTemplates.find((tpl) => tpl.id === whatsappTemplateId);
                          if (!selected) return t("create_appointment_meta_cost_generic");
                          if (!selected.billable) return t("create_appointment_meta_cost_no_direct");
                          const amount = Number(selected.estimated_unit_cost || 0).toFixed(3);
                          const currency = selected.pricing_currency || "USD";
                          return `${t("create_appointment_meta_cost_prefix")} ~$${amount} ${currency} ${t("create_appointment_meta_cost_suffix")}`;
                        })()}
                      </p>
                    )}
                    {!whatsAppMetaConnected && (
                      <p style={reminderHint}>
                        {t("create_appointment_whatsapp_reminder_setup_notice")}
                      </p>
                    )}
                  </div>

                  {/* Email */}
                  <div style={reminderBlock}>
                    <label
                      style={{
                        ...checkboxRow,
                        opacity:
                          hasValidEmail &&
                          emailTemplates.length
                            ? 1
                            : 0.5,
                      }}
                    >
                      <input
                        type="checkbox"
                        checked={reminderEmail}
                        disabled={
                          !hasValidEmail ||
                          emailTemplates.length === 0
                        }
                        onChange={(e) =>
                          setReminderEmail(e.target.checked)
                        }
                      />
                      <span style={{ marginLeft: 8 }}>
                        {t("email")}
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
                            {t("create_appointment_select_email_template")}
                          </option>
                          {emailTemplates.map((t) => (
                            <option key={t.id} value={t.id}>
                              {t.template_name} — {t.label}
                            </option>
                          ))}
                        </select>
                      )}
                    {hasValidEmail && emailTemplates.length === 0 && (
                      <p style={reminderHint}>
                        {t("create_appointment_no_email_templates_for_reminders")}
                      </p>
                    )}
                  </div>
                </>
              )}
            </div>

            {/* Actions */}
            <div
              style={{
                ...modalActions,
                flexDirection: isMobile ? "column-reverse" : "row",
                alignItems: isMobile ? "stretch" : "center",
              }}
            >
              <button
                style={{
                  ...secondaryButton,
                  width: isMobile ? "100%" : "auto",
                }}
                onClick={() => {
                  setShowModal(false);
                  resetForm();
                }}
              >
                {t("cancel")}
              </button>

              <button
                style={{
                  ...primaryButton(!canSubmit || loading),
                  width: isMobile ? "100%" : "auto",
                }}
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
                  {t("create_appointment_duplicate_existing_message_prefix")} ({formatExistingSlot(duplicateExistingAppt)}).
                </p>
                <button
                  style={replaceButton}
                  disabled={loading}
                  onClick={() => submit(true)}
                >
                  {loading ? t("processing") : t("create_appointment_replace_existing_action")}
                </button>
              </div>
            )}

            {overlapExistingAppt && (
              <p style={errorMsg}>
                {t("create_appointment_overlap_existing_message_prefix")} ({formatExistingSlot(overlapExistingAppt)}). {t("create_appointment_overlap_existing_message_suffix")}
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
  padding: "clamp(0.75rem, 0.6rem + 0.8vw, 1.25rem)",
  backgroundColor: "#FFFFFF",
  minHeight: "100%",
  fontFamily: "system-ui, sans-serif",
  color: "#274472",
};

const headerRow = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "flex-start",
  marginBottom: "1.1rem",
  gap: "0.75rem",
  flexWrap: "wrap",
};

const titleStyle = {
  fontSize: "clamp(1.3rem, 1.05rem + 1vw, 1.8rem)",
  color: "#F5A623",
  fontWeight: "bold",
  margin: 0,
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
  padding: "clamp(0.9rem, 0.8rem + 0.9vw, 1.5rem)",
  width: 440,
  boxShadow: "0 14px 34px rgba(0,0,0,0.15)",
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

const clientPickerBox = {
  border: "1px solid #EDEDED",
  backgroundColor: "#FAFBFC",
  borderRadius: 12,
  padding: "0.8rem",
  marginBottom: "0.85rem",
};

const clientPickerTitle = {
  margin: "0 0 0.45rem",
  fontSize: "0.9rem",
  fontWeight: 700,
  color: "#274472",
};

const inlineRow = {
  display: "flex",
  gap: "0.5rem",
  alignItems: "stretch",
  marginBottom: "0.5rem",
  flexWrap: "wrap",
};

const ghostActionButton = {
  border: "1px solid #EDEDED",
  backgroundColor: "#FFFFFF",
  color: "#274472",
  borderRadius: 10,
  padding: "0.5rem 0.75rem",
  cursor: "pointer",
  minWidth: 78,
};

const inlineClientBox = {
  borderTop: "1px dashed #DDE3EA",
  marginTop: "0.55rem",
  paddingTop: "0.55rem",
};

const phoneInputRow = {
  display: "flex",
  gap: "0.6rem",
  marginBottom: "0.35rem",
  flexWrap: "wrap",
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

const integrationPanel = {
  marginTop: "0.9rem",
  display: "grid",
  gap: "0.65rem",
};

const panelBase = {
  borderRadius: 10,
  border: "1px solid #EDEDED",
  padding: "0.7rem 0.8rem",
};

const warningPanel = {
  ...panelBase,
  backgroundColor: "#fff8ed",
  borderColor: "#ffd8a8",
};

const okPanel = {
  ...panelBase,
  backgroundColor: "#edf9f5",
  borderColor: "#bde9df",
};

const dangerPanel = {
  ...panelBase,
  backgroundColor: "#fff0f2",
  borderColor: "#fecdd3",
};

const panelTitle = {
  margin: 0,
  fontWeight: 700,
  color: "#274472",
  fontSize: "0.9rem",
};

const panelText = {
  margin: "0.35rem 0 0",
  color: "#4b5563",
  fontSize: "0.85rem",
  lineHeight: 1.4,
};

const linkButton = {
  marginTop: "0.55rem",
  backgroundColor: "#2EB39A",
  color: "#fff",
  border: "none",
  borderRadius: 8,
  padding: "0.45rem 0.75rem",
  cursor: "pointer",
  fontSize: "0.82rem",
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
