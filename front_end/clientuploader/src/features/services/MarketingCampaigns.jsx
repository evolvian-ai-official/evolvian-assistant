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
    createNewCampaign: isEs ? "Nueva campaña" : "New campaign",
    campaigns: isEs ? "Campañas" : "Campaigns",
    audience: isEs ? "Audiencia" : "Audience",
    filters: isEs ? "Filtros" : "Filters",
    all: isEs ? "Todos" : "All",
    searchAudience: isEs ? "Buscar audiencia" : "Search audience",
    searchCampaigns: isEs ? "Buscar campañas" : "Search campaigns",
    noAudience: isEs ? "Sin audiencia para mostrar." : "No audience to display.",
    noCampaigns: isEs ? "No hay campañas todavía." : "No campaigns yet.",
    history: isEs ? "Historial" : "History",
    recipients: isEs ? "Destinatarios" : "Recipients",
    send: isEs ? "Enviar campaña" : "Send campaign",
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
    openCampaignPicker: isEs ? "Seleccionar campaña" : "Select campaign",
    changeCampaign: isEs ? "Cambiar campaña" : "Change campaign",
    noCampaignSelected: isEs ? "No hay campaña seleccionada." : "No campaign selected.",
    campaignPickerTitle: isEs ? "Seleccionar campaña" : "Select campaign",
    campaignPickerSubtitle: isEs ? "Elige una campaña para envío y seguimiento." : "Choose a campaign for send and tracking.",
    campaignFormCreateTitle: isEs ? "Crear campaña" : "Create campaign",
    campaignFormEditTitle: isEs ? "Editar campaña" : "Edit campaign",
    campaignFormSubtitle: isEs ? "Completa el formulario y guarda tu campaña." : "Complete the form and save your campaign.",
    close: isEs ? "Cerrar" : "Close",
    whatsappNotConnected: isEs
      ? "WhatsApp no está conectado. Conéctalo antes de enviar campañas por WhatsApp."
      : "WhatsApp is not connected. Connect it before sending WhatsApp campaigns.",
    sendSummarySuccess: isEs ? "Campaña enviada correctamente." : "Campaign sent successfully.",
    sendSummaryPartial: isEs ? "Campaña enviada parcialmente." : "Campaign sent partially.",
    sendSummaryFailed: isEs ? "No se pudo enviar la campaña." : "Campaign could not be sent.",
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
      ? "Botón opcional de URL (https://...) usando el CTA."
      : "Optional URL button (https://...) using the CTA fields.",
    whatsappFormatLine3: isEs
      ? "Imagen opcional como header (solo URL pública https://...)."
      : "Optional image header (public https://... URL only).",
    whatsappFormatLine4: isEs
      ? "No uses {1} ni {{1}} en tu texto: el sistema lo agrega automáticamente."
      : "Do not use {1} or {{1}} in your text: the system injects it automatically.",
    whatsappFormatLine5: isEs
      ? "Plantilla final enviada a Meta: Hola, {{1}}, Gracias."
      : "Final template sent to Meta: Hello, {{1}}, Thank you.",
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

  const [campaignSearch, setCampaignSearch] = useState("");
  const [campaignChannel, setCampaignChannel] = useState("all");
  const [campaignStatus, setCampaignStatus] = useState("all");

  const [selectedCampaignId, setSelectedCampaignId] = useState("");
  const [selectedCampaignDetail, setSelectedCampaignDetail] = useState(null);

  const [selectedRecipientKey, setSelectedRecipientKey] = useState("");
  const [recipientHistory, setRecipientHistory] = useState([]);
  const [selectedRecipients, setSelectedRecipients] = useState({});
  const [previewOpen, setPreviewOpen] = useState(false);
  const [contentPreviewOpen, setContentPreviewOpen] = useState(false);
  const [campaignPickerOpen, setCampaignPickerOpen] = useState(false);
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
    if (!selectedCampaignId && items[0]?.id) {
      setSelectedCampaignId(items[0].id);
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
  const getPolicyReasonForChannel = (row, channel = selectedCampaignChannel) => {
    if (!row) return "";
    if (channel === "email") return String(row?.policy_reason_email || "");
    if (channel === "whatsapp") return String(row?.policy_reason_whatsapp || "");
    return String(row?.policy_reason_email || row?.policy_reason_whatsapp || "");
  };
  const getConsentPolicyHelp = (reason) => {
    const normalized = String(reason || "").trim().toLowerCase();
    if (normalized === "missing_or_expired_marketing_consent") return text.consentReasonMissingExpired;
    if (normalized === "email_marketing_not_opted_in") return text.consentReasonNotOptedIn;
    if (normalized === "missing_terms_acceptance_for_marketing") return text.consentReasonMissingTerms;
    if (normalized === "missing_email_in_consent_record") return text.consentReasonMissingEmailInConsent;
    if (normalized === "missing_phone_in_consent_record") return text.consentReasonMissingPhoneInConsent;
    return "";
  };
  const getConsentPolicyBadgeLabel = (reason) => {
    const normalized = String(reason || "").trim().toLowerCase();
    if (normalized === "missing_or_expired_marketing_consent") return text.consentMissingExpiredBadge;
    return text.consentIssueBadge;
  };
  const hasConsentPolicyWarning = (row, channel = selectedCampaignChannel) => {
    const reason = getPolicyReasonForChannel(row, channel);
    return [
      "missing_or_expired_marketing_consent",
      "email_marketing_not_opted_in",
      "missing_terms_acceptance_for_marketing",
      "missing_email_in_consent_record",
      "missing_phone_in_consent_record",
    ].includes(String(reason || "").toLowerCase());
  };

  const selectedRecipientKeys = useMemo(() => Object.keys(selectedRecipients), [selectedRecipients]);
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
    addRecipientsToSelection(audience.filter((row) => !isRecipientBlocked(row) && isRecipientCompatible(row)));

  const selectAudienceBySegment = async (segment) => {
    if (!clientId) return;
    setBusy(true);
    setError("");
    try {
      const result = await fetchAudience({ segment, q: "" });
      addRecipientsToSelection(result.items.filter((row) => !isRecipientBlocked(row) && isRecipientCompatible(row)));
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

      if (isEditing && String(form.channel || "").toLowerCase() === "whatsapp") {
        setNotice({ type: "warning", message: text.whatsappEditVersions });
      } else if (isEditing) {
        setNotice({ type: "success", message: isEs ? "Campaña actualizada." : "Campaign updated." });
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

  const openSendPreview = async () => {
    if (!clientId) return;
    if (!selectedCampaign?.id) {
      setError(text.selectCampaignFirst);
      return;
    }
    if (selectedCampaignChannel === "whatsapp") {
      const isConnected = await checkWhatsAppConnection();
      if (!isConnected) {
        setError(text.whatsappNotConnected);
        setNotice(null);
        return;
      }
    }
    if (selectedRecipientsList.length === 0) {
      setError(text.requiredRecipientSelection);
      return;
    }
    if (sendableSelectedRecipients.length === 0) {
      setError(text.noSendableRecipients);
      return;
    }
    setError("");
    setNotice(null);
    setPreviewOpen(true);
  };

  const openCampaignPicker = async () => {
    setCampaignPickerOpen(true);
    try {
      await loadCampaigns();
    } catch (err) {
      setError(err?.message || "Unexpected error");
    }
  };

  const pickCampaign = (campaignId) => {
    setSelectedCampaignId(campaignId);
    setCampaignPickerOpen(false);
  };

  const confirmSendCampaign = async () => {
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

      const messageCounts = `${text.sent}: ${sent} · ${text.failed}: ${failed} · ${text.blocked}: ${blocked} · ${text.skipped}: ${skipped}`;
      if (sent > 0 && failed === 0 && blocked === 0) {
        setNotice({ type: "success", message: `${text.sendSummarySuccess} ${messageCounts}` });
      } else if (sent > 0) {
        setNotice({ type: "warning", message: `${text.sendSummaryPartial} ${messageCounts}` });
      } else {
        setError(`${text.sendSummaryFailed} ${messageCounts}`);
      }

      await refreshAll();
      await loadCampaignDetail(selectedCampaign.id);
      setPreviewOpen(false);
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

          <div style={{ display: "flex", justifyContent: "flex-end", marginTop: "0.9rem" }}>
            <button type="button" className="ia-button ia-button-primary" onClick={openCreateCampaignModal} disabled={busy}>
              {text.createNewCampaign}
            </button>
          </div>

          <div style={{ ...panelStyle, marginTop: "0.9rem" }}>
            <div style={rowBetweenStyle}>
              <strong style={panelTitleStyle}>{text.audience}</strong>
              <button type="button" className="ia-button ia-button-ghost" onClick={refreshAll} disabled={busy || loading}>
                {text.refresh}
              </button>
            </div>

            <div style={{ display: "flex", gap: "0.45rem", flexWrap: "wrap", marginBottom: "0.55rem" }}>
              <span style={badgeStyle}>Clients: {audienceCounts.clients || 0}</span>
              <span style={badgeStyle}>Leads: {audienceCounts.leads || 0}</span>
            </div>

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

            <div style={{ display: "flex", gap: "0.35rem", flexWrap: "wrap", marginBottom: "0.45rem" }}>
              <button
                type="button"
                className="ia-button ia-button-ghost"
                style={{ padding: "0.28rem 0.5rem", fontSize: "0.76rem" }}
                onClick={selectVisibleAudience}
                disabled={busy || audience.length === 0}
              >
                {text.selectVisible}
              </button>
              <button
                type="button"
                className="ia-button ia-button-ghost"
                style={{ padding: "0.28rem 0.5rem", fontSize: "0.76rem" }}
                onClick={() => selectAudienceBySegment("clients")}
                disabled={busy}
              >
                {text.selectAllClients}
              </button>
              <button
                type="button"
                className="ia-button ia-button-ghost"
                style={{ padding: "0.28rem 0.5rem", fontSize: "0.76rem" }}
                onClick={() => selectAudienceBySegment("leads")}
                disabled={busy}
              >
                {text.selectAllLeads}
              </button>
              <button
                type="button"
                className="ia-button ia-button-ghost"
                style={{ padding: "0.28rem 0.5rem", fontSize: "0.76rem" }}
                onClick={() => selectAudienceBySegment("all")}
                disabled={busy}
              >
                {text.selectAllAudience}
              </button>
              <button
                type="button"
                className="ia-button ia-button-ghost"
                style={{ padding: "0.28rem 0.5rem", fontSize: "0.76rem" }}
                onClick={clearRecipientSelection}
                disabled={busy || selectedRecipientKeys.length === 0}
              >
                {text.clearSelection}
              </button>
            </div>

            {selectedCampaignChannel ? (
              <div style={{ ...itemCardStyle, marginBottom: "0.45rem", background: "#f8fafc" }}>
                <small style={smallStyle}>
                  {selectedCampaignChannel === "email" ? text.channelRuleEmail : text.channelRuleWhatsapp}
                </small>
                <div style={{ marginTop: "0.3rem", display: "flex", gap: "0.35rem", flexWrap: "wrap" }}>
                  <span style={badgeStyle}>
                    {text.selectedForSend}: {sendableSelectedRecipients.length}
                  </span>
                  <span style={badgeStyle}>
                    {text.excludedByChannel}: {excludedByChannelCount}
                  </span>
                </div>
              </div>
            ) : null}

            {loading ? <p style={hintStyle}>{text.loading}</p> : null}

            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(280px,1fr))", gap: "0.6rem" }}>
              <div style={{ display: "flex", flexDirection: "column", gap: "0.45rem", maxHeight: 330, overflowY: "auto" }}>
                {!loading && audience.length === 0 ? <p style={hintStyle}>{text.noAudience}</p> : null}
                {audience.map((row) => {
                  const isSelected = Boolean(selectedRecipients[row.recipient_key]);
                  const blocked = isRecipientBlocked(row);
                  const canSelect = !blocked && isRecipientCompatible(row);
                  const incompatibleReason = blocked ? text.optedOutCannotSelect : getIncompatibleReason(row);
                  const consentWarning = hasConsentPolicyWarning(row);
                  const policyReason = getPolicyReasonForChannel(row);
                  const consentWarningHelp = getConsentPolicyHelp(policyReason);
                  return (
                    <div key={row.recipient_key} style={{ ...itemCardStyle, opacity: canSelect ? 1 : 0.6 }}>
                      <div style={rowBetweenStyle}>
                        <label style={{ display: "flex", alignItems: "center", gap: "0.45rem", flex: 1 }}>
                          <input
                            type="checkbox"
                            checked={isSelected}
                            disabled={!canSelect}
                            onChange={() => toggleRecipientSelection(row)}
                          />
                          <strong>{row.recipient_name || row.email || row.phone || row.recipient_key}</strong>
                        </label>
                        <div style={{ display: "flex", gap: "0.3rem", flexWrap: "wrap", justifyContent: "flex-end" }}>
                          <span style={segmentChip(row.segment)}>{row.label_en} / {row.label_es}</span>
                          {blocked ? (
                            <span style={{ ...badgeStyle, background: "#fef2f2", color: "#b91c1c", borderColor: "#fecaca" }}>
                              {row.opt_out_label_en || text.optedOut} / {row.opt_out_label_es || text.optedOut}
                            </span>
                          ) : null}
                          {consentWarning ? (
                            <span
                              title={`${text.consentBadgeTitle}: ${consentWarningHelp}`}
                              style={{ ...badgeStyle, background: "#fff7ed", color: "#9a3412", borderColor: "#fed7aa" }}
                            >
                              {getConsentPolicyBadgeLabel(policyReason)}
                            </span>
                          ) : null}
                        </div>
                      </div>
                      <small style={smallStyle}>{row.email || ""} {row.phone ? ` · ${row.phone}` : ""}</small>
                      {consentWarning && consentWarningHelp ? (
                        <div style={{ marginTop: "0.28rem" }}>
                          <span style={{ ...badgeStyle, background: "#fff7ed", color: "#9a3412", borderColor: "#fed7aa" }}>
                            {consentWarningHelp}
                          </span>
                        </div>
                      ) : null}
                      {!canSelect && incompatibleReason ? (
                        <div style={{ marginTop: "0.28rem" }}>
                          <span style={{ ...badgeStyle, background: "#fff7ed", color: "#9a3412", borderColor: "#fed7aa" }}>{incompatibleReason}</span>
                        </div>
                      ) : null}
                      <div style={{ marginTop: "0.4rem", display: "flex", gap: "0.35rem", flexWrap: "wrap" }}>
                        <button
                          type="button"
                          className="ia-button ia-button-ghost"
                          style={{ padding: "0.28rem 0.5rem", fontSize: "0.76rem" }}
                          onClick={() => setSelectedRecipientKey(row.recipient_key)}
                        >
                          {text.history}
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
              <div style={{ border: "1px solid #E5E7EB", borderRadius: 10, background: "#f8fafc", padding: "0.55rem", maxHeight: 330, overflowY: "auto" }}>
                <div style={rowBetweenStyle}>
                  <strong>{text.selected}</strong>
                  <span style={badgeStyle}>{text.selectedCount}: {selectedRecipientKeys.length}</span>
                </div>
                <div style={{ marginTop: "0.5rem", display: "flex", flexDirection: "column", gap: "0.45rem" }}>
                  {sendableSelectedRecipients.map((row) => (
                    <div key={row.recipient_key} style={{ ...itemCardStyle, background: "#ffffff" }}>
                      <div style={rowBetweenStyle}>
                        <strong>{row.recipient_name || row.email || row.phone || row.recipient_key}</strong>
                        <button
                          type="button"
                          className="ia-button ia-button-ghost"
                          style={{ padding: "0.22rem 0.45rem", fontSize: "0.72rem" }}
                          onClick={() => removeRecipientFromSelection(row.recipient_key)}
                        >
                          {text.remove}
                        </button>
                      </div>
                      <small style={smallStyle}>{row.email || ""} {row.phone ? ` · ${row.phone}` : ""}</small>
                    </div>
                  ))}
                  {sendableSelectedRecipients.length === 0 ? <p style={hintStyle}>{text.selectedNone}</p> : null}
                </div>
              </div>
            </div>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(280px,1fr))", gap: "0.9rem", marginTop: "0.9rem" }}>
            <div style={panelStyle}>
              <div style={rowBetweenStyle}>
                <strong style={panelTitleStyle}>{text.campaigns}</strong>
                <div style={{ display: "flex", gap: "0.45rem", flexWrap: "wrap", justifyContent: "flex-end" }}>
                  <button type="button" className="ia-button ia-button-ghost" onClick={openCampaignPicker} disabled={busy || loading}>
                    {selectedCampaign ? text.changeCampaign : text.openCampaignPicker}
                  </button>
                  <button
                    type="button"
                    className="ia-button ia-button-warning"
                    disabled={busy || !selectedCampaign || (selectedCampaignChannel === "whatsapp" && !whatsAppMetaConnected)}
                    onClick={openSendPreview}
                  >
                    {busy ? text.sending : text.send}
                  </button>
                </div>
              </div>

              {!selectedCampaign ? <p style={{ ...hintStyle, marginTop: "0.7rem" }}>{text.noCampaignSelected}</p> : null}
              {selectedCampaignChannel === "whatsapp" && !whatsAppMetaConnected ? (
                <p style={{ ...hintStyle, marginTop: "0.7rem", color: "#b45309" }}>{text.whatsappNotConnected}</p>
              ) : null}

              {selectedCampaign ? (
                <div style={{ ...itemCardStyle, marginTop: "0.7rem", background: "#f8fafc" }}>
                  <div style={rowBetweenStyle}>
                    <strong>{selectedCampaign.name}</strong>
                    <span style={badgeStyle}>{selectedCampaign.channel}</span>
                  </div>
                  <small style={smallStyle}>
                    {selectedCampaign.status}
                    {selectedCampaign.subject ? ` · ${selectedCampaign.subject}` : ""}
                  </small>
                  <p style={{ ...smallStyle, marginTop: "0.35rem", color: "#334155", display: "-webkit-box", WebkitLineClamp: 3, WebkitBoxOrient: "vertical", overflow: "hidden" }}>
                    {selectedCampaign.body || ""}
                  </p>
                  <div style={{ marginTop: "0.5rem" }}>
                    <div style={{ display: "flex", gap: "0.35rem", flexWrap: "wrap" }}>
                      <button type="button" className="ia-button ia-button-ghost" onClick={openCampaignPicker} style={{ padding: "0.28rem 0.5rem", fontSize: "0.76rem" }}>
                        {text.openCampaignPicker}
                      </button>
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
                  </div>
                </div>
              ) : null}

              <div style={{ marginTop: "0.65rem", display: "flex", gap: "0.4rem", flexWrap: "wrap" }}>
                <span style={badgeStyle}>{text.campaigns}: {campaigns.length}</span>
                <span style={badgeStyle}>{isEs ? "Seleccionada" : "Selected"}: {selectedCampaign ? 1 : 0}</span>
              </div>
            </div>

            <div style={panelStyle}>
              <strong style={panelTitleStyle}>{text.recipients}</strong>
              {!selectedCampaignDetail ? <p style={hintStyle}>{isEs ? "Selecciona una campaña." : "Select a campaign."}</p> : null}

              {selectedCampaignDetail ? (
                <>
                  <div style={{ marginBottom: "0.6rem" }}>
                    <strong>{selectedCampaignDetail?.campaign?.name}</strong>
                    <small style={smallStyle}> {selectedCampaignDetail?.campaign?.channel} · {selectedCampaignDetail?.campaign?.status}</small>
                  </div>

                  <div style={{ display: "flex", flexDirection: "column", gap: "0.45rem", maxHeight: 310, overflowY: "auto" }}>
                    {(selectedCampaignDetail?.recipients || []).map((row) => (
                      <div key={`${row.campaign_id}-${row.recipient_key}`} style={itemCardStyle}>
                        <div style={rowBetweenStyle}>
                          <strong>{row.recipient_name || row.email || row.phone || row.recipient_key}</strong>
                          <span style={sendStatusChip(row.send_status)}>{row.send_status}</span>
                        </div>
                        <small style={smallStyle}>{row.email || ""} {row.phone ? ` · ${row.phone}` : ""}</small>
                      </div>
                    ))}
                    {(selectedCampaignDetail?.recipients || []).length === 0 ? (
                      <p style={hintStyle}>{isEs ? "Aún no hay destinatarios enviados." : "No recipients sent yet."}</p>
                    ) : null}
                  </div>
                </>
              ) : null}
            </div>
          </div>

          {selectedRecipientKey ? (
            <div style={{ ...panelStyle, marginTop: "0.9rem" }}>
              <div style={rowBetweenStyle}>
                <strong style={panelTitleStyle}>{text.history}</strong>
                <button className="ia-button ia-button-ghost" onClick={() => setSelectedRecipientKey("")}>Close</button>
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: "0.45rem", maxHeight: 220, overflowY: "auto" }}>
                {recipientHistory.map((row, idx) => (
                  <div key={`${row.campaign_id}-${idx}`} style={itemCardStyle}>
                    <div style={rowBetweenStyle}>
                      <strong>{row.campaign_name}</strong>
                      <span style={sendStatusChip(row.send_status)}>{row.send_status}</span>
                    </div>
                    <small style={smallStyle}>{row.campaign_channel} · {row.updated_at || row.sent_at || ""}</small>
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

          {campaignPickerOpen ? (
            <div style={modalOverlayStyle} role="dialog" aria-modal="true">
              <div style={{ ...modalCardStyle, width: "min(900px, 100%)" }}>
                <div style={{ ...rowBetweenStyle, marginBottom: "0.55rem" }}>
                  <div>
                    <strong style={{ fontSize: "1rem", color: "#0f172a" }}>{text.campaignPickerTitle}</strong>
                    <p style={{ ...hintStyle, marginTop: "0.2rem" }}>{text.campaignPickerSubtitle}</p>
                  </div>
                  <button type="button" className="ia-button ia-button-ghost" onClick={() => setCampaignPickerOpen(false)} disabled={busy}>
                    {text.close}
                  </button>
                </div>

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
                  {campaigns.map((campaign) => (
                    <button
                      type="button"
                      key={`picker-${campaign.id}`}
                      onClick={() => pickCampaign(campaign.id)}
                      style={{ ...campaignBtnStyle, ...(selectedCampaignId === campaign.id ? campaignBtnActiveStyle : {}) }}
                    >
                      <div style={rowBetweenStyle}>
                        <strong style={{ textAlign: "left" }}>{campaign.name}</strong>
                        <span style={badgeStyle}>{campaign.channel}</span>
                      </div>
                      <small style={smallStyle}>{campaign.status}{campaign.subject ? ` · ${campaign.subject}` : ""}</small>
                    </button>
                  ))}
                </div>
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
                </div>
              </div>
            </div>
          ) : null}

          {previewOpen && selectedCampaign ? (
            <div style={modalOverlayStyle} role="dialog" aria-modal="true">
              <div style={modalCardStyle}>
                <div style={{ ...rowBetweenStyle, marginBottom: "0.55rem" }}>
                  <div>
                    <strong style={{ fontSize: "1rem", color: "#0f172a" }}>{text.previewTitle}</strong>
                    <p style={{ ...hintStyle, marginTop: "0.2rem" }}>{text.previewSubtitle}</p>
                  </div>
                  <button type="button" className="ia-button ia-button-ghost" onClick={() => setPreviewOpen(false)} disabled={busy}>
                    {text.cancel}
                  </button>
                </div>

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
                      {sendableSelectedRecipients.map((row) => {
                        const previewPolicyReason = getPolicyReasonForChannel(row);
                        const previewConsentWarning = hasConsentPolicyWarning(row);
                        const previewConsentHelp = getConsentPolicyHelp(previewPolicyReason);
                        return (
                          <div key={`preview-${row.recipient_key}`} style={{ ...itemCardStyle, background: "#f8fafc" }}>
                            <div style={rowBetweenStyle}>
                              <strong>{row.recipient_name || row.email || row.phone || row.recipient_key}</strong>
                              <span style={segmentChip(row.segment)}>{row.label_en}</span>
                            </div>
                            <small style={smallStyle}>{row.email || ""} {row.phone ? ` · ${row.phone}` : ""}</small>
                            {previewConsentWarning ? (
                              <div style={{ marginTop: "0.28rem" }}>
                                <span
                                  title={`${text.consentBadgeTitle}: ${previewConsentHelp}`}
                                  style={{ ...badgeStyle, background: "#fff7ed", color: "#9a3412", borderColor: "#fed7aa" }}
                                >
                                  {getConsentPolicyBadgeLabel(previewPolicyReason)}
                                </span>
                              </div>
                            ) : null}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                </div>

                <div style={{ ...rowBetweenStyle, marginTop: "0.8rem" }}>
                  <span style={smallStyle}>{text.selectedForSend}: {sendableSelectedRecipients.length}</span>
                  <button type="button" className="ia-button ia-button-warning" disabled={busy || sendableSelectedRecipients.length === 0} onClick={confirmSendCampaign}>
                    {busy ? text.sending : text.confirmSend}
                  </button>
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
