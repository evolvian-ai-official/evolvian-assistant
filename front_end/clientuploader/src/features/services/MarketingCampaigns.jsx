import { useEffect, useMemo, useState } from "react";
import { useClientId } from "../../hooks/useClientId";
import { useLanguage } from "../../contexts/LanguageContext";
import { authFetch } from "../../lib/authFetch";
import "../../components/ui/internal-admin-responsive.css";

export default function MarketingCampaigns() {
  const clientId = useClientId();
  const { lang } = useLanguage();
  const isEs = lang === "es";
  const API = import.meta.env.VITE_API_URL;

  const text = {
    title: isEs ? "Marketing Campaigns" : "Marketing Campaigns",
    subtitle: isEs
      ? "Crea campañas de Email y WhatsApp, segmenta audiencia y consulta historial de envíos."
      : "Create Email and WhatsApp campaigns, segment audience, and review send history.",
    create: isEs ? "Crear campaña" : "Create campaign",
    createNewCampaign: isEs ? "Crear Campaña" : "Create Campaign",
    campaigns: isEs ? "Campañas" : "Campaigns",
    campaignHistoryTitle: isEs ? "Histórico de campañas" : "Campaign history",
    campaignHistorySubtitle: isEs
      ? "Consulta campañas enviadas, su rendimiento y retoma seguimiento sin perder contexto."
      : "Review sent campaigns, performance, and follow-ups without losing context.",
    selectedCampaignTitle: isEs ? "Campaña seleccionada" : "Selected campaign",
    campaignMetricsSent: isEs ? "Enviados" : "Sent",
    campaignMetricsResponses: isEs ? "Respuestas" : "Responses",
    campaignMetricsOptOut: isEs ? "Opt-out" : "Opt-out",
    campaignMetricsFailed: isEs ? "Fallidos" : "Failed",
    campaignMetricsBlocked: isEs ? "Bloqueados" : "Blocked",
    campaignMetricsSkipped: isEs ? "Omitidos" : "Skipped",
    noCampaignMetrics: isEs ? "Sin actividad todavía." : "No activity yet.",
    audience: isEs ? "Audiencia" : "Audience",
    audienceTitle: isEs ? "Destinatarios para envío" : "Recipients for send",
    audienceSubtitle: isEs
      ? "Filtra por interés, revisa cadencia y arma la siguiente oleada."
      : "Filter by interest, review cadence, and prepare the next wave.",
    filters: isEs ? "Filtros" : "Filters",
    all: isEs ? "Todos" : "All",
    interestFilter: isEs ? "Interés" : "Interest",
    allInterest: isEs ? "Todos los intereses" : "All interests",
    interested: isEs ? "Interesado" : "Interested",
    notInterested: isEs ? "No interesado" : "Not interested",
    noResponse: isEs ? "Sin respuesta" : "No response",
    optOutStatus: isEs ? "Opt-out" : "Opt-out",
    commercialStatus: isEs ? "Status comercial" : "Commercial status",
    campaignsSentCount: isEs ? "Campañas enviadas" : "Campaigns sent",
    emailCampaignsSentCount: isEs ? "Email" : "Email",
    whatsappCampaignsSentCount: isEs ? "WhatsApp" : "WhatsApp",
    emailCampaignsFilter: isEs ? "Número de envíos por Email" : "Number of sends by Email",
    whatsappCampaignsFilter: isEs ? "Número de envíos por WhatsApp" : "Number of sends by WhatsApp",
    campaignCountFiltersTitle: isEs ? "Filtrar por campañas enviadas" : "Filter by campaigns sent",
    campaignCountFiltersHelp: isEs
      ? "Selecciona un total exacto por canal para ver solo esos contactos."
      : "Select an exact total by channel to see only those contacts.",
    countFilterPlaceholder: isEs ? "Cualquiera" : "Any",
    clearCountFilters: isEs ? "Limpiar filtros de envíos" : "Clear send filters",
    lastCampaignSentAt: isEs ? "Último envío" : "Last campaign sent",
    searchAudience: isEs ? "Buscar audiencia" : "Search audience",
    searchCampaigns: isEs ? "Buscar campañas" : "Search campaigns",
    noAudience: isEs ? "Sin audiencia para mostrar." : "No audience to display.",
    noCampaigns: isEs ? "No hay campañas todavía." : "No campaigns yet.",
    history: isEs ? "Historial" : "History",
    recipients: isEs ? "Destinatarios" : "Recipients",
    runCampaign: isEs ? "Iniciar Campaña" : "Start Campaign",
    runCampaignTitle: isEs ? "Iniciar Campaña" : "Start Campaign",
    runCampaignSubtitle: isEs
      ? "Haz el envío en pasos: campaña, destinatarios, preview y resultado."
      : "Run the send in steps: campaign, recipients, preview, and result.",
    runCampaignStepCampaign: isEs ? "1. Campaña" : "1. Campaign",
    runCampaignStepRecipients: isEs ? "2. Destinatarios" : "2. Recipients",
    runCampaignStepPreview: isEs ? "3. Preview" : "3. Preview",
    runCampaignStepResult: isEs ? "4. Resultado" : "4. Result",
    runCampaignSelectCampaign: isEs ? "Selecciona una campaña para continuar." : "Select a campaign to continue.",
    runCampaignSelectRecipients: isEs ? "Selecciona destinatarios antes de continuar." : "Select recipients before continuing.",
    runCampaignStepResultSubtitle: isEs
      ? "Resumen final del envío ejecutado."
      : "Final summary for the executed send.",
    next: isEs ? "Continuar" : "Continue",
    back: isEs ? "Atrás" : "Back",
    finish: isEs ? "Cerrar" : "Close",
    confirmRunCampaign: isEs ? "Confirmar e iniciar campaña" : "Confirm and start campaign",
    sending: isEs ? "Enviando..." : "Sending...",
    refresh: isEs ? "Actualizar" : "Refresh",
    loading: isEs ? "Cargando..." : "Loading...",
    draft: isEs ? "Borrador" : "Draft",
    selected: isEs ? "Seleccionados" : "Selected",
    selectedNone: isEs ? "No hay destinatarios seleccionados." : "No recipients selected.",
    selectedCount: isEs ? "Seleccionados" : "Selected",
    selectVisible: isEs ? "Seleccionar visibles" : "Select visible",
    selectAllClients: isEs ? "Todos clientes" : "All clients",
    selectAllLeads: isEs ? "Todos leads" : "All leads",
    selectAllAudience: isEs ? "Toda audiencia" : "All audience",
    clearSelection: isEs ? "Limpiar selección" : "Clear selection",
    remove: isEs ? "Quitar" : "Remove",
    requiredRecipientSelection: isEs
      ? "Debes seleccionar al menos un destinatario antes de enviar."
      : "Select at least one recipient before sending.",
    noSendableRecipients: isEs
      ? "Los destinatarios seleccionados no tienen canal válido para esta campaña."
      : "Selected recipients do not have a valid channel for this campaign.",
    previewTitle: isEs ? "Confirmar envío de campaña" : "Confirm campaign send",
    previewSubtitle: isEs
      ? "Revisa contenido y destinatarios antes de enviar."
      : "Review content and recipients before sending.",
    previewContent: isEs ? "Preview de contenido" : "Content preview",
    previewAudience: isEs ? "Destinatarios a enviar" : "Recipients to send",
    cancel: isEs ? "Cancelar" : "Cancel",
    confirmSend: isEs ? "Confirmar envío" : "Confirm send",
    selectCampaignFirst: isEs ? "Selecciona una campaña para enviar." : "Select a campaign to send.",
    channelRuleEmail: isEs ? "Campaña Email: solo contactos con email." : "Email campaign: only contacts with email.",
    channelRuleWhatsapp: isEs ? "Campaña WhatsApp: solo contactos con teléfono." : "WhatsApp campaign: only contacts with phone.",
    incompatibleNoEmail: isEs ? "Sin email" : "No email",
    incompatibleNoPhone: isEs ? "Sin teléfono" : "No phone",
    optedOut: isEs ? "Desvinculado" : "Opt-out",
    optedOutCannotSelect: isEs
      ? "Este cliente hizo opt-out y no se puede seleccionar."
      : "This client opted out and cannot be selected.",
    selectedForSend: isEs ? "Listos para envío" : "Ready to send",
    excludedByChannel: isEs ? "Excluidos por canal" : "Excluded by channel",
    uploadImage: isEs ? "Subir imagen" : "Upload image",
    uploadingImage: isEs ? "Subiendo imagen..." : "Uploading image...",
    imageReady: isEs ? "Imagen lista" : "Image ready",
    removeImage: isEs ? "Quitar imagen" : "Remove image",
    imageRequiredType: isEs ? "Selecciona un archivo de imagen válido." : "Select a valid image file.",
    imageTooLarge: isEs ? "Imagen demasiado grande (máximo 2MB)." : "Image too large (max 2MB).",
    invalidCtaUrl: isEs ? "URL inválida. Usa un enlace absoluto con http(s)." : "Invalid URL. Use an absolute http(s) link.",
    aiRestructure: isEs ? "Sugerencia AI" : "AI suggestion",
    aiRestructuring: isEs ? "Reestructurando..." : "Restructuring...",
    aiApplied: isEs ? "Texto reestructurado con AI." : "Text restructured with AI.",
    aiNeedsContent: isEs ? "Escribe contenido antes de usar Sugerencia AI." : "Write content before using AI suggestion.",
    changeCampaign: isEs ? "Cambiar campaña" : "Change campaign",
    noCampaignSelected: isEs ? "No hay campaña seleccionada." : "No campaign selected.",
    campaignPickerTitle: isEs ? "Seleccionar campaña" : "Select campaign",
    campaignPickerSubtitle: isEs ? "Elige una campaña para envío y seguimiento." : "Choose a campaign for send and tracking.",
    campaignPickerHint: isEs
      ? "Paso 1: elige la campaña que quieres mandar o retomar."
      : "Step 1: choose the campaign you want to send or resume.",
    campaignFormCreateTitle: isEs ? "Crear campaña" : "Create campaign",
    campaignFormEditTitle: isEs ? "Editar campaña" : "Edit campaign",
    campaignFormSubtitle: isEs ? "Completa el formulario y guarda tu campaña." : "Complete the form and save your campaign.",
    close: isEs ? "Cerrar" : "Close",
    whatsappNotConnected: isEs
      ? "WhatsApp no está conectado. Conéctalo antes de enviar campañas por WhatsApp."
      : "WhatsApp is not connected. Connect it before sending WhatsApp campaigns.",
    whatsappSyncSuccess: isEs
      ? "Template de WhatsApp sincronizado con Meta automáticamente."
      : "WhatsApp template synced with Meta automatically.",
    whatsappSyncWarning: isEs
      ? "La campaña se guardó, pero el sync con Meta requiere revisión."
      : "Campaign saved, but Meta sync needs review.",
    sendSummarySuccess: isEs ? "Campaña enviada correctamente." : "Campaign sent successfully.",
    sendSummaryPartial: isEs ? "Campaña enviada parcialmente." : "Campaign sent partially.",
    sendSummaryFailed: isEs ? "No se pudo enviar la campaña." : "Campaign could not be sent.",
    sendSummaryImageFallback: isEs
      ? "Algunos mensajes se enviaron sin imagen porque Meta rechazó el header en esa plantilla."
      : "Some messages were sent without image because Meta rejected the template header.",
    sendSummaryImageNoHeader: isEs
      ? "Esta plantilla no tiene header de imagen en Meta; los envíos salen solo con texto/botones."
      : "This template has no image header in Meta; sends go out as text/buttons only.",
    sent: isEs ? "Enviados" : "Sent",
    failed: isEs ? "Fallidos" : "Failed",
    blocked: isEs ? "Bloqueados política" : "Policy blocked",
    skipped: isEs ? "Omitidos" : "Skipped",
    updateCampaign: isEs ? "Actualizar campaña" : "Update campaign",
    editCampaign: isEs ? "Editar" : "Edit",
    cancelEdit: isEs ? "Cancelar edición" : "Cancel edit",
    archiveCampaign: isEs ? "Eliminar (lógico)" : "Archive (logical)",
    archiveConfirm: isEs ? "¿Eliminar esta campaña de forma lógica?" : "Archive this campaign logically?",
    archiveSuccess: isEs ? "Campaña archivada." : "Campaign archived.",
    campaignPreview: isEs ? "Ver preview" : "View preview",
    whatsappEditVersions: isEs
      ? "Campaña WhatsApp actualizada. Se creó una nueva plantilla para Meta."
      : "WhatsApp campaign updated. A new Meta template version was created.",
    whatsappFormatTitle: isEs ? "Formato WhatsApp aceptado" : "Accepted WhatsApp format",
    whatsappFormatLine1: isEs
      ? "Texto de plantilla con variable {{1}} (contenido completo de la campaña)."
      : "Template body text with {{1}} variable (full campaign content).",
    whatsappFormatLine2: isEs
      ? "Botón de interés configurable (quick reply) para abrir seguimiento humano."
      : "Configurable interest button (quick reply) to open human follow-up.",
    whatsappFormatLine3: isEs
      ? "Imagen opcional como header (solo URL pública https://...)."
      : "Optional image header (public https://... URL only).",
    whatsappFormatLine4: isEs
      ? "No uses {1} ni {{1}} en tu texto: el sistema lo agrega automáticamente."
      : "Do not use {1} or {{1}} in your text: the system injects it automatically.",
    whatsappFormatLine5: isEs
      ? "Plantilla final enviada a Meta: Hola, {{1}}, Gracias."
      : "Final template sent to Meta: Hello, {{1}}, Thank you.",
    whatsappOptOutToggle: isEs ? "Agregar botón de baja (opt-out)" : "Add opt-out button",
    whatsappOptOutLabel: isEs ? "Texto botón de baja" : "Opt-out button text",
    whatsappOptOutHelp: isEs
      ? "Si el contacto hace click, se registra opt-out y ya no podrá seleccionarse para campañas."
      : "If a contact clicks it, an opt-out is recorded and it will no longer be selectable for campaigns.",
    whatsappOptOutPlaceholder: isEs ? "No recibir más información" : "Stop receiving updates",
    whatsappInterestToggle: isEs ? "Agregar botón de interés" : "Add interest button",
    whatsappInterestLabel: isEs ? "Texto botón de interés" : "Interest button text",
    whatsappInterestHelp: isEs
      ? "Si el contacto hace click, se registra interés y se crea ticket de seguimiento."
      : "If the contact clicks it, interest is recorded and a follow-up ticket is created.",
    whatsappInterestPlaceholder: isEs ? "Me interesa" : "I'm interested",
    formRulesTitle: isEs ? "Reglas antes de guardar" : "Rules before saving",
    formRuleName: isEs ? "Nombre de campaña obligatorio (mínimo 3 caracteres)." : "Campaign name is required (minimum 3 characters).",
    formRuleBody: isEs ? "Contenido obligatorio." : "Content is required.",
    formRuleCta: isEs ? "Si agregas URL, debe ser un enlace válido http(s)." : "If URL is provided, it must be a valid http(s) link.",
    formRuleWhatsappConnected: isEs
      ? "Para enviar por WhatsApp, primero conecta WhatsApp en Channels."
      : "To send via WhatsApp, connect WhatsApp first in Channels.",
    formErrorName: isEs ? "Falta nombre de campaña." : "Campaign name is missing.",
    formErrorBody: isEs ? "Falta contenido de campaña." : "Campaign content is missing.",
    formErrorCta: isEs ? "La URL del botón no es válida." : "Button URL is invalid.",
    formCannotSave: isEs ? "No se puede guardar todavía." : "Cannot save yet.",
    ctaNormalizedAs: isEs ? "Se guardará como:" : "Will be saved as:",
    consentBadgeTitle: isEs ? "Consentimiento" : "Consent",
    consentMissingExpiredBadge: isEs ? "Consent missing/expired" : "Consent missing/expired",
    consentIssueBadge: isEs ? "Problema de consentimiento" : "Consent issue",
    consentReasonMissingExpired: isEs
      ? "No existe consentimiento de marketing vigente o ya expiró para este contacto."
      : "No valid marketing consent exists, or it already expired for this contact.",
    consentReasonNotOptedIn: isEs
      ? "El contacto no aceptó marketing por email."
      : "The contact has not opted in to email marketing.",
    consentReasonMissingTerms: isEs
      ? "Falta aceptación de términos para marketing."
      : "Terms acceptance for marketing is missing.",
    consentReasonMissingEmailInConsent: isEs
      ? "El consentimiento no contiene email válido."
      : "The consent record does not include a valid email.",
    consentReasonMissingPhoneInConsent: isEs
      ? "El consentimiento no contiene teléfono válido."
      : "The consent record does not include a valid phone number.",
  };

  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState(null);

  const [audience, setAudience] = useState([]);
  const [audienceCounts, setAudienceCounts] = useState({ clients: 0, leads: 0 });
  const [campaigns, setCampaigns] = useState([]);

  const [audienceSearch, setAudienceSearch] = useState("");
  const [audienceSegment, setAudienceSegment] = useState("all");
  const [audienceInterest, setAudienceInterest] = useState("all");
  const [audienceEmailCountFilter, setAudienceEmailCountFilter] = useState("");
  const [audienceWhatsappCountFilter, setAudienceWhatsappCountFilter] = useState("");

  const [campaignSearch, setCampaignSearch] = useState("");
  const [campaignChannel, setCampaignChannel] = useState("all");
  const [campaignStatus, setCampaignStatus] = useState("all");

  const [selectedCampaignId, setSelectedCampaignId] = useState("");
  const [selectedCampaignDetail, setSelectedCampaignDetail] = useState(null);

  const [selectedRecipientKey, setSelectedRecipientKey] = useState("");
  const [recipientHistory, setRecipientHistory] = useState([]);
  const [selectedRecipients, setSelectedRecipients] = useState({});
  const [runCampaignOpen, setRunCampaignOpen] = useState(false);
  const [runCampaignStep, setRunCampaignStep] = useState("campaign");
  const [runCampaignResult, setRunCampaignResult] = useState(null);
  const [contentPreviewOpen, setContentPreviewOpen] = useState(false);
  const [campaignFormOpen, setCampaignFormOpen] = useState(false);
  const [uploadingImage, setUploadingImage] = useState(false);
  const [aiBusy, setAiBusy] = useState(false);
  const [imageFileName, setImageFileName] = useState("");
  const [whatsAppMetaConnected, setWhatsAppMetaConnected] = useState(false);
  const [editingCampaignId, setEditingCampaignId] = useState("");

  const [form, setForm] = useState({
    name: "",
    channel: "email",
    subject: "",
    body: "",
    image_url: "",
    cta_label: "",
    cta_url: "",
    language_family: isEs ? "es" : "en",
    whatsapp_interest_enabled: true,
    whatsapp_interest_label: "",
    whatsapp_opt_out_enabled: true,
    whatsapp_opt_out_label: "",
  });

  const fetchAudience = async ({ segment = "all", q = "" } = {}) => {
    if (!clientId) return { items: [], counts: { clients: 0, leads: 0 } };
    const params = new URLSearchParams({ client_id: clientId });
    if (segment !== "all") params.set("segment", segment);
    if (String(q || "").trim()) params.set("q", String(q).trim());

    const res = await authFetch(`${API}/marketing/audience?${params.toString()}`);
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data?.detail || "Failed loading audience");
    return {
      items: Array.isArray(data?.items) ? data.items : [],
      counts: data?.counts || { clients: 0, leads: 0 },
    };
  };

  const isChannelEnabled = (channel) => Boolean(channel?.is_active ?? channel?.active);

  const checkWhatsAppConnection = async () => {
    if (!clientId) return false;
    try {
      const res = await authFetch(`${API}/channels?client_id=${clientId}&type=whatsapp&provider=meta`);
      if (res.status === 404) {
        setWhatsAppMetaConnected(false);
        return false;
      }
      if (!res.ok) {
        setWhatsAppMetaConnected(false);
        return false;
      }
      const rows = await res.json().catch(() => []);
      const connected = Array.isArray(rows)
        ? rows.some((row) => isChannelEnabled(row) && String(row?.wa_phone_id || "").trim() !== "")
        : false;
      setWhatsAppMetaConnected(connected);
      return connected;
    } catch {
      setWhatsAppMetaConnected(false);
      return false;
    }
  };

  const loadAudience = async () => {
    if (!clientId) return;
    const result = await fetchAudience({ segment: audienceSegment, q: audienceSearch.trim() });
    setAudience(result.items);
    setAudienceCounts(result.counts);
  };

  const loadCampaigns = async () => {
    if (!clientId) return;
    const params = new URLSearchParams({ client_id: clientId });
    if (campaignChannel !== "all") params.set("channel", campaignChannel);
    if (campaignStatus !== "all") params.set("status", campaignStatus);
    if (campaignSearch.trim()) params.set("q", campaignSearch.trim());

    const res = await authFetch(`${API}/marketing/campaigns?${params.toString()}`);
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data?.detail || "Failed loading campaigns");

    const items = Array.isArray(data?.items) ? data.items : [];
    setCampaigns(items);
    if (selectedCampaignId && !items.some((item) => item?.id === selectedCampaignId)) {
      setSelectedCampaignId("");
    }
  };

  const loadCampaignDetail = async (campaignId) => {
    if (!clientId || !campaignId) {
      setSelectedCampaignDetail(null);
      return;
    }
    const params = new URLSearchParams({ client_id: clientId });
    const res = await authFetch(`${API}/marketing/campaigns/${campaignId}?${params.toString()}`);
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data?.detail || "Failed loading campaign detail");
    setSelectedCampaignDetail(data || null);
  };

  const loadRecipientHistory = async (recipientKey) => {
    if (!clientId || !recipientKey) {
      setRecipientHistory([]);
      return;
    }
    const params = new URLSearchParams({ client_id: clientId, recipient_key: recipientKey });
    const res = await authFetch(`${API}/marketing/audience/history?${params.toString()}`);
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data?.detail || "Failed loading recipient history");
    setRecipientHistory(Array.isArray(data?.items) ? data.items : []);
  };

  const refreshAll = async () => {
    if (!clientId) return;
    setLoading(true);
    setError("");
    try {
      await Promise.all([loadAudience(), loadCampaigns()]);
    } catch (err) {
      setError(err?.message || "Unexpected error");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refreshAll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clientId, audienceSegment, campaignChannel, campaignStatus]);

  useEffect(() => {
    checkWhatsAppConnection().catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clientId]);

  useEffect(() => {
    const handle = setTimeout(() => {
      if (!clientId) return;
      refreshAll();
    }, 350);
    return () => clearTimeout(handle);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [audienceSearch, campaignSearch]);

  useEffect(() => {
    loadCampaignDetail(selectedCampaignId).catch((err) => setError(err?.message || "Unexpected error"));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedCampaignId]);

  useEffect(() => {
    loadRecipientHistory(selectedRecipientKey).catch((err) => setError(err?.message || "Unexpected error"));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedRecipientKey]);

  const selectedCampaign = useMemo(() => {
    return campaigns.find((c) => c.id === selectedCampaignId) || null;
  }, [campaigns, selectedCampaignId]);

  const getCampaignSummaryMetrics = (campaign) => ({
    sent: Number(campaign?.sent_count || 0),
    responses: Number(campaign?.responses_count || 0),
    optOut: Number(campaign?.opt_out_count || 0),
    failed: Number(campaign?.failed_count || 0),
    blocked: Number(campaign?.blocked_policy_count || 0),
    skipped: Number(campaign?.skipped_count || 0),
  });

  const normalizeCtaUrl = (value) => {
    const raw = String(value || "").trim();
    if (!raw) return "";
    const candidate = /^[a-zA-Z][a-zA-Z0-9+.-]*:\/\//.test(raw)
      ? raw
      : `https://${raw.replace(/^\/+/, "")}`;
    try {
      const parsed = new URL(candidate);
      if (!["http:", "https:"].includes(parsed.protocol)) return "";
      return parsed.toString();
    } catch {
      return "";
    }
  };

  const selectedCampaignCtaUrl = useMemo(
    () => normalizeCtaUrl(selectedCampaign?.cta_url),
    [selectedCampaign?.cta_url],
  );
  const normalizedFormCtaUrl = useMemo(
    () => normalizeCtaUrl(form.cta_url),
    [form.cta_url],
  );
  const formValidationErrors = useMemo(() => {
    const errors = [];
    if (!String(form.name || "").trim()) errors.push(text.formErrorName);
    if (!String(form.body || "").trim()) errors.push(text.formErrorBody);
    const rawCtaUrl = String(form.cta_url || "").trim();
    if (rawCtaUrl && !normalizedFormCtaUrl) errors.push(text.formErrorCta);
    return errors;
  }, [form.name, form.body, form.cta_url, normalizedFormCtaUrl, text.formErrorName, text.formErrorBody, text.formErrorCta]);
  const canSaveCampaign = formValidationErrors.length === 0 && !busy && !uploadingImage;

  const selectedCampaignChannel = String(selectedCampaign?.channel || "").toLowerCase();
  const audienceByKey = useMemo(() => {
    const map = {};
    for (const row of audience || []) {
      const key = String(row?.recipient_key || "").trim();
      if (!key) continue;
      map[key] = row;
    }
    return map;
  }, [audience]);

  const isRecipientBlocked = (row) => {
    if (!row) return false;
    if (row?.selection_blocked) return true;
    return String(row?.selection_blocked_reason || "").toLowerCase() === "opt_out";
  };

  const isRecipientCompatible = (row, channel = selectedCampaignChannel) => {
    if (!channel) return true;
    if (channel === "email") return Boolean(row?.email);
    if (channel === "whatsapp") return Boolean(row?.phone);
    return true;
  };
  const getIncompatibleReason = (row, channel = selectedCampaignChannel) => {
    if (!channel) return "";
    if (channel === "email" && !row?.email) return text.incompatibleNoEmail;
    if (channel === "whatsapp" && !row?.phone) return text.incompatibleNoPhone;
    return "";
  };
  const getAudienceCommercialStatus = (row) => {
    if (!row) return "unknown";
    if (row?.selection_blocked || String(row?.selection_blocked_reason || "").toLowerCase() === "opt_out") {
      return "opt_out";
    }
    const normalized = String(row?.interest_status || "unknown").trim().toLowerCase();
    if (normalized === "interested" || normalized === "not_interested") return normalized;
    return "unknown";
  };

  const getAudienceCommercialStatusLabel = (row) => {
    const status = getAudienceCommercialStatus(row);
    if (status === "interested") return text.interested;
    if (status === "not_interested") return text.notInterested;
    if (status === "opt_out") return text.optOutStatus;
    return text.noResponse;
  };

  const matchesAudienceInterest = (row, filterValue = audienceInterest) => {
    if (filterValue === "all") return true;
    return getAudienceCommercialStatus(row) === filterValue;
  };

  const matchesCampaignCountFilters = (
    row,
    emailFilterValue = audienceEmailCountFilter,
    whatsappFilterValue = audienceWhatsappCountFilter,
  ) => {
    const normalizedEmailFilter = String(emailFilterValue || "").trim();
    const normalizedWhatsappFilter = String(whatsappFilterValue || "").trim();
    if (normalizedEmailFilter) {
      const expectedEmailCount = Number(normalizedEmailFilter);
      if (!Number.isFinite(expectedEmailCount) || expectedEmailCount < 0) return false;
      if (Number(row?.email_campaigns_sent_count || 0) !== expectedEmailCount) return false;
    }
    if (normalizedWhatsappFilter) {
      const expectedWhatsappCount = Number(normalizedWhatsappFilter);
      if (!Number.isFinite(expectedWhatsappCount) || expectedWhatsappCount < 0) return false;
      if (Number(row?.whatsapp_campaigns_sent_count || 0) !== expectedWhatsappCount) return false;
    }
    return true;
  };

  const formatDateTime = (value) => {
    try {
      const d = new Date(value);
      if (Number.isNaN(d.getTime())) return String(value || "");
      return d.toLocaleString(isEs ? "es-MX" : "en-US", {
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return String(value || "");
    }
  };

  const selectedRecipientKeys = useMemo(() => Object.keys(selectedRecipients), [selectedRecipients]);
  const filteredAudience = useMemo(
    () => (audience || []).filter(
      (row) => matchesAudienceInterest(row, audienceInterest) && matchesCampaignCountFilters(row)
    ),
    [audience, audienceInterest, audienceEmailCountFilter, audienceWhatsappCountFilter],
  );
  const emailCampaignCountOptions = useMemo(
    () => Array.from(
      new Set((audience || []).map((row) => Number(row?.email_campaigns_sent_count || 0)).filter(Number.isFinite))
    ).sort((a, b) => a - b),
    [audience],
  );
  const whatsappCampaignCountOptions = useMemo(
    () => Array.from(
      new Set((audience || []).map((row) => Number(row?.whatsapp_campaigns_sent_count || 0)).filter(Number.isFinite))
    ).sort((a, b) => a - b),
    [audience],
  );
  const selectedRecipientsList = useMemo(
    () => selectedRecipientKeys.map((key) => selectedRecipients[key]).filter(Boolean),
    [selectedRecipientKeys, selectedRecipients],
  );
  const sendableSelectedRecipients = useMemo(
    () => selectedRecipientsList.filter((row) => !isRecipientBlocked(row) && isRecipientCompatible(row)),
    [selectedRecipientsList, selectedCampaignChannel],
  );
  const excludedByChannelCount = Math.max(0, selectedRecipientsList.length - sendableSelectedRecipients.length);

  useEffect(() => {
    setSelectedRecipients((prev) => {
      const entries = Object.entries(prev).filter(([key, row]) => {
        const latest = audienceByKey[key] || row;
        if (isRecipientBlocked(latest)) return false;
        if (!selectedCampaignChannel) return true;
        return isRecipientCompatible(latest, selectedCampaignChannel);
      });
      if (entries.length === Object.keys(prev).length) return prev;
      return Object.fromEntries(entries);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedCampaignChannel, audienceByKey]);

  const addRecipientsToSelection = (rows) => {
    setSelectedRecipients((prev) => {
      const next = { ...prev };
      for (const row of rows || []) {
        const key = String(row?.recipient_key || "").trim();
        if (!key) continue;
        next[key] = row;
      }
      return next;
    });
  };

  const removeRecipientFromSelection = (recipientKey) => {
    setSelectedRecipients((prev) => {
      const next = { ...prev };
      delete next[recipientKey];
      return next;
    });
  };

  const toggleRecipientSelection = (row) => {
    if (isRecipientBlocked(row) || !isRecipientCompatible(row)) return;
    const key = String(row?.recipient_key || "").trim();
    if (!key) return;
    setSelectedRecipients((prev) => {
      if (prev[key]) {
        const next = { ...prev };
        delete next[key];
        return next;
      }
      return { ...prev, [key]: row };
    });
  };

  const selectVisibleAudience = () =>
    addRecipientsToSelection(filteredAudience.filter((row) => !isRecipientBlocked(row) && isRecipientCompatible(row)));

  const selectAudienceBySegment = async (segment) => {
    if (!clientId) return;
    setBusy(true);
    setError("");
    try {
      const result = await fetchAudience({ segment, q: "" });
      addRecipientsToSelection(
        result.items.filter(
          (row) =>
            matchesAudienceInterest(row) &&
            matchesCampaignCountFilters(row) &&
            !isRecipientBlocked(row) &&
            isRecipientCompatible(row)
        )
      );
    } catch (err) {
      setError(err?.message || "Unexpected error");
    } finally {
      setBusy(false);
    }
  };

  const clearRecipientSelection = () => setSelectedRecipients({});

  const resetCampaignForm = () => {
    setEditingCampaignId("");
    setForm({
      name: "",
      channel: "email",
      subject: "",
      body: "",
      image_url: "",
      cta_label: "",
      cta_url: "",
      language_family: isEs ? "es" : "en",
      whatsapp_interest_enabled: true,
      whatsapp_interest_label: "",
      whatsapp_opt_out_enabled: true,
      whatsapp_opt_out_label: "",
    });
    setImageFileName("");
  };

  const openCreateCampaignModal = () => {
    setNotice(null);
    setError("");
    resetCampaignForm();
    setCampaignFormOpen(true);
  };

  const handleCampaignImageUpload = async (file) => {
    if (!file) return;
    if (!String(file.type || "").startsWith("image/")) {
      setError(text.imageRequiredType);
      return;
    }
    if (file.size > 2 * 1024 * 1024) {
      setError(text.imageTooLarge);
      return;
    }
    if (!clientId) return;

    setUploadingImage(true);
    setError("");
    try {
      const formData = new FormData();
      formData.append("client_id", String(clientId));
      formData.append("file", file);

      const res = await authFetch(`${API}/message_templates/footer_image`, {
        method: "POST",
        body: formData,
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data?.detail || "Failed uploading image");

      const uploadedUrl = String(data?.url || "").trim();
      if (!uploadedUrl) throw new Error(isEs ? "No se recibió URL de la imagen." : "Image URL was not returned.");

      setForm((prev) => ({ ...prev, image_url: uploadedUrl }));
      setImageFileName(file.name || "");
    } catch (err) {
      setError(err?.message || "Unexpected error");
    } finally {
      setUploadingImage(false);
    }
  };

  const suggestCampaignBody = async () => {
    if (!clientId) return;
    if (!form.body.trim()) {
      setError(text.aiNeedsContent);
      return;
    }

    setAiBusy(true);
    setError("");
    setNotice(null);
    try {
      const payload = {
        client_id: clientId,
        body: form.body.trim(),
        channel: form.channel,
        language_family: form.language_family,
        cta_mode: form.cta_url.trim() ? "url" : null,
        cta_label: form.cta_label.trim() || null,
      };

      const res = await authFetch(`${API}/marketing/campaigns/rewrite`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data?.detail || "Failed generating AI suggestion");

      const rewrittenBody = String(data?.rewritten_body || "").trim();
      if (rewrittenBody) {
        setForm((prev) => ({ ...prev, body: rewrittenBody }));
        setNotice({ type: "success", message: text.aiApplied });
      }
    } catch (err) {
      setError(err?.message || "Unexpected error");
    } finally {
      setAiBusy(false);
    }
  };

  const startEditCampaign = () => {
    if (!selectedCampaign) return;
    setEditingCampaignId(String(selectedCampaign.id || ""));
    setForm((prev) => ({
      ...prev,
      name: selectedCampaign.name || "",
      channel: selectedCampaign.channel || "email",
      subject: selectedCampaign.subject || "",
      body: selectedCampaign.body || "",
      image_url: selectedCampaign.image_url || "",
      cta_label: selectedCampaign.cta_label || "",
      cta_url: selectedCampaign.cta_url || "",
      language_family: selectedCampaign.language_family || (isEs ? "es" : "en"),
      whatsapp_interest_enabled: selectedCampaign.whatsapp_interest_enabled ?? true,
      whatsapp_interest_label: selectedCampaign.whatsapp_interest_label || "",
      whatsapp_opt_out_enabled: selectedCampaign.whatsapp_opt_out_enabled ?? true,
      whatsapp_opt_out_label: selectedCampaign.whatsapp_opt_out_label || "",
    }));
    setImageFileName("");
    setNotice(null);
    setError("");
    setCampaignFormOpen(true);
  };

  const cancelCampaignEdit = () => {
    resetCampaignForm();
    setCampaignFormOpen(false);
  };

  const archiveSelectedCampaign = async () => {
    if (!clientId || !selectedCampaign?.id) return;
    if (!window.confirm(text.archiveConfirm)) return;

    setBusy(true);
    setError("");
    setNotice(null);
    try {
      const params = new URLSearchParams({ client_id: clientId });
      const res = await authFetch(`${API}/marketing/campaigns/${selectedCampaign.id}?${params.toString()}`, {
        method: "DELETE",
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data?.detail || "Failed archiving campaign");

      setNotice({ type: "success", message: text.archiveSuccess });
      await refreshAll();
      setSelectedCampaignId("");
      setSelectedCampaignDetail(null);
      if (String(editingCampaignId || "") === String(selectedCampaign.id || "")) {
        cancelCampaignEdit();
      }
    } catch (err) {
      setError(err?.message || "Unexpected error");
    } finally {
      setBusy(false);
    }
  };

  const createCampaign = async () => {
    if (!clientId) return;
    if (!form.name.trim() || !form.body.trim()) {
      setError(isEs ? "Nombre y contenido son obligatorios." : "Name and content are required.");
      return;
    }

    setBusy(true);
    setError("");
    try {
      const rawCtaUrl = form.cta_url.trim();
      const normalizedCtaUrl = rawCtaUrl ? normalizedFormCtaUrl : null;
      if (rawCtaUrl && !normalizedCtaUrl) {
        setError(text.invalidCtaUrl);
        return;
      }
      const payload = {
        client_id: clientId,
        name: form.name.trim(),
        channel: form.channel,
        subject: form.channel === "email" ? (form.subject.trim() || form.name.trim()) : null,
        body: form.body.trim(),
        image_url: form.image_url.trim() || null,
        cta_mode: normalizedCtaUrl ? "url" : null,
        cta_label: normalizedCtaUrl ? (form.cta_label.trim() || null) : null,
        cta_url: normalizedCtaUrl,
        language_family: form.language_family,
        whatsapp_interest_enabled: form.channel === "whatsapp" ? Boolean(form.whatsapp_interest_enabled) : null,
        whatsapp_interest_label: form.channel === "whatsapp"
          ? (form.whatsapp_interest_enabled ? (form.whatsapp_interest_label.trim() || null) : null)
          : null,
        whatsapp_opt_out_enabled: form.channel === "whatsapp" ? Boolean(form.whatsapp_opt_out_enabled) : null,
        whatsapp_opt_out_label: form.channel === "whatsapp"
          ? (form.whatsapp_opt_out_enabled ? (form.whatsapp_opt_out_label.trim() || null) : null)
          : null,
      };

      const isEditing = Boolean(editingCampaignId);
      const endpoint = isEditing
        ? `${API}/marketing/campaigns/${editingCampaignId}`
        : `${API}/marketing/campaigns`;
      const method = isEditing ? "PATCH" : "POST";
      const requestPayload = isEditing
        ? { ...payload, channel: undefined }
        : payload;
      const res = await authFetch(endpoint, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(requestPayload),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data?.detail || `Failed ${method === "POST" ? "creating" : "updating"} campaign`);
      const whatsappSync = data?.whatsapp_sync;
      const hasSyncErrors = Array.isArray(whatsappSync?.errors) && whatsappSync.errors.length > 0;

      if (isEditing && String(form.channel || "").toLowerCase() === "whatsapp") {
        setNotice({
          type: hasSyncErrors ? "warning" : "success",
          message: `${text.whatsappEditVersions} ${hasSyncErrors ? text.whatsappSyncWarning : text.whatsappSyncSuccess}`.trim(),
        });
      } else if (isEditing) {
        setNotice({ type: "success", message: isEs ? "Campaña actualizada." : "Campaign updated." });
      } else if (String(form.channel || "").toLowerCase() === "whatsapp") {
        setNotice({
          type: hasSyncErrors ? "warning" : "success",
          message: hasSyncErrors ? text.whatsappSyncWarning : text.whatsappSyncSuccess,
        });
      }

      resetCampaignForm();
      setCampaignFormOpen(false);
      await refreshAll();
      const createdId = data?.campaign?.id;
      if (createdId) setSelectedCampaignId(createdId);
    } catch (err) {
      setError(err?.message || "Unexpected error");
    } finally {
      setBusy(false);
    }
  };

  const openRunCampaignModal = async () => {
    if (!clientId) return;
    setError("");
    setNotice(null);
    setRunCampaignResult(null);
    setRunCampaignStep("campaign");
    clearRecipientSelection();
    setRunCampaignOpen(true);
    try {
      await Promise.all([loadCampaigns(), loadAudience()]);
    } catch (err) {
      setError(err?.message || "Unexpected error");
    }
  };

  const closeRunCampaignModal = () => {
    if (busy) return;
    setRunCampaignOpen(false);
    setRunCampaignStep("campaign");
    setRunCampaignResult(null);
    clearRecipientSelection();
  };

  const pickCampaign = (campaignId) => {
    setSelectedCampaignId(campaignId);
  };

  const continueToRecipients = async () => {
    if (!selectedCampaign?.id) {
      setError(text.runCampaignSelectCampaign);
      return;
    }
    if (selectedCampaignChannel === "whatsapp") {
      const isConnected = await checkWhatsAppConnection();
      if (!isConnected) {
        setError(text.whatsappNotConnected);
        return;
      }
    }
    setError("");
    setRunCampaignStep("recipients");
  };

  const continueToPreview = async () => {
    if (!selectedCampaign?.id) {
      setError(text.selectCampaignFirst);
      return;
    }
    if (selectedRecipientsList.length === 0) {
      setError(text.runCampaignSelectRecipients);
      return;
    }
    if (sendableSelectedRecipients.length === 0) {
      setError(text.noSendableRecipients);
      return;
    }
    setError("");
    setRunCampaignStep("preview");
  };

  const confirmRunCampaign = async () => {
    if (!clientId || !selectedCampaign?.id) return;
    setBusy(true);
    setError("");
    setNotice(null);
    try {
      const payload = {
        client_id: clientId,
        recipient_keys: sendableSelectedRecipients.map((row) => row.recipient_key).filter(Boolean),
      };
      const res = await authFetch(`${API}/marketing/campaigns/${selectedCampaign.id}/send`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data?.detail || "Failed sending campaign");

      const summary = data?.summary || {};
      const sent = Number(summary.sent || 0);
      const failed = Number(summary.failed || 0);
      const blocked = Number(summary.blocked_policy || 0);
      const skipped = Number(summary.skipped || 0);
      const imageFallbackNoHeader = Number(summary.image_fallback_no_header || 0);
      const imageSkippedNoHeaderTemplate = Number(summary.image_skipped_no_header_template || 0);

      const messageCounts = `${text.sent}: ${sent} · ${text.failed}: ${failed} · ${text.blocked}: ${blocked} · ${text.skipped}: ${skipped}`;
      let message = `${text.sendSummaryFailed} ${messageCounts}`;
      let type = "error";
      if (sent > 0 && failed === 0 && blocked === 0) {
        let extra = "";
        if (imageSkippedNoHeaderTemplate > 0) extra += ` ${text.sendSummaryImageNoHeader}`;
        if (imageFallbackNoHeader > 0) extra += ` ${text.sendSummaryImageFallback}`;
        message = `${text.sendSummarySuccess} ${messageCounts}${extra}`;
        type = "success";
      } else if (sent > 0) {
        let extra = "";
        if (imageSkippedNoHeaderTemplate > 0) extra += ` ${text.sendSummaryImageNoHeader}`;
        if (imageFallbackNoHeader > 0) extra += ` ${text.sendSummaryImageFallback}`;
        message = `${text.sendSummaryPartial} ${messageCounts}${extra}`;
        type = "warning";
      }
      setRunCampaignResult({ type, message, sent, failed, blocked, skipped });
      setRunCampaignStep("result");
      setNotice(type === "error" ? null : { type: type === "success" ? "success" : "warning", message });

      await refreshAll();
      await loadCampaignDetail(selectedCampaign.id);
      clearRecipientSelection();
    } catch (err) {
      setError(err?.message || "Unexpected error");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="ia-page">
      <div className="ia-shell ia-services-shell">
        <section className="ia-card" style={{ marginBottom: 0 }}>
          <h2 className="ia-header-title">📣 {text.title}</h2>
          <p className="ia-header-subtitle">{text.subtitle}</p>

          {error ? (
            <div style={{ marginTop: "0.75rem", border: "1px solid #fecaca", background: "#fff1f2", color: "#b91c1c", borderRadius: 10, padding: "0.65rem" }}>
              {error}
            </div>
          ) : null}

          {notice ? (
            <div
              style={{
                marginTop: "0.75rem",
                border: notice.type === "success" ? "1px solid #bbf7d0" : "1px solid #fde68a",
                background: notice.type === "success" ? "#ecfdf3" : "#fffbeb",
                color: notice.type === "success" ? "#065f46" : "#92400e",
                borderRadius: 10,
                padding: "0.65rem",
              }}
            >
              {notice.message}
            </div>
          ) : null}

          <div style={{ ...rowBetweenStyle, marginTop: "0.9rem", alignItems: "flex-start" }}>
            <div>
              <strong style={{ ...panelTitleStyle, fontSize: "1rem" }}>{text.campaignHistoryTitle}</strong>
              <p style={{ ...hintStyle, marginTop: "0.2rem" }}>{text.campaignHistorySubtitle}</p>
            </div>
            <div style={{ display: "flex", gap: "0.45rem", flexWrap: "wrap", justifyContent: "flex-end" }}>
              <button type="button" className="ia-button ia-button-primary" onClick={openCreateCampaignModal} disabled={busy}>
                {text.createNewCampaign}
              </button>
            </div>
          </div>

          <div style={{ ...panelStyle, marginTop: "0.8rem" }}>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(220px,1fr))", gap: "0.55rem", marginBottom: "0.7rem" }}>
              <input
                className="ia-form-input"
                placeholder={text.searchCampaigns}
                value={campaignSearch}
                onChange={(e) => setCampaignSearch(e.target.value)}
              />
              <select className="ia-form-input" value={campaignChannel} onChange={(e) => setCampaignChannel(e.target.value)}>
                <option value="all">{text.all}</option>
                <option value="email">Email</option>
                <option value="whatsapp">WhatsApp</option>
              </select>
              <select className="ia-form-input" value={campaignStatus} onChange={(e) => setCampaignStatus(e.target.value)}>
                <option value="all">{text.all}</option>
                <option value="draft">{text.draft}</option>
                <option value="active">Active</option>
                <option value="sent">Sent</option>
                <option value="paused">Paused</option>
              </select>
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: "0.55rem", maxHeight: 620, overflowY: "auto" }}>
              {campaigns.length === 0 ? <p style={hintStyle}>{text.noCampaigns}</p> : null}
              {campaigns.map((campaign) => {
                const metrics = getCampaignSummaryMetrics(campaign);
                const isActiveCampaign = selectedCampaignId === campaign.id;
                const detailRecipients = isActiveCampaign ? (selectedCampaignDetail?.recipients || []) : [];
                return (
                  <div
                    key={`history-${campaign.id}`}
                    style={{ ...itemCardStyle, ...(isActiveCampaign ? campaignBtnActiveStyle : {}), background: "#fff" }}
                  >
                    <button
                      type="button"
                      onClick={() => setSelectedCampaignId((current) => (current === campaign.id ? "" : campaign.id))}
                      style={{ width: "100%", border: "none", background: "transparent", padding: 0, textAlign: "left", cursor: "pointer" }}
                    >
                      <div style={rowBetweenStyle}>
                        <strong style={{ color: "#0f172a" }}>{campaign.name}</strong>
                        <span style={badgeStyle}>{campaign.channel}</span>
                      </div>
                      <small style={smallStyle}>
                        {campaign.status}
                        {campaign.subject ? ` · ${campaign.subject}` : ""}
                      </small>
                      <div style={{ marginTop: "0.45rem", display: "flex", gap: "0.35rem", flexWrap: "wrap" }}>
                        <span style={badgeStyle}>{text.campaignMetricsSent}: {metrics.sent}</span>
                        <span style={badgeStyle}>{text.campaignMetricsResponses}: {metrics.responses}</span>
                        <span style={badgeStyle}>{text.campaignMetricsOptOut}: {metrics.optOut}</span>
                        <span style={badgeStyle}>{text.campaignMetricsFailed}: {metrics.failed}</span>
                        <span style={badgeStyle}>{text.campaignMetricsBlocked}: {metrics.blocked}</span>
                        <span style={badgeStyle}>{text.campaignMetricsSkipped}: {metrics.skipped}</span>
                      </div>
                    </button>

                    {isActiveCampaign ? (
                      <div style={{ marginTop: "0.75rem", paddingTop: "0.75rem", borderTop: "1px solid #E5E7EB" }}>
                        <p style={{ ...smallStyle, color: "#334155", margin: 0 }}>
                          {campaign.body || ""}
                        </p>

                        <div style={{ marginTop: "0.55rem", display: "flex", gap: "0.35rem", flexWrap: "wrap" }}>
                          <button
                            type="button"
                            className="ia-button ia-button-ghost"
                            style={{ padding: "0.28rem 0.5rem", fontSize: "0.76rem" }}
                            onClick={() => setContentPreviewOpen(true)}
                          >
                            {text.campaignPreview}
                          </button>
                          <button
                            type="button"
                            className="ia-button ia-button-ghost"
                            style={{ padding: "0.28rem 0.5rem", fontSize: "0.76rem" }}
                            onClick={startEditCampaign}
                          >
                            {text.editCampaign}
                          </button>
                          <button
                            type="button"
                            className="ia-button ia-button-ghost"
                            style={{ padding: "0.28rem 0.5rem", fontSize: "0.76rem", color: "#b91c1c", borderColor: "#fecaca", background: "#fff1f2" }}
                            onClick={archiveSelectedCampaign}
                            disabled={busy}
                          >
                            {text.archiveCampaign}
                          </button>
                        </div>

                        <div style={{ marginTop: "0.75rem" }}>
                          <strong style={panelTitleStyle}>{text.recipients}</strong>
                          <div style={{ marginTop: "0.45rem", display: "flex", flexDirection: "column", gap: "0.45rem", maxHeight: 260, overflowY: "auto" }}>
                            {detailRecipients.map((row) => (
                              <div key={`${row.campaign_id}-${row.recipient_key}`} style={{ ...itemCardStyle, background: "#f8fafc" }}>
                                <div style={rowBetweenStyle}>
                                  <strong>{row.recipient_name || row.email || row.phone || row.recipient_key}</strong>
                                  <div style={{ display: "flex", gap: "0.35rem", flexWrap: "wrap", justifyContent: "flex-end" }}>
                                    <span style={sendStatusChip(row.send_status)}>{row.send_status}</span>
                                    <span style={interestStatusChip(row.response_status || "unknown")}>
                                      {getAudienceCommercialStatusLabel({
                                        interest_status: row.response_status,
                                        selection_blocked_reason: row.response_status === "opt_out" ? "opt_out" : "",
                                      })}
                                    </span>
                                  </div>
                                </div>
                                <small style={smallStyle}>{row.email || ""} {row.phone ? ` · ${row.phone}` : ""}</small>
                                <div style={{ marginTop: "0.28rem", display: "flex", gap: "0.35rem", flexWrap: "wrap" }}>
                                  {row.sent_at ? <span style={badgeStyle}>{isEs ? "Enviado" : "Sent"}: {formatDateTime(row.sent_at)}</span> : null}
                                  {row.response_at ? <span style={badgeStyle}>{isEs ? "Respuesta" : "Response"}: {formatDateTime(row.response_at)}</span> : null}
                                </div>
                              </div>
                            ))}
                            {detailRecipients.length === 0 ? (
                              <p style={hintStyle}>{isEs ? "Aún no hay destinatarios enviados." : "No recipients sent yet."}</p>
                            ) : null}
                          </div>
                        </div>
                      </div>
                    ) : null}
                  </div>
                );
              })}
            </div>
          </div>

          <div style={{ display: "flex", justifyContent: "flex-end", marginTop: "0.9rem" }}>
            <button type="button" className="ia-button ia-button-warning" onClick={openRunCampaignModal} disabled={busy}>
              {text.runCampaign}
            </button>
          </div>

          {selectedRecipientKey ? (
            <div style={{ ...panelStyle, marginTop: "0.9rem" }}>
              <div style={rowBetweenStyle}>
                <strong style={panelTitleStyle}>{text.history}</strong>
                <button className="ia-button ia-button-ghost" onClick={() => setSelectedRecipientKey("")}>{text.close}</button>
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: "0.45rem", maxHeight: 220, overflowY: "auto" }}>
                {recipientHistory.map((row, idx) => (
                  <div key={`${row.campaign_id}-${idx}`} style={itemCardStyle}>
                    <div style={rowBetweenStyle}>
                      <strong>{row.campaign_name}</strong>
                      <div style={{ display: "flex", gap: "0.35rem", flexWrap: "wrap", justifyContent: "flex-end" }}>
                        <span style={sendStatusChip(row.send_status)}>{row.send_status}</span>
                        <span style={interestStatusChip(row.response_status || "unknown")}>
                          {getAudienceCommercialStatusLabel({ interest_status: row.response_status, selection_blocked_reason: row.response_status === "opt_out" ? "opt_out" : "" })}
                        </span>
                      </div>
                    </div>
                    <small style={smallStyle}>
                      {row.campaign_channel}
                      {row.sent_at || row.updated_at ? ` · ${formatDateTime(row.response_at || row.sent_at || row.updated_at)}` : ""}
                    </small>
                  </div>
                ))}
                {recipientHistory.length === 0 ? <p style={hintStyle}>{isEs ? "Sin historial." : "No history."}</p> : null}
              </div>
            </div>
          ) : null}

          {campaignFormOpen ? (
            <div style={modalOverlayStyle} role="dialog" aria-modal="true">
              <div style={{ ...modalCardStyle, width: "min(980px, 100%)" }}>
                <div style={{ ...rowBetweenStyle, marginBottom: "0.55rem" }}>
                  <div>
                    <strong style={{ fontSize: "1rem", color: "#0f172a" }}>
                      {editingCampaignId ? text.campaignFormEditTitle : text.campaignFormCreateTitle}
                    </strong>
                    <p style={{ ...hintStyle, marginTop: "0.2rem" }}>{text.campaignFormSubtitle}</p>
                  </div>
                  <button type="button" className="ia-button ia-button-ghost" onClick={cancelCampaignEdit} disabled={busy || uploadingImage}>
                    {text.close}
                  </button>
                </div>

                <div style={{ ...itemCardStyle, background: "#fff7ed", borderColor: "#fed7aa", marginBottom: "0.7rem" }}>
                  <strong style={{ ...smallStyle, color: "#7c2d12" }}>{text.formRulesTitle}</strong>
                  <ul style={{ margin: "0.35rem 0 0 1rem", padding: 0, color: "#9a3412", fontSize: "0.8rem", lineHeight: 1.45 }}>
                    <li>{text.formRuleName}</li>
                    <li>{text.formRuleBody}</li>
                    <li>{text.formRuleCta}</li>
                    {form.channel === "whatsapp" ? <li>{text.formRuleWhatsappConnected}</li> : null}
                  </ul>
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(320px,1fr))", gap: "0.8rem" }}>
                  <div style={{ display: "flex", flexDirection: "column", gap: "0.55rem" }}>
                    <input
                      className="ia-form-input"
                      placeholder={isEs ? "Nombre de campaña" : "Campaign name"}
                      value={form.name}
                      onChange={(e) => setForm((prev) => ({ ...prev, name: e.target.value }))}
                    />

                    <select
                      className="ia-form-input"
                      value={form.channel}
                      onChange={(e) => {
                        const nextChannel = e.target.value;
                        setForm((prev) => ({
                          ...prev,
                          channel: nextChannel,
                        }));
                      }}
                      disabled={Boolean(editingCampaignId)}
                    >
                      <option value="email">Email</option>
                      <option value="whatsapp">WhatsApp</option>
                    </select>

                    {form.channel === "email" ? (
                      <input
                        className="ia-form-input"
                        placeholder={isEs ? "Asunto" : "Subject"}
                        value={form.subject}
                        onChange={(e) => setForm((prev) => ({ ...prev, subject: e.target.value }))}
                      />
                    ) : null}

                    <textarea
                      className="ia-form-input"
                      rows={7}
                      placeholder={isEs ? "Contenido de campaña" : "Campaign content"}
                      value={form.body}
                      onChange={(e) => setForm((prev) => ({ ...prev, body: e.target.value }))}
                    />
                    <div style={{ display: "flex", justifyContent: "flex-end", marginTop: "-0.2rem", marginBottom: "0.25rem" }}>
                      <button
                        type="button"
                        className="ia-button ia-button-ghost"
                        style={{ padding: "0.28rem 0.5rem", fontSize: "0.76rem" }}
                        onClick={suggestCampaignBody}
                        disabled={busy || aiBusy || !form.body.trim()}
                      >
                        {aiBusy ? text.aiRestructuring : text.aiRestructure}
                      </button>
                    </div>
                  </div>

                  <div style={{ display: "flex", flexDirection: "column", gap: "0.55rem" }}>
                    <div style={{ ...itemCardStyle, background: "#f8fafc" }}>
                      <label style={{ ...smallStyle, display: "block", marginBottom: "0.35rem" }}>
                        {isEs ? "Imagen de campaña (opcional)" : "Campaign image (optional)"}
                      </label>
                      <input
                        type="file"
                        accept="image/*"
                        className="ia-form-input"
                        onChange={(e) => handleCampaignImageUpload(e.target.files?.[0])}
                        disabled={uploadingImage}
                      />
                      <div style={{ marginTop: "0.4rem", display: "flex", gap: "0.35rem", alignItems: "center", flexWrap: "wrap" }}>
                        <span style={badgeStyle}>
                          {uploadingImage ? text.uploadingImage : form.image_url ? text.imageReady : text.uploadImage}
                        </span>
                        {imageFileName ? <small style={smallStyle}>{imageFileName}</small> : null}
                        {form.image_url ? (
                          <button
                            type="button"
                            className="ia-button ia-button-ghost"
                            style={{ padding: "0.22rem 0.45rem", fontSize: "0.72rem" }}
                            onClick={() => {
                              setForm((prev) => ({ ...prev, image_url: "" }));
                              setImageFileName("");
                            }}
                            disabled={uploadingImage}
                          >
                            {text.removeImage}
                          </button>
                        ) : null}
                      </div>
                      {form.image_url ? (
                        <img
                          src={form.image_url}
                          alt="campaign upload"
                          style={{ marginTop: "0.45rem", width: "100%", maxHeight: 160, objectFit: "contain", borderRadius: 10, border: "1px solid #E5E7EB", background: "#f8fafc" }}
                        />
                      ) : null}
                    </div>

                    {form.channel === "whatsapp" ? (
                      <div style={{ ...itemCardStyle, background: "#f8fafc" }}>
                        <strong style={{ ...smallStyle, color: "#0f172a" }}>{text.whatsappFormatTitle}</strong>
                        <ul style={{ margin: "0.35rem 0 0 1rem", padding: 0, color: "#334155", fontSize: "0.8rem", lineHeight: 1.4 }}>
                          <li>{text.whatsappFormatLine1}</li>
                          <li>{text.whatsappFormatLine2}</li>
                          <li>{text.whatsappFormatLine3}</li>
                          <li>{text.whatsappFormatLine4}</li>
                          <li>{text.whatsappFormatLine5}</li>
                        </ul>
                      </div>
                    ) : null}

                    {form.channel === "whatsapp" ? (
                      <div style={{ ...itemCardStyle, background: "#f8fafc" }}>
                        <label style={{ display: "flex", alignItems: "center", gap: "0.45rem", marginBottom: "0.45rem" }}>
                          <input
                            type="checkbox"
                            checked={Boolean(form.whatsapp_interest_enabled)}
                            onChange={(e) => setForm((prev) => ({ ...prev, whatsapp_interest_enabled: e.target.checked }))}
                          />
                          <strong style={{ ...smallStyle, color: "#0f172a" }}>{text.whatsappInterestToggle}</strong>
                        </label>
                        {form.whatsapp_interest_enabled ? (
                          <>
                            <small style={{ ...smallStyle, display: "block", marginBottom: "0.25rem", color: "#334155" }}>
                              {text.whatsappInterestLabel}
                            </small>
                            <input
                              className="ia-form-input"
                              placeholder={text.whatsappInterestPlaceholder}
                              value={form.whatsapp_interest_label}
                              onChange={(e) => setForm((prev) => ({ ...prev, whatsapp_interest_label: e.target.value }))}
                            />
                          </>
                        ) : null}
                        <small style={{ ...smallStyle, display: "block", marginTop: "0.35rem" }}>
                          {text.whatsappInterestHelp}
                        </small>
                      </div>
                    ) : null}

                    {form.channel === "whatsapp" ? (
                      <div style={{ ...itemCardStyle, background: "#f8fafc" }}>
                        <label style={{ display: "flex", alignItems: "center", gap: "0.45rem", marginBottom: "0.45rem" }}>
                          <input
                            type="checkbox"
                            checked={Boolean(form.whatsapp_opt_out_enabled)}
                            onChange={(e) => setForm((prev) => ({ ...prev, whatsapp_opt_out_enabled: e.target.checked }))}
                          />
                          <strong style={{ ...smallStyle, color: "#0f172a" }}>{text.whatsappOptOutToggle}</strong>
                        </label>
                        {form.whatsapp_opt_out_enabled ? (
                          <>
                            <small style={{ ...smallStyle, display: "block", marginBottom: "0.25rem", color: "#334155" }}>
                              {text.whatsappOptOutLabel}
                            </small>
                            <input
                              className="ia-form-input"
                              placeholder={text.whatsappOptOutPlaceholder}
                              value={form.whatsapp_opt_out_label}
                              onChange={(e) => setForm((prev) => ({ ...prev, whatsapp_opt_out_label: e.target.value }))}
                            />
                          </>
                        ) : null}
                        <small style={{ ...smallStyle, display: "block", marginTop: "0.35rem" }}>
                          {text.whatsappOptOutHelp}
                        </small>
                      </div>
                    ) : null}

                    <input
                      className="ia-form-input"
                      placeholder={isEs ? "Texto botón de redirección (opcional)" : "Redirect button text (optional)"}
                      value={form.cta_label}
                      onChange={(e) => setForm((prev) => ({ ...prev, cta_label: e.target.value }))}
                    />

                    <input
                      className="ia-form-input"
                      placeholder={isEs ? "URL de redirección (opcional) https://..." : "Redirect URL (optional) https://..."}
                      value={form.cta_url}
                      onChange={(e) => setForm((prev) => ({ ...prev, cta_url: e.target.value }))}
                    />
                    {String(form.cta_url || "").trim() ? (
                      <small style={{ ...smallStyle, color: normalizedFormCtaUrl ? "#065f46" : "#b91c1c" }}>
                        {normalizedFormCtaUrl
                          ? `${text.ctaNormalizedAs} ${normalizedFormCtaUrl}`
                          : text.invalidCtaUrl}
                      </small>
                    ) : null}

                    <select
                      className="ia-form-input"
                      value={form.language_family}
                      onChange={(e) => setForm((prev) => ({ ...prev, language_family: e.target.value }))}
                    >
                      <option value="es">Español</option>
                      <option value="en">English</option>
                    </select>
                  </div>
                </div>

                <div style={{ display: "flex", justifyContent: "space-between", gap: "0.45rem", flexWrap: "wrap", marginTop: "0.45rem" }}>
                  <button type="button" className="ia-button ia-button-ghost" disabled={busy || uploadingImage} onClick={cancelCampaignEdit}>
                    {text.cancel}
                  </button>
                  <button type="button" className="ia-button ia-button-primary" disabled={!canSaveCampaign} onClick={createCampaign}>
                    {busy ? text.loading : (editingCampaignId ? text.updateCampaign : text.create)}
                  </button>
                </div>
                {formValidationErrors.length > 0 ? (
                  <div style={{ ...itemCardStyle, marginTop: "0.6rem", background: "#fef2f2", borderColor: "#fecaca" }}>
                    <strong style={{ ...smallStyle, color: "#b91c1c" }}>{text.formCannotSave}</strong>
                    <ul style={{ margin: "0.35rem 0 0 1rem", padding: 0, color: "#b91c1c", fontSize: "0.8rem", lineHeight: 1.4 }}>
                      {formValidationErrors.map((rule) => (
                        <li key={rule}>{rule}</li>
                      ))}
                    </ul>
                  </div>
                ) : null}
              </div>
            </div>
          ) : null}

          {contentPreviewOpen && selectedCampaign ? (
            <div style={modalOverlayStyle} role="dialog" aria-modal="true">
              <div style={modalCardStyle}>
                <div style={{ ...rowBetweenStyle, marginBottom: "0.55rem" }}>
                  <div>
                    <strong style={{ fontSize: "1rem", color: "#0f172a" }}>{text.campaignPreview}</strong>
                    <p style={{ ...hintStyle, marginTop: "0.2rem" }}>{text.previewContent}</p>
                  </div>
                  <button type="button" className="ia-button ia-button-ghost" onClick={() => setContentPreviewOpen(false)}>
                    {text.close}
                  </button>
                </div>

                <div style={{ ...itemCardStyle, background: "#fff" }}>
                  <div style={{ ...rowBetweenStyle, marginBottom: "0.4rem" }}>
                    <strong>{selectedCampaign.name}</strong>
                    <span style={badgeStyle}>{selectedCampaign.channel}</span>
                  </div>
                  {selectedCampaign.channel === "email" ? (
                    <small style={{ ...smallStyle, display: "block", marginBottom: "0.4rem" }}>
                      {selectedCampaign.subject || selectedCampaign.name}
                    </small>
                  ) : null}
                  <div style={{ whiteSpace: "pre-wrap", color: "#0f172a", fontSize: "0.9rem", lineHeight: 1.45 }}>
                    {selectedCampaign.body || ""}
                  </div>
                  {selectedCampaign.image_url ? (
                    <img
                      src={selectedCampaign.image_url}
                      alt="campaign preview"
                      style={{ width: "100%", maxHeight: "52vh", objectFit: "contain", borderRadius: 10, marginTop: "0.55rem", border: "1px solid #E5E7EB", background: "#f8fafc" }}
                    />
                  ) : null}
                  {selectedCampaignCtaUrl ? (
                    <a
                      href={selectedCampaignCtaUrl}
                      target="_blank"
                      rel="noreferrer"
                      style={{ display: "inline-block", marginTop: "0.55rem", padding: "0.45rem 0.7rem", borderRadius: 8, background: "#1d4ed8", color: "#fff", textDecoration: "none", fontSize: "0.82rem" }}
                    >
                      {selectedCampaign.cta_label || (isEs ? "Abrir sitio" : "Open site")}
                    </a>
                  ) : null}
                  {selectedCampaign.channel === "whatsapp" && selectedCampaign.whatsapp_interest_enabled ? (
                    <span
                      style={{
                        display: "inline-block",
                        marginTop: "0.45rem",
                        marginLeft: selectedCampaignCtaUrl ? "0.45rem" : 0,
                        padding: "0.38rem 0.62rem",
                        borderRadius: 8,
                        border: "1px solid #bfdbfe",
                        background: "#eff6ff",
                        color: "#1d4ed8",
                        fontSize: "0.8rem",
                      }}
                    >
                      {selectedCampaign.whatsapp_interest_label || text.whatsappInterestPlaceholder}
                    </span>
                  ) : null}
                  {selectedCampaign.channel === "whatsapp" && selectedCampaign.whatsapp_opt_out_enabled ? (
                    <span
                      style={{
                        display: "inline-block",
                        marginTop: "0.45rem",
                        marginLeft: selectedCampaignCtaUrl ? "0.45rem" : 0,
                        padding: "0.38rem 0.62rem",
                        borderRadius: 8,
                        border: "1px solid #fecaca",
                        background: "#fff1f2",
                        color: "#9f1239",
                        fontSize: "0.8rem",
                      }}
                    >
                      {selectedCampaign.whatsapp_opt_out_label || text.whatsappOptOutPlaceholder}
                    </span>
                  ) : null}
                </div>
              </div>
            </div>
          ) : null}

          {runCampaignOpen ? (
            <div style={modalOverlayStyle} role="dialog" aria-modal="true">
              <div style={modalCardStyle}>
                <div style={{ ...rowBetweenStyle, marginBottom: "0.55rem" }}>
                  <div>
                    <strong style={{ fontSize: "1rem", color: "#0f172a" }}>{text.runCampaignTitle}</strong>
                    <p style={{ ...hintStyle, marginTop: "0.2rem" }}>{text.runCampaignSubtitle}</p>
                  </div>
                  <button type="button" className="ia-button ia-button-ghost" onClick={closeRunCampaignModal} disabled={busy}>
                    {runCampaignStep === "result" ? text.finish : text.cancel}
                  </button>
                </div>

                <div style={{ display: "flex", gap: "0.35rem", flexWrap: "wrap", marginBottom: "0.75rem" }}>
                  <span style={runFlowStepChip(runCampaignStep === "campaign")}>{text.runCampaignStepCampaign}</span>
                  <span style={runFlowStepChip(runCampaignStep === "recipients")}>{text.runCampaignStepRecipients}</span>
                  <span style={runFlowStepChip(runCampaignStep === "preview")}>{text.runCampaignStepPreview}</span>
                  <span style={runFlowStepChip(runCampaignStep === "result")}>{text.runCampaignStepResult}</span>
                </div>

                {runCampaignStep === "campaign" ? (
                  <div>
                    <p style={{ ...hintStyle, marginBottom: "0.55rem" }}>{text.campaignPickerHint}</p>
                    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(220px,1fr))", gap: "0.55rem", marginBottom: "0.6rem" }}>
                      <input
                        className="ia-form-input"
                        placeholder={text.searchCampaigns}
                        value={campaignSearch}
                        onChange={(e) => setCampaignSearch(e.target.value)}
                      />
                      <select className="ia-form-input" value={campaignChannel} onChange={(e) => setCampaignChannel(e.target.value)}>
                        <option value="all">{text.all}</option>
                        <option value="email">Email</option>
                        <option value="whatsapp">WhatsApp</option>
                      </select>
                      <select className="ia-form-input" value={campaignStatus} onChange={(e) => setCampaignStatus(e.target.value)}>
                        <option value="all">{text.all}</option>
                        <option value="draft">{text.draft}</option>
                        <option value="active">Active</option>
                        <option value="sent">Sent</option>
                        <option value="paused">Paused</option>
                      </select>
                    </div>
                    <div style={{ display: "flex", flexDirection: "column", gap: "0.45rem", maxHeight: 420, overflowY: "auto" }}>
                      {campaigns.length === 0 ? <p style={hintStyle}>{text.noCampaigns}</p> : null}
                      {campaigns.map((campaign) => {
                        const metrics = getCampaignSummaryMetrics(campaign);
                        return (
                          <button
                            type="button"
                            key={`run-campaign-${campaign.id}`}
                            onClick={() => pickCampaign(campaign.id)}
                            style={{ ...campaignBtnStyle, ...(selectedCampaignId === campaign.id ? campaignBtnActiveStyle : {}), textAlign: "left" }}
                          >
                            <div style={rowBetweenStyle}>
                              <strong>{campaign.name}</strong>
                              <span style={badgeStyle}>{campaign.channel}</span>
                            </div>
                            <small style={smallStyle}>{campaign.status}{campaign.subject ? ` · ${campaign.subject}` : ""}</small>
                            <div style={{ marginTop: "0.35rem", display: "flex", gap: "0.35rem", flexWrap: "wrap" }}>
                              <span style={badgeStyle}>{text.campaignMetricsSent}: {metrics.sent}</span>
                              <span style={badgeStyle}>{text.campaignMetricsResponses}: {metrics.responses}</span>
                              <span style={badgeStyle}>{text.campaignMetricsOptOut}: {metrics.optOut}</span>
                            </div>
                          </button>
                        );
                      })}
                    </div>
                  </div>
                ) : null}

                {runCampaignStep === "recipients" ? (
                  <div>
                    <div style={{ display: "flex", gap: "0.45rem", flexWrap: "wrap", marginBottom: "0.55rem" }}>
                      <span style={badgeStyle}>Clients: {audienceCounts.clients || 0}</span>
                      <span style={badgeStyle}>Leads: {audienceCounts.leads || 0}</span>
                      {selectedCampaignChannel ? (
                        <span style={badgeStyle}>
                          {selectedCampaignChannel === "email" ? text.channelRuleEmail : text.channelRuleWhatsapp}
                        </span>
                      ) : null}
                    </div>

                    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(220px,1fr))", gap: "0.55rem", marginBottom: "0.55rem" }}>
                      <input
                        className="ia-form-input"
                        placeholder={text.searchAudience}
                        value={audienceSearch}
                        onChange={(e) => setAudienceSearch(e.target.value)}
                      />
                      <select className="ia-form-input" value={audienceSegment} onChange={(e) => setAudienceSegment(e.target.value)}>
                        <option value="all">{text.all}</option>
                        <option value="clients">Clients / Clientes</option>
                        <option value="leads">Leads</option>
                      </select>
                      <select className="ia-form-input" value={audienceInterest} onChange={(e) => setAudienceInterest(e.target.value)}>
                        <option value="all">{text.interestFilter}: {text.allInterest}</option>
                        <option value="unknown">{text.noResponse}</option>
                        <option value="interested">{text.interested}</option>
                        <option value="not_interested">{text.notInterested}</option>
                        <option value="opt_out">{text.optOutStatus}</option>
                      </select>
                    </div>

                    <div style={{ ...itemCardStyle, marginBottom: "0.55rem", background: "#fff" }}>
                      <div style={rowBetweenStyle}>
                        <div>
                          <strong style={panelTitleStyle}>{text.campaignCountFiltersTitle}</strong>
                          <p style={{ ...hintStyle, marginTop: "0.2rem", marginBottom: 0 }}>{text.campaignCountFiltersHelp}</p>
                        </div>
                        <button
                          type="button"
                          className="ia-button ia-button-ghost"
                          style={{ padding: "0.28rem 0.5rem", fontSize: "0.76rem", whiteSpace: "nowrap" }}
                          onClick={() => {
                            setAudienceEmailCountFilter("");
                            setAudienceWhatsappCountFilter("");
                          }}
                          disabled={busy && audienceEmailCountFilter === "" && audienceWhatsappCountFilter === ""}
                        >
                          {text.clearCountFilters}
                        </button>
                      </div>
                      <div style={{ marginTop: "0.45rem", display: "flex", gap: "0.35rem", flexWrap: "wrap" }}>
                        <span style={badgeStyle}>
                          {text.emailCampaignsFilter}: {audienceEmailCountFilter === "" ? text.all : audienceEmailCountFilter}
                        </span>
                        <span style={badgeStyle}>
                          {text.whatsappCampaignsFilter}: {audienceWhatsappCountFilter === "" ? text.all : audienceWhatsappCountFilter}
                        </span>
                      </div>
                      <div style={{ display: "flex", gap: "0.55rem", flexWrap: "wrap", marginTop: "0.55rem" }}>
                        <label style={{ display: "flex", flexDirection: "column", gap: "0.25rem", width: "100%", maxWidth: 220 }}>
                          <span style={{ ...smallStyle, color: "#0f172a", fontWeight: 700 }}>{text.emailCampaignsFilter}</span>
                          <select
                            className="ia-form-input"
                            style={{ minHeight: 36, padding: "0.38rem 0.65rem", fontSize: "0.86rem" }}
                            value={audienceEmailCountFilter}
                            onChange={(e) => setAudienceEmailCountFilter(e.target.value)}
                          >
                            <option value="">{text.countFilterPlaceholder}</option>
                            {emailCampaignCountOptions.map((count) => (
                              <option key={`email-count-${count}`} value={String(count)}>
                                {count}
                              </option>
                            ))}
                          </select>
                        </label>
                        <label style={{ display: "flex", flexDirection: "column", gap: "0.25rem", width: "100%", maxWidth: 220 }}>
                          <span style={{ ...smallStyle, color: "#0f172a", fontWeight: 700 }}>{text.whatsappCampaignsFilter}</span>
                          <select
                            className="ia-form-input"
                            style={{ minHeight: 36, padding: "0.38rem 0.65rem", fontSize: "0.86rem" }}
                            value={audienceWhatsappCountFilter}
                            onChange={(e) => setAudienceWhatsappCountFilter(e.target.value)}
                          >
                            <option value="">{text.countFilterPlaceholder}</option>
                            {whatsappCampaignCountOptions.map((count) => (
                              <option key={`whatsapp-count-${count}`} value={String(count)}>
                                {count}
                              </option>
                            ))}
                          </select>
                        </label>
                      </div>
                    </div>

                    <div style={{ display: "flex", gap: "0.35rem", flexWrap: "wrap", marginBottom: "0.55rem" }}>
                      <button type="button" className="ia-button ia-button-ghost" style={{ padding: "0.28rem 0.5rem", fontSize: "0.76rem" }} onClick={selectVisibleAudience} disabled={busy || filteredAudience.length === 0}>
                        {text.selectVisible}
                      </button>
                      <button type="button" className="ia-button ia-button-ghost" style={{ padding: "0.28rem 0.5rem", fontSize: "0.76rem" }} onClick={() => selectAudienceBySegment("clients")} disabled={busy}>
                        {text.selectAllClients}
                      </button>
                      <button type="button" className="ia-button ia-button-ghost" style={{ padding: "0.28rem 0.5rem", fontSize: "0.76rem" }} onClick={() => selectAudienceBySegment("leads")} disabled={busy}>
                        {text.selectAllLeads}
                      </button>
                      <button type="button" className="ia-button ia-button-ghost" style={{ padding: "0.28rem 0.5rem", fontSize: "0.76rem" }} onClick={clearRecipientSelection} disabled={busy || selectedRecipientKeys.length === 0}>
                        {text.clearSelection}
                      </button>
                    </div>

                    <div style={{ display: "grid", gridTemplateColumns: "minmax(320px, 1.35fr) minmax(280px, 1fr)", gap: "0.7rem" }}>
                      <div style={{ display: "flex", flexDirection: "column", gap: "0.45rem", maxHeight: 420, overflowY: "auto" }}>
                        {!loading && filteredAudience.length === 0 ? <p style={hintStyle}>{text.noAudience}</p> : null}
                        {filteredAudience.map((row) => {
                          const isSelected = Boolean(selectedRecipients[row.recipient_key]);
                          const blocked = isRecipientBlocked(row);
                          const canSelect = !blocked && isRecipientCompatible(row);
                          const incompatibleReason = blocked ? text.optedOutCannotSelect : getIncompatibleReason(row);
                          return (
                            <div key={row.recipient_key} style={{ ...itemCardStyle, opacity: canSelect ? 1 : 0.6 }}>
                              <div style={rowBetweenStyle}>
                                <label style={{ display: "flex", alignItems: "center", gap: "0.45rem", flex: 1 }}>
                                  <input type="checkbox" checked={isSelected} disabled={!canSelect} onChange={() => toggleRecipientSelection(row)} />
                                  <strong>{row.recipient_name || row.email || row.phone || row.recipient_key}</strong>
                                </label>
                                <div style={{ display: "flex", gap: "0.3rem", flexWrap: "wrap", justifyContent: "flex-end" }}>
                                  <span style={segmentChip(row.segment)}>{row.label_en} / {row.label_es}</span>
                                  <span style={interestStatusChip(getAudienceCommercialStatus(row))}>
                                    {getAudienceCommercialStatusLabel(row)}
                                  </span>
                                </div>
                              </div>
                              <small style={smallStyle}>{row.email || ""} {row.phone ? ` · ${row.phone}` : ""}</small>
                              <div style={{ marginTop: "0.28rem", display: "flex", gap: "0.35rem", flexWrap: "wrap" }}>
                                <span style={badgeStyle}>{text.emailCampaignsSentCount}: {Number(row.email_campaigns_sent_count || 0)}</span>
                                <span style={badgeStyle}>{text.whatsappCampaignsSentCount}: {Number(row.whatsapp_campaigns_sent_count || 0)}</span>
                              </div>
                              {!canSelect && incompatibleReason ? (
                                <div style={{ marginTop: "0.28rem" }}>
                                  <span style={{ ...badgeStyle, background: "#fff7ed", color: "#9a3412", borderColor: "#fed7aa" }}>{incompatibleReason}</span>
                                </div>
                              ) : null}
                            </div>
                          );
                        })}
                      </div>

                      <div style={{ border: "1px solid #E5E7EB", borderRadius: 10, background: "#f8fafc", padding: "0.6rem", maxHeight: 420, overflowY: "auto" }}>
                        <div style={rowBetweenStyle}>
                          <strong>{text.selected}</strong>
                          <span style={badgeStyle}>{text.selectedCount}: {selectedRecipientKeys.length}</span>
                        </div>
                        <div style={{ marginTop: "0.45rem", display: "flex", gap: "0.35rem", flexWrap: "wrap" }}>
                          <span style={badgeStyle}>{text.selectedForSend}: {sendableSelectedRecipients.length}</span>
                          <span style={badgeStyle}>{text.excludedByChannel}: {excludedByChannelCount}</span>
                        </div>
                        <div style={{ marginTop: "0.55rem", display: "flex", flexDirection: "column", gap: "0.45rem" }}>
                          {sendableSelectedRecipients.map((row) => (
                            <div key={row.recipient_key} style={{ ...itemCardStyle, background: "#ffffff" }}>
                              <div style={rowBetweenStyle}>
                                <strong>{row.recipient_name || row.email || row.phone || row.recipient_key}</strong>
                                <button type="button" className="ia-button ia-button-ghost" style={{ padding: "0.22rem 0.45rem", fontSize: "0.72rem" }} onClick={() => removeRecipientFromSelection(row.recipient_key)}>
                                  {text.remove}
                                </button>
                              </div>
                              <small style={smallStyle}>{row.email || ""} {row.phone ? ` · ${row.phone}` : ""}</small>
                              <div style={{ marginTop: "0.28rem", display: "flex", gap: "0.35rem", flexWrap: "wrap" }}>
                                <span style={badgeStyle}>{text.emailCampaignsSentCount}: {Number(row.email_campaigns_sent_count || 0)}</span>
                                <span style={badgeStyle}>{text.whatsappCampaignsSentCount}: {Number(row.whatsapp_campaigns_sent_count || 0)}</span>
                              </div>
                            </div>
                          ))}
                          {sendableSelectedRecipients.length === 0 ? <p style={hintStyle}>{text.selectedNone}</p> : null}
                        </div>
                      </div>
                    </div>
                  </div>
                ) : null}

                {runCampaignStep === "preview" && selectedCampaign ? (
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(280px,1fr))", gap: "0.7rem" }}>
                    <div style={{ ...itemCardStyle, background: "#fff" }}>
                      <strong style={panelTitleStyle}>{text.previewContent}</strong>
                      <div style={{ marginTop: "0.55rem", border: "1px solid #E5E7EB", borderRadius: 10, padding: "0.65rem", background: "#ffffff" }}>
                        <div style={{ ...rowBetweenStyle, marginBottom: "0.4rem" }}>
                          <strong>{selectedCampaign.name}</strong>
                          <span style={badgeStyle}>{selectedCampaign.channel}</span>
                        </div>
                        {selectedCampaign.channel === "email" ? (
                          <small style={{ ...smallStyle, display: "block", marginBottom: "0.4rem" }}>
                            {selectedCampaign.subject || selectedCampaign.name}
                          </small>
                        ) : null}
                        <div style={{ whiteSpace: "pre-wrap", color: "#0f172a", fontSize: "0.9rem", lineHeight: 1.45 }}>
                          {selectedCampaign.body || ""}
                        </div>
                        {selectedCampaign.image_url ? (
                          <img
                            src={selectedCampaign.image_url}
                            alt="campaign"
                            style={{ width: "100%", maxHeight: "44vh", objectFit: "contain", borderRadius: 10, marginTop: "0.55rem", border: "1px solid #E5E7EB", background: "#f8fafc" }}
                          />
                        ) : null}
                        {selectedCampaignCtaUrl ? (
                          <a
                            href={selectedCampaignCtaUrl}
                            target="_blank"
                            rel="noreferrer"
                            style={{ display: "inline-block", marginTop: "0.55rem", padding: "0.45rem 0.7rem", borderRadius: 8, background: "#1d4ed8", color: "#fff", textDecoration: "none", fontSize: "0.82rem" }}
                          >
                            {selectedCampaign.cta_label || (isEs ? "Abrir sitio" : "Open site")}
                          </a>
                        ) : null}
                      </div>
                    </div>

                    <div style={{ ...itemCardStyle, background: "#fff" }}>
                      <strong style={panelTitleStyle}>{text.previewAudience}</strong>
                      <div style={{ marginTop: "0.5rem", display: "flex", gap: "0.4rem", flexWrap: "wrap" }}>
                        <span style={badgeStyle}>{text.selectedForSend}: {sendableSelectedRecipients.length}</span>
                      </div>
                      <div style={{ marginTop: "0.55rem", display: "flex", flexDirection: "column", gap: "0.45rem", maxHeight: 280, overflowY: "auto" }}>
                        {sendableSelectedRecipients.map((row) => (
                          <div key={`preview-${row.recipient_key}`} style={{ ...itemCardStyle, background: "#f8fafc" }}>
                            <div style={rowBetweenStyle}>
                              <strong>{row.recipient_name || row.email || row.phone || row.recipient_key}</strong>
                              <span style={segmentChip(row.segment)}>{row.label_en}</span>
                            </div>
                            <small style={smallStyle}>{row.email || ""} {row.phone ? ` · ${row.phone}` : ""}</small>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                ) : null}

                {runCampaignStep === "result" ? (
                  <div style={{ ...itemCardStyle, background: "#fff" }}>
                    <strong style={panelTitleStyle}>{text.runCampaignStepResultSubtitle}</strong>
                    <p
                      style={{
                        ...hintStyle,
                        marginTop: "0.45rem",
                        color: runCampaignResult?.type === "success" ? "#065f46" : runCampaignResult?.type === "warning" ? "#92400e" : "#b91c1c",
                      }}
                    >
                      {runCampaignResult?.message || text.sendSummaryFailed}
                    </p>
                    <div style={{ marginTop: "0.55rem", display: "flex", gap: "0.45rem", flexWrap: "wrap" }}>
                      <span style={badgeStyle}>{text.sent}: {runCampaignResult?.sent || 0}</span>
                      <span style={badgeStyle}>{text.failed}: {runCampaignResult?.failed || 0}</span>
                      <span style={badgeStyle}>{text.blocked}: {runCampaignResult?.blocked || 0}</span>
                      <span style={badgeStyle}>{text.skipped}: {runCampaignResult?.skipped || 0}</span>
                    </div>
                  </div>
                ) : null}

                <div style={{ ...rowBetweenStyle, marginTop: "0.8rem" }}>
                  <div style={{ display: "flex", gap: "0.35rem", flexWrap: "wrap" }}>
                    {selectedCampaign ? <span style={badgeStyle}>{selectedCampaign.name}</span> : null}
                    {selectedCampaign?.channel ? <span style={badgeStyle}>{selectedCampaign.channel}</span> : null}
                    {runCampaignStep !== "campaign" ? <span style={badgeStyle}>{text.selectedForSend}: {sendableSelectedRecipients.length}</span> : null}
                  </div>
                  <div style={{ display: "flex", gap: "0.45rem", flexWrap: "wrap", justifyContent: "flex-end" }}>
                    {runCampaignStep === "campaign" ? (
                      <button type="button" className="ia-button ia-button-warning" disabled={busy || !selectedCampaign} onClick={continueToRecipients}>
                        {text.next}
                      </button>
                    ) : null}
                    {runCampaignStep === "recipients" ? (
                      <>
                        <button type="button" className="ia-button ia-button-ghost" disabled={busy} onClick={() => setRunCampaignStep("campaign")}>
                          {text.back}
                        </button>
                        <button type="button" className="ia-button ia-button-warning" disabled={busy || sendableSelectedRecipients.length === 0} onClick={continueToPreview}>
                          {text.next}
                        </button>
                      </>
                    ) : null}
                    {runCampaignStep === "preview" ? (
                      <>
                        <button type="button" className="ia-button ia-button-ghost" disabled={busy} onClick={() => setRunCampaignStep("recipients")}>
                          {text.back}
                        </button>
                        <button type="button" className="ia-button ia-button-warning" disabled={busy || sendableSelectedRecipients.length === 0} onClick={confirmRunCampaign}>
                          {busy ? text.sending : text.confirmRunCampaign}
                        </button>
                      </>
                    ) : null}
                    {runCampaignStep === "result" ? (
                      <button type="button" className="ia-button ia-button-warning" onClick={closeRunCampaignModal}>
                        {text.finish}
                      </button>
                    ) : null}
                  </div>
                </div>
              </div>
            </div>
          ) : null}
        </section>
      </div>
    </div>
  );
}

const panelStyle = {
  border: "1px solid #E5E7EB",
  borderRadius: 12,
  background: "#ffffff",
  padding: "0.8rem",
};

const panelTitleStyle = {
  color: "#274472",
  fontSize: "0.95rem",
};

const rowBetweenStyle = {
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  gap: "0.55rem",
};

const hintStyle = {
  color: "#667085",
  fontSize: "0.88rem",
};

const itemCardStyle = {
  border: "1px solid #E5E7EB",
  borderRadius: 10,
  background: "#FAFAFA",
  padding: "0.55rem",
};

const badgeStyle = {
  border: "1px solid #E5E7EB",
  borderRadius: 999,
  padding: "0.18rem 0.5rem",
  fontSize: "0.77rem",
  color: "#334155",
  background: "#f8fafc",
};

const smallStyle = {
  color: "#6b7280",
  fontSize: "0.77rem",
};

const campaignBtnStyle = {
  border: "1px solid #E5E7EB",
  borderRadius: 10,
  background: "#fff",
  padding: "0.55rem",
  display: "flex",
  flexDirection: "column",
  alignItems: "flex-start",
  gap: "0.2rem",
  cursor: "pointer",
};

const campaignBtnActiveStyle = {
  border: "1px solid #274472",
  boxShadow: "0 0 0 1px rgba(39,68,114,0.15)",
};

const runFlowStepChip = (active) => ({
  ...badgeStyle,
  background: active ? "#facc15" : "#f8fafc",
  color: active ? "#713f12" : "#475569",
  borderColor: active ? "#eab308" : "#e2e8f0",
  fontWeight: active ? 700 : 500,
});

const modalOverlayStyle = {
  position: "fixed",
  inset: 0,
  zIndex: 1200,
  background: "rgba(15,23,42,0.45)",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  padding: "1rem",
};

const modalCardStyle = {
  width: "min(1100px, 100%)",
  maxHeight: "92vh",
  overflowY: "auto",
  borderRadius: 14,
  border: "1px solid #E5E7EB",
  background: "#ffffff",
  padding: "0.9rem",
  boxShadow: "0 30px 80px rgba(15,23,42,0.24)",
};

const segmentChip = (segment) => {
  const key = String(segment || "").toLowerCase();
  if (key === "clients") return { ...badgeStyle, background: "#ecfdf3", color: "#047857", borderColor: "#bbf7d0" };
  if (key === "leads") return { ...badgeStyle, background: "#eff6ff", color: "#1d4ed8", borderColor: "#bfdbfe" };
  return { ...badgeStyle, background: "#fff7ed", color: "#c2410c", borderColor: "#fed7aa" };
};

const sendStatusChip = (status) => {
  const key = String(status || "pending").toLowerCase();
  if (key === "sent") return { ...badgeStyle, background: "#ecfdf3", color: "#047857", borderColor: "#bbf7d0" };
  if (key === "blocked_policy") return { ...badgeStyle, background: "#fff7ed", color: "#c2410c", borderColor: "#fed7aa" };
  if (key === "failed") return { ...badgeStyle, background: "#fef2f2", color: "#b91c1c", borderColor: "#fecaca" };
  return { ...badgeStyle, background: "#f8fafc", color: "#334155", borderColor: "#e2e8f0" };
};

const interestStatusChip = (status) => {
  const key = String(status || "unknown").toLowerCase();
  if (key === "interested") return { ...badgeStyle, background: "#ecfdf3", color: "#047857", borderColor: "#bbf7d0" };
  if (key === "not_interested") return { ...badgeStyle, background: "#fff7ed", color: "#9a6700", borderColor: "#fed7aa" };
  if (key === "opt_out") return { ...badgeStyle, background: "#fff1f2", color: "#be123c", borderColor: "#fecaca" };
  return { ...badgeStyle, background: "#f8fafc", color: "#475569", borderColor: "#e2e8f0" };
};
