// 💬 Evolvian Chat Widget – Versión Final Consolidada (con Consent + CheckConsent + UI completa)
import { useState, useRef, useEffect, useMemo } from "react";
import { useLanguage } from "../contexts/LanguageContext";
import WidgetConsentScreen from "./WidgetConsentScreen";

const ASSETS_BASE_URL =
  import.meta.env.VITE_WIDGET_ASSETS_URL ||
  "https://evolvian-assistant.onrender.com/static";

const generateSessionId = () => {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `sid-${Date.now()}-${Math.random().toString(16).slice(2)}`;
};

const consentStorageKey = (publicClientId) =>
  `evolvian_widget_consent_token:${publicClientId}`;

const normalizeFeatureKey = (value) =>
  String(value || "")
    .toLowerCase()
    .trim()
    .replace(/\s+/g, "_");

const withAlpha = (color, alpha) => {
  if (!color) return `rgba(17, 24, 39, ${alpha})`;

  const rgbMatch = color.match(/^rgba?\((\d+),\s*(\d+),\s*(\d+)/i);
  if (rgbMatch) {
    return `rgba(${rgbMatch[1]}, ${rgbMatch[2]}, ${rgbMatch[3]}, ${alpha})`;
  }

  const hex = color.replace("#", "").trim();
  if (/^[0-9a-fA-F]{3}$/.test(hex)) {
    const r = parseInt(hex[0] + hex[0], 16);
    const g = parseInt(hex[1] + hex[1], 16);
    const b = parseInt(hex[2] + hex[2], 16);
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
  }

  if (/^[0-9a-fA-F]{6}$/.test(hex)) {
    const r = parseInt(hex.slice(0, 2), 16);
    const g = parseInt(hex.slice(2, 4), 16);
    const b = parseInt(hex.slice(4, 6), 16);
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
  }

  return color;
};

const resolveApiBaseUrl = () => {
  const hostname = (typeof window !== "undefined" && window.location?.hostname) || "";
  const isLocalHost =
    hostname === "localhost" ||
    hostname === "127.0.0.1" ||
    hostname === "::1" ||
    hostname === "0.0.0.0";

  return isLocalHost
    ? "http://localhost:8001"
    : "https://evolvian-assistant.onrender.com";
};

export default function ChatWidget({ clientId: propClientId, usageLimit = 100 }) {
  const languageContext = useLanguage();
  const { t = (x) => x, lang = "es", changeLanguage } = languageContext || {};
  const wt = (key, fallback) => {
    const value = t(key);
    return !value || value === key ? fallback : value;
  };

  // =============================
  // 🔹 Estados base
  // =============================
  const [publicClientId, setPublicClientId] = useState(null);
  const [assistantName, setAssistantName] = useState("Assistant");
  const [showPoweredBy, setShowPoweredBy] = useState(false);
  const [showLogo, setShowLogo] = useState(false);
  const [loading, setLoading] = useState(true);

  const [hasConsent, setHasConsent] = useState(false);
  const [consentChecked, setConsentChecked] = useState(false);
  const [clientSettings, setClientSettings] = useState({});
  const handoffFeatureEnabled = useMemo(() => {
    const rawPlanFeatures = Array.isArray(clientSettings?.plan?.plan_features)
      ? clientSettings.plan.plan_features
      : Array.isArray(clientSettings?.plan_features)
        ? clientSettings.plan_features
        : [];

    return rawPlanFeatures.some((f) => {
      if (typeof f === "string") return normalizeFeatureKey(f) === "handoff";
      if (!f || typeof f !== "object") return false;
      if (f.is_active === false) return false;
      return normalizeFeatureKey(f.feature) === "handoff";
    });
  }, [clientSettings]);
  const effectiveLang =
    String(clientSettings?.language || lang || "es").toLowerCase() === "en" ? "en" : "es";
  const isEnglish = effectiveLang === "en";
  const agendaText = useMemo(
    () =>
      isEnglish
        ? {
            loadAvailabilityError: "Could not load availability",
            calendarInactive: "Calendar is inactive for this assistant.",
            cancelNeedContact: "Add an email or phone number to find your appointment.",
            cancelValidateError: "Could not validate your appointment.",
            cancelNotFound: "We could not find an active appointment with those details.",
            cancelLookupError: "Could not search for your appointment.",
            cancelMissingAppointment: "No appointment found to cancel.",
            cancelError: "Could not cancel the appointment.",
            cancelFallbackSuccess: "Your appointment has been cancelled.",
            dayView: "Day",
            weekView: "Week",
            monthView: "Month",
            loadingSlots: "Loading available time slots...",
            selectedPrefix: "Selected:",
            nameRequired: "Name is required.",
            addContactRequired: "Add at least email or phone.",
            bookError: "Could not book the appointment.",
            bookSuccessMessage:
              "✅ Your session was booked. If you need to cancel, use the 'Find my appointment' option in Book.",
            bookSuccessStatus: "Appointment booked successfully.",
            bookingInProgress: "Booking...",
            confirmAppointment: "Confirm appointment",
            duplicateActive: "An active appointment already exists for this contact",
            replaceError: "Could not replace the appointment.",
            rescheduleSuccessMessage:
              "✅ Your session was rescheduled. If you need to cancel, use the 'Find my appointment' option in Book.",
            rescheduleSuccessStatus: "Appointment rescheduled successfully.",
            replaceCurrentWithNew: "Cancel current and create new",
            hideLookup: "Hide search",
            findMyAppointment: "Find my appointment",
            findAppointmentTitle: "Find your appointment:",
            searching: "Searching...",
            dateRangeHint: "Only dates from today up to 1 year ahead are shown.",
            timezoneLabel: "Time zone",
            sessionBookedTitle: "Session booked",
            sessionBookedBodyLine1: "Your session was booked successfully.",
            sessionBookedBodyLine2: "If you need to cancel, use the 'Find my appointment' option in Book.",
            understood: "Understood",
            confirmCancellation: "Confirm cancellation",
            foundAppointment: "We found this appointment:",
            labelName: "Name",
            labelDate: "Date",
            labelType: "Type",
            labelEmail: "Email",
            labelPhone: "Phone",
            appointmentTypeFallback: "Appointment",
            keepAppointment: "Keep appointment",
            cancelling: "Cancelling...",
            cancelAppointment: "Cancel appointment",
            noSlotsThisDay: "No available time slots this day.",
            nextAvailablePrefix: "Next available:",
            noNextSlots: "No upcoming time slots in the loaded range.",
            available: "Available",
            availableShort: "avail.",
            noDate: "no date",
          }
        : {
            loadAvailabilityError: "No se pudo cargar disponibilidad",
            calendarInactive: "El calendario está inactivo para este asistente.",
            cancelNeedContact: "Agrega email o teléfono para ubicar tu cita.",
            cancelValidateError: "No se pudo validar tu cita.",
            cancelNotFound: "No encontramos una cita activa con esos datos.",
            cancelLookupError: "No se pudo buscar tu cita.",
            cancelMissingAppointment: "No se encontró la cita a cancelar.",
            cancelError: "No se pudo cancelar la cita.",
            cancelFallbackSuccess: "Tu cita ha sido cancelada.",
            dayView: "Día",
            weekView: "Semana",
            monthView: "Mes",
            loadingSlots: "Cargando horarios disponibles...",
            selectedPrefix: "Seleccionado:",
            nameRequired: "El nombre es obligatorio.",
            addContactRequired: "Agrega al menos email o teléfono.",
            bookError: "No se pudo agendar.",
            bookSuccessMessage:
              "✅ Tu sesión fue agendada. Si necesitas cancelar, usa la opción 'Buscar mi cita' en Agendar.",
            bookSuccessStatus: "Cita agendada correctamente.",
            bookingInProgress: "Agendando...",
            confirmAppointment: "Confirmar cita",
            duplicateActive: "Ya existe una cita activa para este contacto",
            replaceError: "No se pudo reemplazar la cita.",
            rescheduleSuccessMessage:
              "✅ Tu sesión fue reagendada. Si necesitas cancelar, usa la opción 'Buscar mi cita' en Agendar.",
            rescheduleSuccessStatus: "Cita reagendada correctamente.",
            replaceCurrentWithNew: "Cancelar actual y crear nueva",
            hideLookup: "Ocultar búsqueda",
            findMyAppointment: "Buscar mi cita",
            findAppointmentTitle: "Busca tu cita:",
            searching: "Buscando...",
            dateRangeHint: "Solo se muestran fechas desde hoy y hasta 1 año adelante.",
            timezoneLabel: "Zona horaria",
            sessionBookedTitle: "Sesión agendada",
            sessionBookedBodyLine1: "Tu sesión fue agendada correctamente.",
            sessionBookedBodyLine2: 'Si necesitas cancelar, usa la opción "Buscar mi cita" en Agendar.',
            understood: "Entendido",
            confirmCancellation: "Confirmar cancelación",
            foundAppointment: "Encontramos esta cita:",
            labelName: "Nombre",
            labelDate: "Fecha",
            labelType: "Tipo",
            labelEmail: "Email",
            labelPhone: "Teléfono",
            appointmentTypeFallback: "Cita",
            keepAppointment: "Mantener cita",
            cancelling: "Cancelando...",
            cancelAppointment: "Cancelar cita",
            noSlotsThisDay: "No hay horarios disponibles este día.",
            nextAvailablePrefix: "Próximo disponible:",
            noNextSlots: "No hay próximos horarios en el rango cargado.",
            available: "Disponible",
            availableShort: "disp.",
            noDate: "sin fecha",
          },
    [isEnglish]
  );

  // =============================
  // ⚡️ Nuevos estados visuales
  // =============================
  const [showTooltip, setShowTooltip] = useState(false);
  const [tooltipText, setTooltipText] = useState("");
  const [tooltipBg, setTooltipBg] = useState("#FFF8E1");
  const [tooltipColor, setTooltipColor] = useState("#5C4B00");

  const [showLegalLinks, setShowLegalLinks] = useState(false);
  const [termsUrl, setTermsUrl] = useState("");
  const [privacyUrl, setPrivacyUrl] = useState("");
  const [widgetOpeningTemplate, setWidgetOpeningTemplate] = useState(null);

  const [theme, setTheme] = useState({
    headerColor: "#fff9f0",
    headerTextColor: "#1b2a41",
    backgroundColor: "#ffffff",
    userMessageColor: "#a3d9b1",
    botMessageColor: "#f7f7f7",
    buttonColor: "#f5a623",
    buttonTextColor: "#ffffff",
    footerTextColor: "#999999",
    fontFamily: "'Inter', sans-serif",
    widgetHeight: 420,
    widgetRadius: 16,
  });
  const [isMobileLayout, setIsMobileLayout] = useState(() =>
    typeof window !== "undefined"
      ? window.matchMedia("(max-width: 640px)").matches
      : false
  );
  const aura = useMemo(
    () => ({
      wrapperBg: `radial-gradient(130% 120% at 0% 0%, ${withAlpha(theme.buttonColor, 0.15)} 0%, ${withAlpha(theme.backgroundColor, 0.98)} 44%, ${theme.backgroundColor} 100%)`,
      panelShadow: `0 18px 42px ${withAlpha(theme.headerTextColor, 0.18)}`,
      border: withAlpha(theme.headerTextColor, 0.08),
      softBorder: withAlpha(theme.headerTextColor, 0.12),
      headerBg: `linear-gradient(135deg, ${withAlpha(theme.headerColor, 0.96)} 0%, ${withAlpha(theme.buttonColor, 0.14)} 100%)`,
      messagesBg: `linear-gradient(180deg, ${withAlpha(theme.backgroundColor, 0.84)} 0%, ${withAlpha(theme.buttonColor, 0.05)} 100%)`,
      inputBg: withAlpha(theme.backgroundColor, 0.82),
      inputBorder: withAlpha(theme.headerTextColor, 0.16),
      mutedText: withAlpha(theme.headerTextColor, 0.58),
      buttonShadow: `0 10px 24px ${withAlpha(theme.buttonColor, 0.28)}`,
    }),
    [theme]
  );

  // =============================
  // 💬 Mensajería
  // =============================
  const [sessionId, setSessionId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [thinkingDots, setThinkingDots] = useState("");
  const [, setUsageCount] = useState(0);
  const [usageLimitReached, setUsageLimitReached] = useState(false);
  const [showHumanHandoffPrompt, setShowHumanHandoffPrompt] = useState(false);
  const [humanHandoffFormOpen, setHumanHandoffFormOpen] = useState(false);
  const [humanHandoffSubmitted, setHumanHandoffSubmitted] = useState(false);
  const [humanHandoffSubmitting, setHumanHandoffSubmitting] = useState(false);
  const [humanHandoffError, setHumanHandoffError] = useState("");
  const [humanHandoffSuccess, setHumanHandoffSuccess] = useState("");
  const [humanHandoffTrigger, setHumanHandoffTrigger] = useState("manual_request");
  const [humanHandoffReason, setHumanHandoffReason] = useState("user_requested_human");
  const [humanHandoffLastAiMessage, setHumanHandoffLastAiMessage] = useState("");
  const [humanHandoffName, setHumanHandoffName] = useState("");
  const [humanHandoffEmail, setHumanHandoffEmail] = useState("");
  const [humanHandoffPhone, setHumanHandoffPhone] = useState("");
  const [humanHandoffAcceptedTerms, setHumanHandoffAcceptedTerms] = useState(false);
  const [humanHandoffAcceptedMarketing, setHumanHandoffAcceptedMarketing] = useState(false);
  const messagesEndRef = useRef(null);
  const openingTemplateInjectedRef = useRef(false);
  const lastSendTriggerAtRef = useRef(0);
  const [activePanel, setActivePanel] = useState("chat");
  const [calendarViewMode, setCalendarViewMode] = useState("month");
  const [calendarDate, setCalendarDate] = useState(new Date());
  const [calendarSlots, setCalendarSlots] = useState([]);
  const [calendarCountsByDay, setCalendarCountsByDay] = useState({});
  const [calendarLoading, setCalendarLoading] = useState(false);
  const [calendarError, setCalendarError] = useState("");
  const [calendarTimezone, setCalendarTimezone] = useState("");
  const [calendarEnabled, setCalendarEnabled] = useState(true);
  const [showAgendaButton, setShowAgendaButton] = useState(false);
  const [selectedCalendarSlot, setSelectedCalendarSlot] = useState(null);
  const [bookingName, setBookingName] = useState("");
  const [bookingEmail, setBookingEmail] = useState("");
  const [bookingPhone, setBookingPhone] = useState("");
  const [bookingSubmitting, setBookingSubmitting] = useState(false);
  const [bookingError, setBookingError] = useState("");
  const [bookingSuccess, setBookingSuccess] = useState("");
  const [calendarRefreshTick, setCalendarRefreshTick] = useState(0);
  const [duplicateExistingAppt, setDuplicateExistingAppt] = useState(null);
  const [showBookingSuccessModal, setShowBookingSuccessModal] = useState(false);
  const [showCancelLookup, setShowCancelLookup] = useState(false);
  const [cancelEmail, setCancelEmail] = useState("");
  const [cancelPhone, setCancelPhone] = useState("");
  const [cancelLookupLoading, setCancelLookupLoading] = useState(false);
  const [cancelSubmitting, setCancelSubmitting] = useState(false);
  const [cancelError, setCancelError] = useState("");
  const [cancelSuccess, setCancelSuccess] = useState("");
  const [cancelPreviewAppt, setCancelPreviewAppt] = useState(null);
  const [showCancelConfirmModal, setShowCancelConfirmModal] = useState(false);
  const requireConsentForChat =
    Boolean(clientSettings?.require_email_consent) ||
    Boolean(clientSettings?.require_terms_consent);

  // =============================
  // 🧭 Detectar publicClientId
  // =============================
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const urlClientId = params.get("public_client_id");
    const urlView = params.get("view");
    if (propClientId) setPublicClientId(propClientId);
    else if (urlClientId) setPublicClientId(urlClientId);
    if (urlView === "calendar") setActivePanel("calendar");
  }, [propClientId]);

  useEffect(() => {
    const handleViewMessage = (event) => {
      const payload = event?.data;
      if (!payload || payload.type !== "EVOLVIAN_WIDGET_VIEW") return;
      if (payload.view === "calendar" && calendarEnabled && showAgendaButton) setActivePanel("calendar");
      if (payload.view === "chat") setActivePanel("chat");
    };

    window.addEventListener("message", handleViewMessage);
    return () => window.removeEventListener("message", handleViewMessage);
  }, [calendarEnabled, showAgendaButton]);

  useEffect(() => {
    if (typeof window === "undefined") return undefined;
    const mediaQuery = window.matchMedia("(max-width: 640px)");
    const onChange = (event) => setIsMobileLayout(event.matches);

    setIsMobileLayout(mediaQuery.matches);
    if (mediaQuery.addEventListener) {
      mediaQuery.addEventListener("change", onChange);
      return () => mediaQuery.removeEventListener("change", onChange);
    }

    mediaQuery.addListener(onChange);
    return () => mediaQuery.removeListener(onChange);
  }, []);

  // =============================
  // 🧠 Generar sessionId persistente
  // =============================
  useEffect(() => {
    let sid = null;
    try {
      sid = localStorage.getItem("evolvian_session_id");
      if (!sid) {
        sid = generateSessionId();
        localStorage.setItem("evolvian_session_id", sid);
      }
    } catch {
      sid = generateSessionId();
    }
    setSessionId(sid);
  }, []);

  // =============================
  // 🧾 Verificar consentimiento
  // =============================
  useEffect(() => {
    const checkConsentStatus = async () => {
      if (!publicClientId) return;
      try {
        let consentToken = null;
        try {
          consentToken = localStorage.getItem(consentStorageKey(publicClientId));
        } catch {
          consentToken = null;
        }

        const apiUrl = resolveApiBaseUrl();

        const params = new URLSearchParams({ public_client_id: publicClientId });
        if (consentToken) {
          params.set("consent_token", consentToken);
        }

        const res = await fetch(`${apiUrl}/check_consent?${params.toString()}`);
        const data = await res.json();
        setHasConsent(!!data.valid);

        if (data?.consent_token) {
          try {
            localStorage.setItem(consentStorageKey(publicClientId), data.consent_token);
          } catch {
            // ignore storage failures in embedded contexts
          }
        } else if (!data?.valid && consentToken) {
          try {
            localStorage.removeItem(consentStorageKey(publicClientId));
          } catch {
            // ignore storage failures
          }
        }
      } catch {
        setHasConsent(false);
      } finally {
        setConsentChecked(true);
      }
    };
    checkConsentStatus();
  }, [publicClientId]);

  // =============================
  // 🧾 Obtener configuración cliente
  // =============================
  useEffect(() => {
    const fetchClientSettings = async () => {
      if (!publicClientId) return;
      setLoading(true);
      try {
        const apiUrl = resolveApiBaseUrl();

        const res = await fetch(`${apiUrl}/client_settings?public_client_id=${publicClientId}`);
        const raw = await res.json();
        const data = Array.isArray(raw) ? raw[0] : raw;
        if (!data) return;

        if (typeof data.language === "string" && data.language.trim()) {
          changeLanguage?.(data.language);
        }

        setClientSettings(data);
        setAssistantName(data.assistant_name || "Assistant");
        setShowPoweredBy(!!data.show_powered_by);
        setShowLogo(!!data.show_logo);
        setShowTooltip(!!data.show_tooltip);
        setTooltipText(data.tooltip_text || "");
        setTooltipBg(data.tooltip_bg_color || "#FFF8E1");
        setTooltipColor(data.tooltip_text_color || "#5C4B00");

        setShowLegalLinks(!!data.show_legal_links);
        setTermsUrl(data.terms_url || "");
        setPrivacyUrl(data.privacy_url || "");
        setWidgetOpeningTemplate(data.widget_opening_template || null);

        if (["premium", "white_label"].includes(data.plan?.id)) {
          setTheme({
            headerColor: data.header_color || "#fff9f0",
            headerTextColor: data.header_text_color || "#1b2a41",
            backgroundColor: data.background_color || "#ffffff",
            userMessageColor: data.user_message_color || "#a3d9b1",
            botMessageColor: data.bot_message_color || "#f7f7f7",
            buttonColor: data.button_color || "#f5a623",
            buttonTextColor: data.button_text_color || "#ffffff",
            footerTextColor: data.footer_text_color || "#999999",
            fontFamily: data.font_family || "'Inter', sans-serif",
            widgetHeight: data.widget_height || 420,
            widgetRadius: data.widget_border_radius || 16,
          });
        }
      } catch (err) {
        console.warn("⚠️ No se pudo cargar configuración:", err);
        setWidgetOpeningTemplate(null);
      } finally {
        setLoading(false);
      }
    };
    fetchClientSettings();
  }, [publicClientId]);

  useEffect(() => {
    openingTemplateInjectedRef.current = false;
  }, [publicClientId]);

  useEffect(() => {
    if (openingTemplateInjectedRef.current) return;
    if (!publicClientId || loading || !consentChecked) return;
    if (activePanel !== "chat") return;
    if (messages.length > 0) return;

    if (requireConsentForChat && !hasConsent) return;

    const openingText = String(widgetOpeningTemplate?.body || "").trim();
    if (!openingText) return;

    openingTemplateInjectedRef.current = true;
    const timestamp = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    setMessages((prev) =>
      prev.length > 0 ? prev : [{ from: "bot", text: openingText, timestamp }]
    );
  }, [
    activePanel,
    clientSettings,
    consentChecked,
    hasConsent,
    loading,
    messages.length,
    publicClientId,
    requireConsentForChat,
    widgetOpeningTemplate,
  ]);

  // =============================
  // 🔄 Auto-scroll
  // =============================
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // =============================
  // 💭 Animación “pensando...”
  // =============================
  useEffect(() => {
    let interval;
    if (sending) {
      interval = setInterval(() => {
        setThinkingDots((prev) => (prev.length >= 3 ? "" : prev + "."));
      }, 400);
    } else setThinkingDots("");
    return () => clearInterval(interval);
  }, [sending]);

  useEffect(() => {
    if (hasConsent) {
      setHumanHandoffAcceptedTerms(true);
    }
  }, [hasConsent]);

  useEffect(() => {
    if (handoffFeatureEnabled) return;
    setShowHumanHandoffPrompt(false);
    setHumanHandoffFormOpen(false);
  }, [handoffFeatureEnabled]);

  // =============================
  // 💬 Enviar mensaje
  // =============================
  const openHumanHandoffPrompt = ({
    trigger = "manual_request",
    reason = "user_requested_human",
    aiMessage = "",
  } = {}) => {
    if (!handoffFeatureEnabled) return;
    setShowHumanHandoffPrompt(true);
    if (!humanHandoffSubmitted) setHumanHandoffFormOpen(true);
    setHumanHandoffError("");
    setHumanHandoffSuccess("");
    setHumanHandoffTrigger(trigger);
    setHumanHandoffReason(reason);
    if (aiMessage) setHumanHandoffLastAiMessage(aiMessage);
  };

  const submitHumanHandoffRequest = async () => {
    if (!publicClientId) return;
    if (!handoffFeatureEnabled) {
      setHumanHandoffError(
        wt(
          "widget_handoff_premium_required",
          "Human follow-up is available on the Premium plan."
        )
      );
      return;
    }
    const userName = humanHandoffName.trim();
    const email = humanHandoffEmail.trim();
    const phone = humanHandoffPhone.trim();

    if (!userName) {
      setHumanHandoffError(wt("widget_handoff_name_required", "Please share your name."));
      return;
    }
    if (!email && !phone) {
      setHumanHandoffError(
        wt("widget_handoff_contact_required", "Please share an email or phone number.")
      );
      return;
    }
    if (!humanHandoffAcceptedTerms) {
      setHumanHandoffError(
        wt("widget_handoff_terms_required", "Please accept the terms to request human follow-up.")
      );
      return;
    }

    setHumanHandoffSubmitting(true);
    setHumanHandoffError("");

    try {
      const lastUserMessage =
        [...messages].reverse().find((m) => m?.from === "user")?.text || "";
      const lastBotMessage =
        humanHandoffLastAiMessage ||
        [...messages].reverse().find((m) => m?.from === "bot")?.text ||
        "";

      let consentToken = null;
      try {
        consentToken = localStorage.getItem(consentStorageKey(publicClientId));
      } catch {
        consentToken = null;
      }

      const apiUrl = resolveApiBaseUrl();
      const res = await fetch(`${apiUrl}/widget/handoff/request`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          public_client_id: publicClientId,
          session_id: sessionId || generateSessionId(),
          channel: "widget",
          trigger: humanHandoffTrigger || "manual_request",
          reason: humanHandoffReason || "user_requested_human",
          user_name: userName,
          email: email || null,
          phone: phone || null,
          accepted_terms: !!humanHandoffAcceptedTerms,
          accepted_email_marketing: !!humanHandoffAcceptedMarketing,
          consent_token: consentToken || null,
          last_user_message: lastUserMessage || null,
          last_ai_message: lastBotMessage || null,
          language: effectiveLang,
        }),
      });

      const data = await res.json();
      if (!res.ok) {
        if (res.status === 403) {
          throw new Error(
            wt(
              "widget_handoff_premium_required",
              "Human follow-up is available on the Premium plan."
            )
          );
        }
        throw new Error(data?.detail || `HTTP ${res.status}`);
      }

      if (data?.consent_token) {
        try {
          localStorage.setItem(consentStorageKey(publicClientId), data.consent_token);
        } catch {
          // ignore storage failures
        }
      }

      if (data?.confirmation_message) {
        setHumanHandoffSuccess(data.confirmation_message);
      }
      if (data?.fallback_message) {
        const now = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
        setMessages((prev) => [...prev, { from: "bot", text: data.fallback_message, timestamp: now }]);
      }

      setHumanHandoffSubmitted(true);
      setHumanHandoffFormOpen(false);
      setShowHumanHandoffPrompt(true);
    } catch (err) {
      setHumanHandoffError(
        err?.message || wt("widget_handoff_submit_error", "Could not request human follow-up.")
      );
    } finally {
      setHumanHandoffSubmitting(false);
    }
  };

  const sendMessage = async (overrideText = null) => {
    const outboundText = (overrideText ?? input).trim();
    if (!outboundText || usageLimitReached) return;
    if (sending) return;
    if (!publicClientId) return;

    let effectiveSessionId = sessionId;
    if (!effectiveSessionId) {
      effectiveSessionId = generateSessionId();
      setSessionId(effectiveSessionId);
      try {
        localStorage.setItem("evolvian_session_id", effectiveSessionId);
      } catch {
        // Ignore storage failures in restricted iframe/mobile environments.
      }
    }

    const now = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    const userMsg = { from: "user", text: outboundText, timestamp: now };
    setMessages((prev) => [...prev, userMsg]);
    if (!overrideText) setInput("");
    setSending(true);

    try {
      const apiUrl = resolveApiBaseUrl();

      const res = await fetch(`${apiUrl}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          public_client_id: publicClientId,
          session_id: effectiveSessionId,
          message: userMsg.text,
          channel: "widget",
        }),
      });

      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }

      const data = await res.json();
      const botMsg = {
        from: "bot",
        text: data.answer || "(respuesta vacía)",
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      };
      setMessages((prev) => [...prev, botMsg]);

      setUsageCount((prev) => {
        const next = prev + 1;
        if (next >= usageLimit) setUsageLimitReached(true);
        return next;
      });

      if (data?.limit_reached) {
        setUsageLimitReached(true);
        openHumanHandoffPrompt({
          trigger: "usage_limit",
          reason: "session_limit_reached",
          aiMessage: botMsg.text,
        });
      } else if (data?.needs_human || data?.handoff_recommended || data?.human_intervention_recommended) {
        openHumanHandoffPrompt({
          trigger: "ai_handoff_recommended",
          reason: data?.handoff_reason || "low_confidence",
          aiMessage: botMsg.text,
        });
      }
    } catch (err) {
      console.error("❌ Error al enviar mensaje:", err);
      const fallback = {
        from: "bot",
        text: t("send_error") || "No se pudo enviar el mensaje. Intenta nuevamente.",
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      };
      setMessages((prev) => [...prev, fallback]);
      openHumanHandoffPrompt({
        trigger: "chat_error",
        reason: "delivery_error",
        aiMessage: fallback.text,
      });
    } finally {
      setSending(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const triggerSendFromUi = () => {
    const now = Date.now();
    if (now - lastSendTriggerAtRef.current < 320) return;
    lastSendTriggerAtRef.current = now;
    sendMessage();
  };

  const handleSendButtonClick = () => triggerSendFromUi();

  const handleSendButtonTouchEnd = () => triggerSendFromUi();

  const handleSendButtonPointerUp = () => triggerSendFromUi();

  const todayStart = useMemo(() => {
    const tday = new Date();
    tday.setHours(0, 0, 0, 0);
    return tday;
  }, []);

  const maxForwardDate = useMemo(() => {
    const max = new Date();
    max.setFullYear(max.getFullYear() + 1);
    max.setHours(23, 59, 59, 999);
    return max;
  }, []);

  const goCalendarPrev = () => {
    const next = new Date(calendarDate);
    if (calendarViewMode === "day") next.setDate(next.getDate() - 1);
    if (calendarViewMode === "week") next.setDate(next.getDate() - 7);
    if (calendarViewMode === "month") next.setMonth(next.getMonth() - 1);
    if (next < todayStart) return;
    setCalendarDate(next);
  };

  const goCalendarNext = () => {
    const next = new Date(calendarDate);
    if (calendarViewMode === "day") next.setDate(next.getDate() + 1);
    if (calendarViewMode === "week") next.setDate(next.getDate() + 7);
    if (calendarViewMode === "month") next.setMonth(next.getMonth() + 1);
    if (next > maxForwardDate) return;
    setCalendarDate(next);
  };

  const calendarTitle = useMemo(() => {
    const locale = isEnglish ? "en-US" : "es-ES";
    if (calendarViewMode === "month") {
      return calendarDate.toLocaleDateString(locale, {
        month: "long",
        year: "numeric",
      });
    }
    if (calendarViewMode === "week") {
      const start = new Date(calendarDate);
      start.setDate(start.getDate() - start.getDay());
      const end = new Date(start);
      end.setDate(end.getDate() + 6);
      return `${start.toLocaleDateString(locale)} - ${end.toLocaleDateString(locale)}`;
    }
    return calendarDate.toLocaleDateString(locale);
  }, [calendarDate, calendarViewMode, isEnglish]);

  const formatDuplicateSlot = (existing) => {
    if (!existing) return agendaText.noDate;
    if (existing.formatted_time) return existing.formatted_time;
    const raw = existing.scheduled_time;
    if (!raw) return agendaText.noDate;
    try {
      const dt = new Date(raw);
      if (Number.isNaN(dt.getTime())) return raw;
      const local = dt.toLocaleString(isEnglish ? "en-US" : "es-ES", {
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        hour12: false,
        timeZone: calendarTimezone || undefined,
      });
      return calendarTimezone ? `${local} (${calendarTimezone})` : local;
    } catch {
      return raw;
    }
  };

  const formatDateKey = (dateObj) => {
    const year = dateObj.getFullYear();
    const month = String(dateObj.getMonth() + 1).padStart(2, "0");
    const day = String(dateObj.getDate()).padStart(2, "0");
    return `${year}-${month}-${day}`;
  };

  const calendarRange = useMemo(() => {
    let start = new Date(calendarDate);
    let end = new Date(calendarDate);

    if (calendarViewMode === "week") {
      start.setDate(start.getDate() - start.getDay());
      end = new Date(start);
      end.setDate(end.getDate() + 6);
    }

    if (calendarViewMode === "month") {
      start = new Date(calendarDate.getFullYear(), calendarDate.getMonth(), 1);
      end = new Date(calendarDate.getFullYear(), calendarDate.getMonth() + 1, 0);
    }
    if (calendarViewMode === "day") {
      end = new Date(calendarDate);
      end.setDate(end.getDate() + 30);
    }

    if (start < todayStart) start = new Date(todayStart);
    if (end > maxForwardDate) end = new Date(maxForwardDate);
    if (end < start) end = new Date(start);

    return { from: formatDateKey(start), to: formatDateKey(end) };
  }, [calendarDate, calendarViewMode, todayStart, maxForwardDate]);

  useEffect(() => {
    if (!publicClientId) return;

    const loadCalendarVisibility = async () => {
      try {
        const apiUrl = resolveApiBaseUrl();
        const url = new URL(`${apiUrl}/widget/calendar/visibility`);
        url.searchParams.set("public_client_id", publicClientId);
        const res = await fetch(url.toString());
        const data = await res.json();
        if (!res.ok) {
          throw new Error(
            data?.detail || (isEnglish ? "Could not load calendar visibility" : "No se pudo cargar visibilidad de agenda")
          );
        }

        const showAgenda = Boolean(data?.show_agenda_in_chat_widget ?? false);
        const status = String(data?.calendar_status || "inactive").toLowerCase();
        setShowAgendaButton(showAgenda);
        setCalendarEnabled(status === "active");

        if (!showAgenda && activePanel === "calendar") {
          setActivePanel("chat");
        }
      } catch {
        // Fail-closed for visibility: keep agenda hidden unless explicitly enabled.
        setShowAgendaButton(false);
        if (activePanel === "calendar") {
          setActivePanel("chat");
        }
      }
    };

    loadCalendarVisibility();
  }, [publicClientId, activePanel, isEnglish]);

  useEffect(() => {
    if (activePanel !== "calendar" || !publicClientId) return;

    const fetchAvailability = async () => {
      setCalendarLoading(true);
      setCalendarError("");

      try {
        const apiUrl = resolveApiBaseUrl();

        const url = new URL(`${apiUrl}/widget/calendar/availability`);
        url.searchParams.set("public_client_id", publicClientId);
        url.searchParams.set("from_date", calendarRange.from);
        url.searchParams.set("to_date", calendarRange.to);

        const res = await fetch(url.toString());
        const data = await res.json();
        if (!res.ok) {
          throw new Error(data?.detail || agendaText.loadAvailabilityError);
        }
        if (data?.available === false) {
          setCalendarEnabled(false);
          setCalendarSlots([]);
          setCalendarCountsByDay({});
          setCalendarTimezone(data.timezone || "");
          setCalendarError(data?.message || agendaText.calendarInactive);
          return;
        }

        setCalendarSlots(Array.isArray(data.slots) ? data.slots : []);
        setCalendarCountsByDay(data.counts_by_day || {});
        setCalendarTimezone(data.timezone || "");
      } catch (err) {
        setCalendarSlots([]);
        setCalendarCountsByDay({});
        setCalendarError(err?.message || agendaText.loadAvailabilityError);
      } finally {
        setCalendarLoading(false);
      }
    };

    fetchAvailability();
  }, [activePanel, publicClientId, calendarRange, calendarRefreshTick, agendaText]);

  useEffect(() => {
    if (!selectedCalendarSlot) return;
    const stillExists = calendarSlots.some((slot) => slot.start_iso === selectedCalendarSlot.start_iso);
    if (!stillExists) setSelectedCalendarSlot(null);
  }, [calendarSlots, selectedCalendarSlot]);

  useEffect(() => {
    setBookingError("");
    setBookingSuccess("");
    setDuplicateExistingAppt(null);
  }, [selectedCalendarSlot]);

  useEffect(() => {
    if (activePanel !== "calendar") {
      setShowCancelLookup(false);
      setShowCancelConfirmModal(false);
      setCancelPreviewAppt(null);
      setCancelError("");
    }
  }, [activePanel]);

  const lookupAppointmentForCancellation = async () => {
    if (!cancelEmail.trim() && !cancelPhone.trim()) {
      setCancelError(agendaText.cancelNeedContact);
      return;
    }

    setCancelLookupLoading(true);
    setCancelError("");
    setCancelSuccess("");
    setCancelPreviewAppt(null);

    try {
      const apiUrl = resolveApiBaseUrl();
      const res = await fetch(`${apiUrl}/widget/calendar/cancel/lookup`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          public_client_id: publicClientId,
          user_email: cancelEmail.trim() || null,
          user_phone: cancelPhone.trim() || null,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data?.detail || data?.message || agendaText.cancelValidateError);
      }
      if (!data?.found || !data?.appointment) {
        setCancelError(data?.message || agendaText.cancelNotFound);
        return;
      }

      setCancelPreviewAppt(data.appointment);
      setShowCancelConfirmModal(true);
    } catch (err) {
      setCancelError(err?.message || agendaText.cancelLookupError);
    } finally {
      setCancelLookupLoading(false);
    }
  };

  const confirmWidgetCancellation = async () => {
    if (!cancelPreviewAppt?.id) {
      setCancelError(agendaText.cancelMissingAppointment);
      return;
    }

    setCancelSubmitting(true);
    setCancelError("");

    try {
      const apiUrl = resolveApiBaseUrl();
      const res = await fetch(`${apiUrl}/widget/calendar/cancel/confirm`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          public_client_id: publicClientId,
          appointment_id: cancelPreviewAppt.id,
          user_email: cancelEmail.trim() || null,
          user_phone: cancelPhone.trim() || null,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data?.detail || data?.message || agendaText.cancelError);
      }

      const finalMessage = data?.message || agendaText.cancelFallbackSuccess;
      const now = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
      setMessages((prev) => [...prev, { from: "bot", text: `✅ ${finalMessage}`, timestamp: now }]);
      setCancelSuccess(finalMessage);
      setShowCancelConfirmModal(false);
      setCancelPreviewAppt(null);
      setCalendarRefreshTick((v) => v + 1);
    } catch (err) {
      setCancelError(err?.message || agendaText.cancelError);
    } finally {
      setCancelSubmitting(false);
    }
  };

  // ===================================================
  // 🧾 Mostrar PANTALLA DE CONSENTIMIENTO
  // ===================================================
  if (
    consentChecked &&
    publicClientId &&
    Object.keys(clientSettings).length > 0
  ) {
    const requireEmailConsent = Boolean(clientSettings.require_email_consent);
    const requireTermsConsent = Boolean(clientSettings.require_terms_consent);
    const requireConsent =
      requireEmailConsent || requireTermsConsent;

    if (!hasConsent && requireConsent) {
      return (
        <WidgetConsentScreen
          publicClientId={publicClientId}
          requireEmailConsent={requireEmailConsent}
          requireTermsConsent={requireTermsConsent}
          showLegalLinks={showLegalLinks}
          clientSettings={clientSettings}
          onConsentComplete={() => setHasConsent(true)}
        />
      );
    }
  }

  // =============================
  // 🌀 Loading
  // =============================
  if (loading || !consentChecked) {
    return (
      <div
        style={{
          ...styles.wrapper,
          display: "flex",
          justifyContent: "center",
          alignItems: "center",
          color: "#999",
        }}
      >
        {t("loading") || "Loading..."}
      </div>
    );
  }
  const effectiveWidgetRadius = isMobileLayout ? 12 : theme.widgetRadius;
  const canShowOpeningTemplate =
    !loading &&
    consentChecked &&
    !(requireConsentForChat && !hasConsent);
  const openingTemplateText = String(widgetOpeningTemplate?.body || "").trim();
  const renderedMessages =
    messages.length === 0 && activePanel === "chat" && canShowOpeningTemplate && openingTemplateText
      ? [{ from: "bot", text: openingTemplateText, timestamp: "" }]
      : messages;

  // =============================
  // 💬 RENDER PRINCIPAL
  // =============================
  return (
    <div
      style={{
        ...styles.wrapper,
        position: "relative",
        background: aura.wrapperBg,
        minHeight: isMobileLayout ? "100%" : `${theme.widgetHeight}px`,
        borderRadius: `${effectiveWidgetRadius}px`,
        fontFamily: theme.fontFamily,
        border: `1px solid ${aura.border}`,
        boxShadow: aura.panelShadow,
        backdropFilter: "blur(12px)",
      }}
    >
      {/* 🧠 Tooltip */}
      {showTooltip && tooltipText && (
        <div
          style={{
            backgroundColor: tooltipBg,
            color: tooltipColor,
            fontSize: "0.8rem",
            textAlign: "center",
            padding: "0.4rem 0.8rem",
            borderTopLeftRadius: `${effectiveWidgetRadius}px`,
            borderTopRightRadius: `${effectiveWidgetRadius}px`,
            borderBottom: `1px solid ${aura.softBorder}`,
            backdropFilter: "blur(6px)",
          }}
        >
          {tooltipText}
        </div>
      )}

      {/* Header */}
      <div
        style={{
          ...styles.header,
          ...(isMobileLayout ? styles.headerMobile : null),
          background: aura.headerBg,
          borderBottom: `1px solid ${aura.softBorder}`,
          backdropFilter: "blur(10px)",
        }}
      >
        <div style={{ ...styles.headerLeft, ...(isMobileLayout ? styles.headerLeftMobile : null) }}>
          {showLogo && (
            <img
              src={`${ASSETS_BASE_URL}/logo-evolvian.svg`}
              alt="Evolvian"
              style={{ height: "22px", marginRight: "0.6rem" }}
              onError={(e) => (e.currentTarget.style.display = "none")}
            />
          )}
          <strong
            style={{
              fontSize: isMobileLayout ? "0.95rem" : "1rem",
              color: theme.headerTextColor,
              ...(isMobileLayout
                ? {
                    whiteSpace: "nowrap",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    maxWidth: "58vw",
                  }
                : null),
            }}
          >
            {assistantName}
          </strong>
        </div>
        <div style={{ ...styles.headerActions, ...(isMobileLayout ? styles.headerActionsMobile : null) }}>
          <button
            style={{
              ...styles.headerActionBtn,
              ...(isMobileLayout ? styles.headerActionBtnMobile : null),
              background:
                activePanel === "chat"
                  ? `linear-gradient(135deg, ${withAlpha(theme.buttonColor, 0.92)} 0%, ${theme.buttonColor} 100%)`
                  : withAlpha(theme.backgroundColor, 0.72),
              color:
                activePanel === "chat"
                  ? theme.buttonTextColor
                  : withAlpha(theme.headerTextColor, 0.88),
              border: `1px solid ${activePanel === "chat" ? withAlpha(theme.buttonColor, 0.56) : aura.softBorder}`,
              boxShadow: activePanel === "chat" ? aura.buttonShadow : "none",
            }}
            onClick={() => setActivePanel("chat")}
          >
            Chat
          </button>
          {showAgendaButton && (
            <button
              style={{
                ...styles.headerActionBtn,
                ...(isMobileLayout ? styles.headerActionBtnMobile : null),
                background:
                  activePanel === "calendar"
                    ? `linear-gradient(135deg, ${withAlpha(theme.buttonColor, 0.92)} 0%, ${theme.buttonColor} 100%)`
                    : withAlpha(theme.backgroundColor, 0.72),
                color:
                  activePanel === "calendar"
                    ? theme.buttonTextColor
                    : withAlpha(theme.headerTextColor, 0.88),
                border: `1px solid ${activePanel === "calendar" ? withAlpha(theme.buttonColor, 0.56) : aura.softBorder}`,
                boxShadow: activePanel === "calendar" ? aura.buttonShadow : "none",
              }}
              onClick={() => setActivePanel("calendar")}
            >
              {wt("widget_book_tab", isEnglish ? "Book" : "Agenda")}
            </button>
          )}
        </div>
      </div>

      {activePanel === "chat" ? (
        <div
          style={{
            ...styles.messages,
            ...(isMobileLayout ? styles.messagesMobile : null),
            background: aura.messagesBg,
          }}
        >
          {renderedMessages.map((msg, idx) => (
            <div
              key={idx}
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: msg.from === "user" ? "flex-end" : "flex-start",
              }}
            >
              <div
                style={{
                  ...styles.message,
                  ...(isMobileLayout ? styles.messageMobile : null),
                  background:
                    msg.from === "user"
                      ? `linear-gradient(145deg, ${withAlpha(theme.userMessageColor, 0.96)} 0%, ${withAlpha(theme.buttonColor, 0.18)} 100%)`
                      : `linear-gradient(145deg, ${withAlpha(theme.botMessageColor, 0.97)} 0%, ${withAlpha(theme.backgroundColor, 0.9)} 100%)`,
                  color: theme.headerTextColor,
                  border: `1px solid ${msg.from === "user" ? withAlpha(theme.buttonColor, 0.24) : aura.softBorder}`,
                  boxShadow: `0 8px 20px ${withAlpha(theme.headerTextColor, 0.08)}`,
                  backdropFilter: "blur(8px)",
                }}
              >
                {msg.text}
              </div>
              {msg.timestamp ? (
                <span style={{ ...styles.timestamp, color: aura.mutedText }}>{msg.timestamp}</span>
              ) : null}
            </div>
          ))}
          {usageLimitReached && (
            <div style={{ ...styles.limitNotice, color: theme.buttonColor }}>
              ⚠️ {t("usage_limit_reached") || "Has alcanzado tu límite de mensajes."}
            </div>
          )}
          {activePanel === "chat" &&
            handoffFeatureEnabled &&
            renderedMessages.length > 0 &&
            !showHumanHandoffPrompt &&
            !humanHandoffSubmitted && (
            <div
              style={{
                marginTop: "0.5rem",
                border: `1px solid ${aura.softBorder}`,
                borderRadius: "12px",
                padding: "0.75rem",
                background: withAlpha(theme.backgroundColor, 0.82),
                boxShadow: `0 8px 18px ${withAlpha(theme.headerTextColor, 0.06)}`,
              }}
            >
              <div style={{ fontSize: "0.85rem", color: withAlpha(theme.headerTextColor, 0.82) }}>
                {wt(
                  "widget_handoff_cta_copy",
                  "Need a human agent? Share your contact details and we will follow up as soon as possible."
                )}
              </div>
              <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.6rem", flexWrap: "wrap" }}>
                <button
                  type="button"
                  onClick={() =>
                    openHumanHandoffPrompt({
                      trigger: "manual_request",
                      reason: "user_requested_human",
                    })
                  }
                  style={{
                    border: "none",
                    borderRadius: "10px",
                    padding: "0.55rem 0.85rem",
                    background: theme.buttonColor,
                    color: theme.buttonTextColor,
                    fontWeight: 600,
                    cursor: "pointer",
                  }}
                >
                  {wt("widget_handoff_cta_button", "Request human help")}
                </button>
              </div>
            </div>
          )}
          {handoffFeatureEnabled && (showHumanHandoffPrompt || humanHandoffSubmitted) && (
            <div
              style={{
                marginTop: "0.5rem",
                border: `1px solid ${withAlpha(theme.buttonColor, 0.28)}`,
                borderRadius: "12px",
                padding: "0.85rem",
                background: `linear-gradient(180deg, ${withAlpha(theme.backgroundColor, 0.94)} 0%, ${withAlpha(theme.buttonColor, 0.06)} 100%)`,
              }}
            >
              <div style={{ fontWeight: 700, fontSize: "0.88rem", color: theme.headerTextColor }}>
                {wt("widget_handoff_title", "Human intervention")}
              </div>
              <div
                style={{
                  marginTop: "0.35rem",
                  fontSize: "0.8rem",
                  lineHeight: 1.35,
                  color: withAlpha(theme.headerTextColor, 0.78),
                }}
              >
                {humanHandoffSubmitted
                  ? humanHandoffSuccess ||
                    wt(
                      "widget_handoff_success_default",
                      "We received your request and a human agent will review it as soon as possible."
                    )
                  : wt(
                      "widget_handoff_form_intro",
                      "Share your details so we can follow up outside this chat session if needed."
                    )}
              </div>

              {!humanHandoffSubmitted && (
                <>
                  {!humanHandoffFormOpen && (
                    <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.6rem", flexWrap: "wrap" }}>
                      <button
                        type="button"
                        onClick={() => setHumanHandoffFormOpen(true)}
                        style={{
                          border: "none",
                          borderRadius: "10px",
                          padding: "0.5rem 0.8rem",
                          background: theme.buttonColor,
                          color: theme.buttonTextColor,
                          fontWeight: 600,
                          cursor: "pointer",
                        }}
                      >
                        {wt("widget_handoff_open_form", "Open form")}
                      </button>
                      <button
                        type="button"
                        onClick={() => setShowHumanHandoffPrompt(false)}
                        style={{
                          borderRadius: "10px",
                          padding: "0.5rem 0.8rem",
                          border: `1px solid ${aura.softBorder}`,
                          background: withAlpha(theme.backgroundColor, 0.8),
                          color: withAlpha(theme.headerTextColor, 0.84),
                          cursor: "pointer",
                        }}
                      >
                        {wt("widget_handoff_keep_chatting", "Keep chatting")}
                      </button>
                    </div>
                  )}

                  {humanHandoffFormOpen && (
                    <div style={{ marginTop: "0.7rem", display: "grid", gap: "0.45rem" }}>
                      <input
                        type="text"
                        placeholder={wt("widget_handoff_name_placeholder", "Your name")}
                        value={humanHandoffName}
                        onChange={(e) => setHumanHandoffName(e.target.value)}
                        style={styles.formInput}
                      />
                      <input
                        type="email"
                        placeholder={wt("widget_handoff_email_placeholder", "Email (optional if phone)")}
                        value={humanHandoffEmail}
                        onChange={(e) => setHumanHandoffEmail(e.target.value)}
                        style={styles.formInput}
                      />
                      <input
                        type="tel"
                        placeholder={wt("widget_handoff_phone_placeholder", "Phone (optional if email)")}
                        value={humanHandoffPhone}
                        onChange={(e) => setHumanHandoffPhone(e.target.value)}
                        style={styles.formInput}
                      />

                      <label
                        style={{
                          display: "flex",
                          gap: "0.45rem",
                          alignItems: "flex-start",
                          fontSize: "0.76rem",
                          color: withAlpha(theme.headerTextColor, 0.82),
                        }}
                      >
                        <input
                          type="checkbox"
                          checked={humanHandoffAcceptedTerms}
                          onChange={(e) => setHumanHandoffAcceptedTerms(e.target.checked)}
                          style={{ marginTop: "0.15rem" }}
                        />
                        <span>
                          {wt("widget_handoff_terms_label", "I accept the Terms & Conditions for follow-up.")}
                          {termsUrl ? (
                            <>
                              {" "}
                              <a
                                href={termsUrl}
                                target="_blank"
                                rel="noopener noreferrer"
                                style={{ color: theme.buttonColor, textDecoration: "underline" }}
                              >
                                {wt("terms", "Terms & Conditions")}
                              </a>
                            </>
                          ) : null}
                        </span>
                      </label>

                      <label
                        style={{
                          display: "flex",
                          gap: "0.45rem",
                          alignItems: "flex-start",
                          fontSize: "0.76rem",
                          color: withAlpha(theme.headerTextColor, 0.82),
                        }}
                      >
                        <input
                          type="checkbox"
                          checked={humanHandoffAcceptedMarketing}
                          onChange={(e) => setHumanHandoffAcceptedMarketing(e.target.checked)}
                          style={{ marginTop: "0.15rem" }}
                        />
                        <span>
                          {wt(
                            "widget_handoff_marketing_label",
                            "I want to receive updates and marketing communications (optional)."
                          )}
                        </span>
                      </label>

                      {humanHandoffError ? (
                        <div style={{ ...styles.formError, marginTop: "0.2rem" }}>{humanHandoffError}</div>
                      ) : null}

                      <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", marginTop: "0.2rem" }}>
                        <button
                          type="button"
                          onClick={submitHumanHandoffRequest}
                          disabled={humanHandoffSubmitting}
                          style={{
                            border: "none",
                            borderRadius: "10px",
                            padding: "0.55rem 0.85rem",
                            background: humanHandoffSubmitting ? "#999" : theme.buttonColor,
                            color: theme.buttonTextColor,
                            fontWeight: 600,
                            cursor: humanHandoffSubmitting ? "not-allowed" : "pointer",
                          }}
                        >
                          {humanHandoffSubmitting
                            ? wt("widget_handoff_submitting", "Sending...")
                            : wt("widget_handoff_submit", "Request follow-up")}
                        </button>
                        <button
                          type="button"
                          onClick={() => setHumanHandoffFormOpen(false)}
                          disabled={humanHandoffSubmitting}
                          style={{
                            borderRadius: "10px",
                            padding: "0.55rem 0.85rem",
                            border: `1px solid ${aura.softBorder}`,
                            background: withAlpha(theme.backgroundColor, 0.8),
                            color: withAlpha(theme.headerTextColor, 0.84),
                            cursor: humanHandoffSubmitting ? "not-allowed" : "pointer",
                          }}
                        >
                          {wt("widget_handoff_cancel", "Cancel")}
                        </button>
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>
      ) : (
        <div style={{ ...styles.calendarPanel, ...(isMobileLayout ? styles.calendarPanelMobile : null) }}>
          <div style={{ ...styles.calendarModeBar, ...(isMobileLayout ? styles.calendarModeBarMobile : null) }}>
            <button
              style={styles.calendarModeBtn(calendarViewMode === "day")}
              onClick={() => setCalendarViewMode("day")}
            >
              {agendaText.dayView}
            </button>
            <button
              style={styles.calendarModeBtn(calendarViewMode === "week")}
              onClick={() => setCalendarViewMode("week")}
            >
              {agendaText.weekView}
            </button>
            <button
              style={styles.calendarModeBtn(calendarViewMode === "month")}
              onClick={() => setCalendarViewMode("month")}
            >
              {agendaText.monthView}
            </button>
          </div>

          <div style={{ ...styles.calendarNavBar, ...(isMobileLayout ? styles.calendarNavBarMobile : null) }}>
            <button style={styles.calendarNavBtn} onClick={goCalendarPrev}>←</button>
            <strong
              style={{
                fontSize: isMobileLayout ? "0.82rem" : "0.9rem",
                textTransform: "capitalize",
                textAlign: "center",
              }}
            >
              {calendarTitle}
            </strong>
            <button style={styles.calendarNavBtn} onClick={goCalendarNext}>→</button>
          </div>

          {calendarLoading ? (
            <div style={styles.calendarStatus}>{agendaText.loadingSlots}</div>
          ) : calendarError ? (
            <div style={styles.calendarStatusError}>{calendarError}</div>
          ) : (
            <CalendarVisualView
              mode={calendarViewMode}
              currentDate={calendarDate}
              minDate={todayStart}
              maxDate={maxForwardDate}
              slots={calendarSlots}
              countsByDay={calendarCountsByDay}
              onSelectDate={(date) => {
                setCalendarDate(date);
                setCalendarViewMode("day");
              }}
              selectedSlot={selectedCalendarSlot}
              onSelectSlot={(slot) => setSelectedCalendarSlot(slot)}
              isMobile={isMobileLayout}
              lang={effectiveLang}
              labels={agendaText}
            />
          )}
          {selectedCalendarSlot && (
            <div style={styles.selectedSlotBar}>
              <div style={styles.selectedSlotText}>
                {agendaText.selectedPrefix} {selectedCalendarSlot.date} {selectedCalendarSlot.time}
              </div>
              <div style={styles.formGrid}>
                <input
                  type="text"
                  placeholder={`${agendaText.labelName} *`}
                  value={bookingName}
                  onChange={(e) => setBookingName(e.target.value)}
                  style={styles.formInput}
                />
                <input
                  type="email"
                  placeholder={`${agendaText.labelEmail} (${isEnglish ? "optional" : "opcional"})`}
                  value={bookingEmail}
                  onChange={(e) => setBookingEmail(e.target.value)}
                  style={styles.formInput}
                />
                <input
                  type="text"
                  placeholder={`${agendaText.labelPhone} (${isEnglish ? "optional" : "opcional"})`}
                  value={bookingPhone}
                  onChange={(e) => setBookingPhone(e.target.value)}
                  style={styles.formInput}
                />
              </div>
              {bookingError ? <div style={styles.formError}>{bookingError}</div> : null}
              {bookingSuccess ? <div style={styles.formSuccess}>{bookingSuccess}</div> : null}
              <button
                type="button"
                style={styles.selectedSlotButton}
                disabled={bookingSubmitting}
                onClick={async () => {
                  if (!bookingName.trim()) {
                    setBookingError(agendaText.nameRequired);
                    return;
                  }
                  if (!bookingEmail.trim() && !bookingPhone.trim()) {
                    setBookingError(agendaText.addContactRequired);
                    return;
                  }

                  setBookingSubmitting(true);
                  setBookingError("");
                  setBookingSuccess("");
                  setDuplicateExistingAppt(null);

                  try {
                    const apiUrl = resolveApiBaseUrl();

                    const requestPayload = {
                      public_client_id: publicClientId,
                      session_id: sessionId,
                      scheduled_time: selectedCalendarSlot.start_iso,
                      user_name: bookingName.trim(),
                      user_email: bookingEmail.trim() || null,
                      user_phone: bookingPhone.trim() || null,
                      replace_existing: false,
                    };

                    let res = await fetch(`${apiUrl}/widget/calendar/book`, {
                      method: "POST",
                      headers: { "Content-Type": "application/json" },
                      body: JSON.stringify(requestPayload),
                    });

                    let data = await res.json();

                    if (res.status === 409 && data?.duplicate_active) {
                      setDuplicateExistingAppt(data?.existing_appointment || {});
                      return;
                    }

                    if (!res.ok) {
                      throw new Error(data?.detail || data?.message || agendaText.bookError);
                    }

                    setBookingSubmitting(false);

                    const successMsg = agendaText.bookSuccessMessage;
                    const now = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
                    setMessages((prev) => [...prev, { from: "bot", text: successMsg, timestamp: now }]);
                    setBookingSuccess(agendaText.bookSuccessStatus);
                    setSelectedCalendarSlot(null);
                    setBookingName("");
                    setBookingEmail("");
                    setBookingPhone("");
                    setCalendarRefreshTick((v) => v + 1);
                    setShowBookingSuccessModal(true);
                  } catch (err) {
                    setBookingError(err?.message || agendaText.bookError);
                  } finally {
                    setBookingSubmitting(false);
                  }
                }}
              >
                {bookingSubmitting ? agendaText.bookingInProgress : agendaText.confirmAppointment}
              </button>
              {duplicateExistingAppt && (
                <div style={styles.duplicateBox}>
                  <div style={styles.formError}>
                    {agendaText.duplicateActive} ({formatDuplicateSlot(duplicateExistingAppt)}).
                  </div>
                  <button
                    type="button"
                    style={styles.replaceButton}
                    disabled={bookingSubmitting}
                    onClick={async () => {
                      try {
                        setBookingSubmitting(true);
                        setBookingError("");
                        const apiUrl = resolveApiBaseUrl();
                        const res = await fetch(`${apiUrl}/widget/calendar/book`, {
                          method: "POST",
                          headers: { "Content-Type": "application/json" },
                          body: JSON.stringify({
                            public_client_id: publicClientId,
                            session_id: sessionId,
                            scheduled_time: selectedCalendarSlot.start_iso,
                            user_name: bookingName.trim(),
                            user_email: bookingEmail.trim() || null,
                            user_phone: bookingPhone.trim() || null,
                            replace_existing: true,
                          }),
                        });
                        const data = await res.json();
                        if (!res.ok) throw new Error(data?.detail || data?.message || agendaText.replaceError);

                        const successMsg = agendaText.rescheduleSuccessMessage;
                        const now = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
                        setMessages((prev) => [...prev, { from: "bot", text: successMsg, timestamp: now }]);
                        setBookingSuccess(agendaText.rescheduleSuccessStatus);
                        setDuplicateExistingAppt(null);
                        setSelectedCalendarSlot(null);
                        setBookingName("");
                        setBookingEmail("");
                        setBookingPhone("");
                        setCalendarRefreshTick((v) => v + 1);
                        setShowBookingSuccessModal(true);
                      } catch (err) {
                        setBookingError(err?.message || agendaText.replaceError);
                      } finally {
                        setBookingSubmitting(false);
                      }
                    }}
                  >
                    {agendaText.replaceCurrentWithNew}
                  </button>
                </div>
              )}
            </div>
          )}
          <div style={styles.cancelLookupToggleWrap}>
            <button
              type="button"
              style={styles.cancelLookupToggleBtn}
              onClick={() => {
                setShowCancelLookup((prev) => !prev);
                setCancelError("");
                setCancelSuccess("");
                setShowCancelConfirmModal(false);
              }}
            >
              {showCancelLookup ? agendaText.hideLookup : agendaText.findMyAppointment}
            </button>
          </div>
          {showCancelLookup && (
            <div style={styles.cancelLookupCard}>
              <div style={styles.cancelLookupTitle}>{agendaText.findAppointmentTitle}</div>
              <div style={styles.formGrid}>
                <input
                  type="email"
                  placeholder={`${agendaText.labelEmail} (${isEnglish ? "optional" : "opcional"})`}
                  value={cancelEmail}
                  onChange={(e) => setCancelEmail(e.target.value)}
                  style={styles.formInput}
                />
                <input
                  type="text"
                  placeholder={`${agendaText.labelPhone} (${isEnglish ? "optional" : "opcional"})`}
                  value={cancelPhone}
                  onChange={(e) => setCancelPhone(e.target.value)}
                  style={styles.formInput}
                />
              </div>
              {cancelError ? <div style={styles.formError}>{cancelError}</div> : null}
              {cancelSuccess ? <div style={styles.formSuccess}>{cancelSuccess}</div> : null}
              <button
                type="button"
                style={styles.cancelLookupSearchBtn}
                onClick={lookupAppointmentForCancellation}
                disabled={cancelLookupLoading || cancelSubmitting}
              >
                {cancelLookupLoading ? agendaText.searching : agendaText.findMyAppointment}
              </button>
            </div>
          )}
          <div style={styles.calendarHint}>
            {agendaText.dateRangeHint}
            {calendarTimezone ? ` ${agendaText.timezoneLabel}: ${calendarTimezone}.` : ""}
          </div>
        </div>
      )}

      {/* ============================= */}
      {/* 💬 INPUT + BOTÓN + FOOTER    */}
      {/* ============================= */}
      <div
        style={{
          ...styles.bottomContainer,
          ...(isMobileLayout ? styles.bottomContainerMobile : null),
          background: aura.inputBg,
          borderTop: `1px solid ${aura.softBorder}`,
          backdropFilter: "blur(10px)",
        }}
      >
        {activePanel === "chat" && (
          <div style={{ ...styles.inputContainer, ...(isMobileLayout ? styles.inputContainerMobile : null) }}>
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={wt("type_message", effectiveLang === "en" ? "Type your question..." : "Escribe tu consulta...")}
              style={{
                ...styles.textarea,
                ...(isMobileLayout ? styles.textareaMobile : null),
                background: withAlpha(theme.backgroundColor, 0.9),
                border: `1px solid ${aura.inputBorder}`,
                boxShadow: `inset 0 1px 0 ${withAlpha(theme.backgroundColor, 0.65)}`,
                color: theme.headerTextColor,
              }}
              rows={2}
              disabled={usageLimitReached}
            />

            <button
              onClick={handleSendButtonClick}
              onPointerUp={handleSendButtonPointerUp}
              onTouchEnd={handleSendButtonTouchEnd}
              style={{
                ...styles.button,
                ...(isMobileLayout ? styles.buttonMobile : null),
                background: usageLimitReached
                  ? "#ccc"
                  : `linear-gradient(135deg, ${withAlpha(theme.buttonColor, 0.9)} 0%, ${theme.buttonColor} 100%)`,
                color: theme.buttonTextColor,
                opacity: sending ? 0.7 : 1,
                boxShadow: usageLimitReached ? "none" : aura.buttonShadow,
                touchAction: "manipulation",
              }}
              disabled={sending || usageLimitReached}
            >
              {usageLimitReached
                ? wt("limit_button", effectiveLang === "en" ? "Limit reached" : "Límite alcanzado")
                : sending
                ? `${wt("thinking", effectiveLang === "en" ? "Thinking" : "Pensando")}${thinkingDots}`
                : wt("send", effectiveLang === "en" ? "Send" : "Enviar")}
            </button>
          </div>
        )}

        {showPoweredBy && (
          <div
            style={{
              ...styles.footer,
              color: theme.footerTextColor,
              borderTop: `1px solid ${aura.softBorder}`,
              background: withAlpha(theme.backgroundColor, 0.72),
            }}
          >
            {wt("widget_preview_powered_by", effectiveLang === "en" ? "Powered by" : "Impulsado por")} <strong>Evolvian</strong> — evolvianai.com
          </div>
        )}

        {showLegalLinks && (termsUrl || privacyUrl) && (
          <div style={{ ...styles.legalContainer, color: aura.mutedText }}>
            {termsUrl && (
              <a
                href={termsUrl}
                target="_blank"
                rel="noopener noreferrer"
                style={{ ...styles.legalLink, color: aura.mutedText }}
              >
                {wt("widget_preview_terms", effectiveLang === "en" ? "Terms" : "Términos")}
              </a>
            )}

            {privacyUrl && (
              <>
                <span style={{ margin: "0 4px", color: "#aaa" }}>|</span>
                <a
                  href={privacyUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{ ...styles.legalLink, color: aura.mutedText }}
                >
                  {wt("widget_preview_privacy", effectiveLang === "en" ? "Privacy" : "Privacidad")}
                </a>
              </>
            )}
          </div>
        )}
      </div>
      {showBookingSuccessModal && (
        <div style={styles.successOverlay}>
          <div style={styles.successModal}>
            <h4 style={styles.successTitle}>{agendaText.sessionBookedTitle}</h4>
            <p style={styles.successBody}>
              {agendaText.sessionBookedBodyLine1}
              <br />
              {agendaText.sessionBookedBodyLine2}
            </p>
            <button
              type="button"
              style={styles.successButton}
              onClick={() => {
                setShowBookingSuccessModal(false);
                setActivePanel("chat");
                setSelectedCalendarSlot(null);
                try {
                  window.parent?.postMessage({ type: "EVOLVIAN_WIDGET_CLOSE" }, "*");
                } catch {
                  // Fallback: keep widget open and return to chat.
                }
              }}
            >
              {agendaText.understood}
            </button>
          </div>
        </div>
      )}
      {showCancelConfirmModal && cancelPreviewAppt && (
        <div style={styles.cancelOverlay}>
          <div style={styles.cancelModal}>
            <h4 style={styles.cancelModalTitle}>{agendaText.confirmCancellation}</h4>
            <p style={styles.cancelModalBody}>{agendaText.foundAppointment}</p>
            <div style={styles.cancelDataGrid}>
              <div><strong>{agendaText.labelName}:</strong> {cancelPreviewAppt.user_name || "—"}</div>
              <div><strong>{agendaText.labelDate}:</strong> {cancelPreviewAppt.formatted_time || cancelPreviewAppt.scheduled_time || "—"}</div>
              <div><strong>{agendaText.labelType}:</strong> {cancelPreviewAppt.appointment_type || agendaText.appointmentTypeFallback}</div>
              <div><strong>{agendaText.labelEmail}:</strong> {cancelPreviewAppt.user_email || "—"}</div>
              <div><strong>{agendaText.labelPhone}:</strong> {cancelPreviewAppt.user_phone || "—"}</div>
            </div>
            <div style={styles.cancelActionsRow}>
              <button
                type="button"
                style={styles.cancelKeepBtn}
                onClick={() => {
                  setShowCancelConfirmModal(false);
                  setCancelPreviewAppt(null);
                }}
                disabled={cancelSubmitting}
              >
                {agendaText.keepAppointment}
              </button>
              <button
                type="button"
                style={styles.cancelConfirmBtn}
                onClick={confirmWidgetCancellation}
                disabled={cancelSubmitting}
              >
                {cancelSubmitting ? agendaText.cancelling : agendaText.cancelAppointment}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function CalendarVisualView({
  mode,
  currentDate,
  minDate,
  maxDate,
  slots,
  countsByDay,
  onSelectDate,
  selectedSlot,
  onSelectSlot,
  isMobile = false,
  lang = "es",
  labels = {},
}) {
  const isEnglish = lang === "en";
  const fallbackLabels = isEnglish
    ? {
        noSlotsThisDay: "No available time slots this day.",
        nextAvailablePrefix: "Next available:",
        noNextSlots: "No upcoming time slots in the loaded range.",
        available: "Available",
        availableShort: "avail.",
      }
    : {
        noSlotsThisDay: "No hay horarios disponibles este día.",
        nextAvailablePrefix: "Próximo disponible:",
        noNextSlots: "No hay próximos horarios en el rango cargado.",
        available: "Disponible",
        availableShort: "disp.",
      };
  const text = { ...fallbackLabels, ...labels };
  const locale = isEnglish ? "en-US" : "es-ES";
  const monthHeaders = isEnglish ? ["S", "M", "T", "W", "T", "F", "S"] : ["D", "L", "M", "M", "J", "V", "S"];

  const slotsForDay = (dateObj) => {
    const key = `${dateObj.getFullYear()}-${String(dateObj.getMonth() + 1).padStart(2, "0")}-${String(dateObj.getDate()).padStart(2, "0")}`;
    return (slots || []).filter((slot) => slot.date === key);
  };

  if (mode === "day") {
    const day = new Date(currentDate);
    const daySlots = slotsForDay(day);
    const dayKey = `${day.getFullYear()}-${String(day.getMonth() + 1).padStart(2, "0")}-${String(day.getDate()).padStart(2, "0")}`;
    const nextAvailable = (slots || [])
      .filter((slot) => slot.date > dayKey)
      .sort((a, b) => a.start_iso.localeCompare(b.start_iso))[0];
    return (
      <div style={styles.calendarScrollArea}>
        {daySlots.length === 0 ? (
          <div style={styles.calendarEmptyState}>
            <div>{text.noSlotsThisDay}</div>
            {nextAvailable ? (
              <button
                type="button"
                style={styles.nextAvailableBtn}
                onClick={() => {
                  const dt = new Date(nextAvailable.start_iso);
                  if (!Number.isNaN(dt.getTime())) onSelectDate?.(dt);
                }}
              >
                {text.nextAvailablePrefix} {nextAvailable.date} {nextAvailable.time}
              </button>
            ) : (
              <div style={styles.nextAvailableText}>{text.noNextSlots}</div>
            )}
          </div>
        ) : (
          daySlots
            .slice()
            .sort((a, b) => a.start_iso.localeCompare(b.start_iso))
            .map((slot) => (
              <button
                key={slot.start_iso}
                type="button"
                style={{
                  ...styles.slotRow,
                  ...(selectedSlot?.start_iso === slot.start_iso ? styles.slotRowSelected : null),
                }}
                onClick={() => onSelectSlot?.(slot)}
              >
                <span>{slot.time}</span>
                <span>{text.available}</span>
              </button>
            ))
        )}
      </div>
    );
  }

  if (mode === "week") {
    const weekStart = new Date(currentDate);
    weekStart.setDate(weekStart.getDate() - weekStart.getDay());
    const days = Array.from({ length: 7 }, (_, idx) => {
      const d = new Date(weekStart);
      d.setDate(weekStart.getDate() + idx);
      return d;
    });

    const weekGrid = (
      <div style={{ ...styles.weekGrid, ...(isMobile ? styles.weekGridMobile : null) }}>
        {days.map((day) => {
          const disabled = day < minDate || day > maxDate;
          const key = `${day.getFullYear()}-${String(day.getMonth() + 1).padStart(2, "0")}-${String(day.getDate()).padStart(2, "0")}`;
          const count = countsByDay?.[key] || 0;
          return (
            <button
              key={day.toISOString()}
              type="button"
              style={{
                ...styles.weekCell,
                ...(isMobile ? styles.weekCellMobile : null),
                opacity: disabled ? 0.35 : 1,
                cursor: disabled ? "default" : "pointer",
              }}
              onClick={() => {
                if (!disabled) onSelectDate?.(day);
              }}
            >
              <div style={styles.weekDay}>{day.toLocaleDateString(locale, { weekday: "short" })}</div>
              <div style={styles.weekDate}>{day.getDate()}</div>
              <div style={styles.weekCount}>
                {count} {text.availableShort}
              </div>
            </button>
          );
        })}
      </div>
    );

    if (isMobile) {
      return <div style={styles.weekGridScroll}>{weekGrid}</div>;
    }

    return weekGrid;
  }

  const year = currentDate.getFullYear();
  const month = currentDate.getMonth();
  const firstDay = new Date(year, month, 1);
  const startDay = firstDay.getDay();
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const cells = [];

  for (let i = 0; i < startDay; i += 1) cells.push(null);
  for (let d = 1; d <= daysInMonth; d += 1) cells.push(new Date(year, month, d));

  return (
    <div style={{ ...styles.monthGrid, ...(isMobile ? styles.monthGridMobile : null) }}>
      {monthHeaders.map((label, idx) => (
        <div key={`${label}-${idx}`} style={styles.monthHeaderCell}>{label}</div>
      ))}
      {cells.map((day, idx) => {
        if (!day) return <div key={`empty-${idx}`} style={styles.monthEmptyCell} />;
        const disabled = day < minDate || day > maxDate;
        const key = `${day.getFullYear()}-${String(day.getMonth() + 1).padStart(2, "0")}-${String(day.getDate()).padStart(2, "0")}`;
        const count = countsByDay?.[key] || 0;
        return (
          <button
            key={day.toISOString()}
            type="button"
            style={{
              ...styles.monthCell,
              ...(isMobile ? styles.monthCellMobile : null),
              opacity: disabled ? 0.35 : 1,
              cursor: disabled ? "default" : "pointer",
            }}
            onClick={() => {
              if (!disabled) onSelectDate?.(day);
            }}
          >
            <span>{day.getDate()}</span>
            <span style={styles.monthCount}>{count}</span>
          </button>
        );
      })}
    </div>
  );
}

// 🎨 Estilos base
const styles = {
  wrapper: {
    width: "100%",
    height: "100%",
    display: "flex",
    flexDirection: "column",
    overflow: "hidden",
    border: "1px solid #f0f0f0",
  },
  header: {
    flexShrink: 0,
    height: "56px",
    borderBottom: "1px solid #f0f0f0",
    display: "flex",
    alignItems: "center",
    padding: "0 1rem",
    gap: "0.6rem",
  },
  headerMobile: {
    minHeight: "56px",
    height: "auto",
    padding: "0.45rem 0.65rem",
    gap: "0.35rem",
    flexWrap: "nowrap",
  },
  headerLeft: {
    display: "flex",
    alignItems: "center",
    gap: "0.4rem",
  },
  headerLeftMobile: {
    minWidth: 0,
    flex: 1,
  },
  headerActions: {
    marginLeft: "auto",
    display: "flex",
    gap: "0.35rem",
  },
  headerActionsMobile: {
    marginLeft: "auto",
    width: "auto",
    flexShrink: 0,
    alignSelf: "flex-start",
    gap: "0.28rem",
  },
  headerActionBtn: {
    border: "1px solid #d8e7f8",
    borderRadius: "999px",
    padding: "0.2rem 0.55rem",
    fontSize: "0.75rem",
    fontWeight: "600",
    cursor: "pointer",
  },
  headerActionBtnMobile: {
    flex: "none",
    textAlign: "center",
    padding: "0.12rem 0.48rem",
    fontSize: "0.66rem",
    minHeight: "24px",
    lineHeight: 1.05,
  },
  messages: {
    flex: 1,
    overflowY: "auto",
    padding: "1rem",
    display: "flex",
    flexDirection: "column",
    gap: "0.75rem",
  },
  messagesMobile: {
    padding: "0.75rem",
    gap: "0.65rem",
  },
  calendarPanel: {
    flex: 1,
    minHeight: 0,
    display: "flex",
    flexDirection: "column",
    padding: "0.8rem 0.8rem 1rem",
    gap: "0.6rem",
    overflowY: "auto",
    overflowX: "hidden",
    scrollbarGutter: "stable",
  },
  calendarPanelMobile: {
    padding: "0.65rem 0.65rem 0.9rem",
  },
  calendarModeBar: {
    display: "flex",
    gap: "0.5rem",
  },
  calendarModeBarMobile: {
    flexWrap: "wrap",
  },
  calendarModeBtn: (active) => ({
    border: "1px solid #dce5ef",
    borderRadius: 8,
    fontSize: "0.78rem",
    padding: "0.25rem 0.55rem",
    backgroundColor: active ? "#4a90e2" : "#ffffff",
    color: active ? "#ffffff" : "#274472",
    fontWeight: "600",
    cursor: "pointer",
  }),
  calendarNavBar: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    gap: "0.8rem",
  },
  calendarNavBarMobile: {
    gap: "0.45rem",
  },
  calendarNavBtn: {
    border: "1px solid #dce5ef",
    borderRadius: 8,
    background: "#ffffff",
    cursor: "pointer",
    padding: "0.2rem 0.5rem",
    color: "#274472",
  },
  calendarScrollArea: {
    flex: 1,
    overflowY: "auto",
    border: "1px solid #edf1f7",
    borderRadius: 10,
    padding: "0.5rem",
  },
  calendarStatus: {
    flex: 1,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    border: "1px solid #edf1f7",
    borderRadius: 10,
    color: "#607d9d",
    fontSize: "0.85rem",
  },
  calendarStatusError: {
    flex: 1,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    border: "1px solid #f6d6d6",
    borderRadius: 10,
    color: "#b04545",
    fontSize: "0.85rem",
    padding: "0.5rem",
    textAlign: "center",
  },
  calendarEmptyState: {
    color: "#607d9d",
    textAlign: "center",
    fontSize: "0.82rem",
    padding: "0.8rem 0.4rem",
    display: "flex",
    flexDirection: "column",
    gap: "0.5rem",
    alignItems: "center",
  },
  nextAvailableBtn: {
    border: "1px solid #cfe0f6",
    borderRadius: 8,
    background: "#f4f8ff",
    color: "#274472",
    fontSize: "0.75rem",
    padding: "0.35rem 0.6rem",
    cursor: "pointer",
  },
  nextAvailableText: {
    fontSize: "0.74rem",
    color: "#7a8ea8",
  },
  slotRow: {
    display: "flex",
    justifyContent: "space-between",
    borderBottom: "1px solid #f2f4f8",
    padding: "0.45rem 0.2rem",
    fontSize: "0.82rem",
    color: "#274472",
    width: "100%",
    textAlign: "left",
    borderLeft: "none",
    borderRight: "none",
    borderTop: "none",
    background: "#ffffff",
    cursor: "pointer",
  },
  slotRowSelected: {
    background: "#eaf3ff",
    borderBottom: "1px solid #bcd5f4",
    fontWeight: "700",
  },
  weekGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(7, 1fr)",
    gap: "0.4rem",
  },
  weekGridScroll: {
    overflowX: "auto",
    paddingBottom: "0.2rem",
  },
  weekGridMobile: {
    gridTemplateColumns: "repeat(7, minmax(62px, 1fr))",
  },
  weekCell: {
    border: "1px solid #edf1f7",
    borderRadius: 10,
    minHeight: 70,
    textAlign: "center",
    display: "flex",
    flexDirection: "column",
    justifyContent: "center",
    color: "#274472",
    backgroundColor: "#ffffff",
  },
  weekCellMobile: {
    minHeight: 56,
  },
  weekDay: {
    fontSize: "0.7rem",
    textTransform: "capitalize",
  },
  weekDate: {
    fontSize: "1rem",
    fontWeight: "700",
  },
  weekCount: {
    fontSize: "0.7rem",
    color: "#607d9d",
  },
  monthGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(7, 1fr)",
    gap: "0.25rem",
    border: "1px solid #edf1f7",
    borderRadius: 10,
    padding: "0.35rem",
  },
  monthGridMobile: {
    gap: "0.2rem",
    padding: "0.25rem",
  },
  monthHeaderCell: {
    textAlign: "center",
    fontSize: "0.72rem",
    fontWeight: "700",
    color: "#6982a6",
    paddingBottom: "0.2rem",
  },
  monthEmptyCell: {
    minHeight: 28,
  },
  monthCell: {
    minHeight: 34,
    border: "1px solid #f1f4f8",
    borderRadius: 6,
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    fontSize: "0.78rem",
    color: "#274472",
    background: "#ffffff",
    padding: "0 0.25rem",
  },
  monthCellMobile: {
    minHeight: 30,
    fontSize: "0.72rem",
    padding: "0 0.2rem",
  },
  monthCount: {
    fontSize: "0.65rem",
    color: "#607d9d",
  },
  selectedSlotBar: {
    border: "1px solid #d9e8fb",
    borderRadius: 10,
    background: "#f7fbff",
    padding: "0.55rem",
    display: "flex",
    flexDirection: "column",
    gap: "0.45rem",
  },
  formGrid: {
    display: "grid",
    gridTemplateColumns: "1fr",
    gap: "0.4rem",
  },
  formInput: {
    border: "1px solid #cfe0f6",
    borderRadius: 8,
    padding: "0.45rem 0.55rem",
    fontSize: "0.8rem",
    outline: "none",
  },
  formError: {
    color: "#b04545",
    fontSize: "0.75rem",
  },
  formSuccess: {
    color: "#2f7d4a",
    fontSize: "0.75rem",
  },
  selectedSlotText: {
    fontSize: "0.78rem",
    color: "#274472",
    fontWeight: "600",
  },
  selectedSlotButton: {
    border: "none",
    borderRadius: 8,
    background: "#4a90e2",
    color: "#ffffff",
    fontSize: "0.78rem",
    fontWeight: "700",
    padding: "0.45rem 0.55rem",
    cursor: "pointer",
  },
  duplicateBox: {
    border: "1px solid #f2c2c2",
    background: "#fff7f7",
    borderRadius: 8,
    padding: "0.5rem",
    display: "flex",
    flexDirection: "column",
    gap: "0.4rem",
  },
  replaceButton: {
    border: "none",
    borderRadius: 8,
    background: "#d9534f",
    color: "#ffffff",
    fontSize: "0.75rem",
    fontWeight: "700",
    padding: "0.4rem 0.55rem",
    cursor: "pointer",
  },
  cancelLookupToggleWrap: {
    display: "flex",
    justifyContent: "center",
  },
  cancelLookupToggleBtn: {
    border: "1px solid #d4dde8",
    borderRadius: 8,
    background: "#ffffff",
    color: "#334155",
    fontSize: "0.76rem",
    fontWeight: "700",
    padding: "0.4rem 0.75rem",
    cursor: "pointer",
  },
  cancelLookupCard: {
    border: "1px solid #e2e8f0",
    borderRadius: 10,
    background: "#f8fafc",
    padding: "0.6rem",
    display: "flex",
    flexDirection: "column",
    gap: "0.45rem",
  },
  cancelLookupTitle: {
    fontSize: "0.78rem",
    fontWeight: "700",
    color: "#334155",
  },
  cancelLookupSearchBtn: {
    border: "1px solid #cbd5e1",
    borderRadius: 8,
    background: "#ffffff",
    color: "#334155",
    fontSize: "0.77rem",
    fontWeight: "700",
    padding: "0.42rem 0.6rem",
    cursor: "pointer",
  },
  cancelOverlay: {
    position: "absolute",
    inset: 0,
    backdropFilter: "blur(5px)",
    background: "rgba(14, 27, 44, 0.32)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    zIndex: 35,
    padding: "1rem",
  },
  cancelModal: {
    width: "100%",
    maxWidth: 340,
    background: "#ffffff",
    borderRadius: 14,
    border: "1px solid #d8e7f8",
    padding: "1rem",
    boxShadow: "0 12px 30px rgba(0,0,0,0.16)",
  },
  cancelModalTitle: {
    margin: 0,
    color: "#1b2a41",
    fontSize: "0.98rem",
  },
  cancelModalBody: {
    margin: "0.5rem 0 0.65rem 0",
    color: "#475569",
    fontSize: "0.82rem",
  },
  cancelDataGrid: {
    display: "grid",
    gap: "0.34rem",
    fontSize: "0.78rem",
    color: "#1e293b",
    background: "#f8fafc",
    border: "1px solid #e2e8f0",
    borderRadius: 10,
    padding: "0.55rem",
  },
  cancelActionsRow: {
    display: "flex",
    gap: "0.45rem",
    marginTop: "0.7rem",
  },
  cancelKeepBtn: {
    flex: 1,
    border: "1px solid #cbd5e1",
    borderRadius: 8,
    background: "#ffffff",
    color: "#334155",
    padding: "0.44rem 0.6rem",
    cursor: "pointer",
    fontWeight: "700",
    fontSize: "0.78rem",
  },
  cancelConfirmBtn: {
    flex: 1,
    border: "1px solid #cbd5e1",
    borderRadius: 8,
    background: "#f8fafc",
    color: "#334155",
    padding: "0.44rem 0.6rem",
    cursor: "pointer",
    fontWeight: "700",
    fontSize: "0.78rem",
  },
  successOverlay: {
    position: "absolute",
    inset: 0,
    backdropFilter: "blur(4px)",
    background: "rgba(14, 27, 44, 0.32)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    zIndex: 30,
    padding: "1rem",
  },
  successModal: {
    width: "100%",
    maxWidth: 290,
    background: "#ffffff",
    borderRadius: 14,
    border: "1px solid #d8e7f8",
    padding: "1rem",
    textAlign: "center",
    boxShadow: "0 12px 30px rgba(0,0,0,0.16)",
  },
  successTitle: {
    margin: 0,
    color: "#1b2a41",
    fontSize: "1rem",
  },
  successBody: {
    margin: "0.55rem 0 0.8rem 0",
    color: "#3f5c7e",
    fontSize: "0.86rem",
    lineHeight: 1.35,
  },
  successButton: {
    border: "none",
    borderRadius: 8,
    background: "#4a90e2",
    color: "#ffffff",
    padding: "0.42rem 0.8rem",
    cursor: "pointer",
    fontWeight: "700",
    fontSize: "0.82rem",
  },
  calendarHint: {
    fontSize: "0.74rem",
    color: "#607d9d",
    textAlign: "center",
  },
  bottomContainer: {
    flexShrink: 0,
    borderTop: "1px solid #f0f0f0",
  },
  bottomContainerMobile: {
    paddingBottom: "env(safe-area-inset-bottom, 0px)",
  },
  inputContainer: {
    display: "flex",
    gap: "0.5rem",
    padding: "0.8rem",
  },
  inputContainerMobile: {
    flexDirection: "column",
    gap: "0.45rem",
    padding: "0.7rem",
  },
  textarea: {
    flex: 1,
    resize: "none",
    borderRadius: "10px",
    padding: "0.6rem 0.75rem",
    border: "1px solid #ddd",
    fontSize: "0.95rem",
    outline: "none",
    color: "#1b2a41",
    backgroundColor: "#fff",
    fontFamily: "'Inter', sans-serif",
  },
  textareaMobile: {
    minHeight: "72px",
    fontSize: "0.9rem",
  },
  button: {
    border: "none",
    padding: "0.6rem 1rem",
    borderRadius: "10px",
    fontWeight: "600",
    fontSize: "0.95rem",
    cursor: "pointer",
    transition: "background 0.2s",
  },
  buttonMobile: {
    width: "100%",
  },
  message: {
    padding: "0.75rem 1rem",
    borderRadius: "18px",
    maxWidth: "75%",
    wordBreak: "break-word",
    whiteSpace: "pre-line",
    fontSize: "0.95rem",
    boxShadow: "0 1px 3px rgba(0,0,0,0.05)",
  },
  messageMobile: {
    maxWidth: "88%",
    fontSize: "0.9rem",
  },
  timestamp: {
    fontSize: "0.7rem",
    color: "#bbb",
    marginTop: "0.25rem",
  },
  footer: {
    textAlign: "center",
    fontSize: "0.75rem",
    padding: "0.6rem",
    borderTop: "1px solid #f0f0f0",
  },
  legalContainer: {
    textAlign: "center",
    fontSize: "0.75rem",
    paddingBottom: "0.5rem",
  },
  legalLink: {
    color: "#888",
    textDecoration: "none",
  },
  limitNotice: {
    textAlign: "center",
    fontSize: "0.85rem",
    marginTop: "1rem",
  },
};
