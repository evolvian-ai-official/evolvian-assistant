import { useEffect, useMemo, useState } from "react";
import { useClientId } from "../../hooks/useClientId";
import { useLanguage } from "../../contexts/LanguageContext";
import { authFetch } from "../../lib/authFetch";
import {
  PHONE_COUNTRY_OPTIONS,
  buildContactMatchKey,
  composeE164Phone,
  inferPhoneCountryCode,
  isValidAppointmentEmail,
  isValidAppointmentPhone,
  normalizeAppointmentEmail,
  normalizeAppointmentName,
  sanitizePhoneLocalInput,
  splitE164Phone,
} from "./appointmentContactUtils";

const API_BASE_URL =
  import.meta.env.VITE_API_URL ||
  (import.meta.env.MODE === "development"
    ? "http://localhost:8001"
    : "https://evolvian-assistant.onrender.com");

export default function AppointmentClients({
  showCampaignHistory = false,
  appointmentsCtaHref = "",
  appointmentsCtaLabel = "",
}) {
  const clientId = useClientId();
  const { t, lang } = useLanguage();
  const isEs = lang === "es";
  const uiLocale = isEs ? "es-MX" : "en-US";
  const ui = {
    title: isEs ? "Clientes" : "Clients",
    subtitle: isEs
      ? "Lista editable de clientes y su histórico de citas en orden cronológico."
      : "Editable client list and appointment history in chronological order.",
    newClient: isEs ? "+ Nuevo cliente" : "+ New client",
    close: isEs ? "Cerrar" : "Close",
    searchPlaceholder: isEs
      ? "Buscar por nombre, email o teléfono"
      : "Search by name, email or phone",
    refresh: isEs ? "Actualizar" : "Refresh",
    createClientTitle: isEs ? "Crear cliente" : "Create client",
    name: isEs ? "Nombre" : "Name",
    email: "Email",
    invalidEmail: isEs ? "Email inválido." : "Invalid email.",
    invalidPhone: isEs ? "Teléfono inválido. Usa prefijo internacional." : "Invalid phone. Use international format.",
    phonePlaceholder: isEs ? "Teléfono (sin prefijo)" : "Phone (without country code)",
    cancel: isEs ? "Cancelar" : "Cancel",
    saveClient: isEs ? "Guardar cliente" : "Save client",
    saveClientFailed: isEs ? "No se pudo guardar el cliente." : "Could not save the client.",
    saving: isEs ? "Guardando..." : "Saving...",
    loadClientsError: isEs ? "No se pudo cargar la lista de clientes." : "Could not load the clients list.",
    directoryMissing503: isEs
      ? "La tabla appointment_clients aún no existe. Puedes ver clientes derivados de citas, pero para crear/editar corre la migración SQL."
      : "The appointment_clients table does not exist yet. You can view clients derived from appointments, but run the SQL migration to create/edit clients.",
    directoryUnavailable: isEs
      ? "Directorio de clients no disponible todavía. Se muestra lista derivada de citas; para editar/crear corre la migración SQL."
      : "Clients directory is not available yet. Showing clients derived from appointments; run the SQL migration to edit/create.",
    noClients: isEs
      ? "No hay clientes todavía. Crea uno nuevo o crea una cita para generar historial."
      : "No clients yet. Create a new one or create an appointment to generate history.",
    clientFallback: isEs ? "Cliente" : "Client",
    appointmentsCount: (count) => `${count} ${isEs ? "cita(s)" : "appointment(s)"}`,
    lastLabel: isEs ? "Última" : "Last",
    derivedFromAppointments: isEs ? "Derivado de Appointments" : "Derived from Appointments",
    hideHistory: isEs ? "Ocultar histórico" : "Hide history",
    viewHistory: isEs ? "Ver histórico" : "View history",
    editTitle: isEs ? "Editar" : "Edit",
    closeEditTitle: isEs ? "Cerrar edición" : "Close edit",
    saveChanges: isEs ? "Guardar cambios" : "Save changes",
    saveInClients: isEs ? "Guardar en Clients" : "Save to Clients",
    saveFailed: isEs ? "No se pudo guardar." : "Could not save.",
    deleteTitle: isEs ? "Eliminar cliente" : "Delete client",
    deleting: isEs ? "Eliminando..." : "Deleting...",
    deleteConfirm: isEs
      ? "¿Seguro que quieres eliminar este cliente del directorio editable?"
      : "Are you sure you want to delete this client from the editable directory?",
    deleteFailed: isEs ? "No se pudo eliminar el cliente." : "Could not delete the client.",
    historyTitle: isEs ? "Histórico (cronológico)" : "History (chronological)",
    internalNotesLabel: isEs ? "Notas internas" : "Internal notes",
    noHistory: isEs ? "Sin citas registradas todavía." : "No appointments recorded yet.",
    campaignsTitle: isEs ? "Campañas enviadas" : "Sent campaigns",
    campaignsLoading: isEs ? "Cargando campañas..." : "Loading campaigns...",
    noCampaignHistory: isEs ? "Sin campañas enviadas para este cliente." : "No sent campaigns for this client.",
    campaignsNeedsContact: isEs
      ? "Este cliente necesita email o teléfono válido para mapear campañas."
      : "This client needs a valid email or phone to map campaigns.",
    campaignsLoadFailed: isEs ? "No se pudo cargar el historial de campañas." : "Could not load campaign history.",
    campaignsUnavailable: isEs
      ? "Marketing Campaigns no está disponible todavía para este cliente."
      : "Marketing Campaigns is not available yet for this client.",
    campaignLabel: isEs ? "Campaña" : "Campaign",
    campaignFilterLabel: isEs ? "Filtrar por campaña" : "Filter by campaign",
    allCampaigns: isEs ? "Todas las campañas" : "All campaigns",
    interestFilterLabel: isEs ? "Filtrar por interés" : "Filter by interest",
    allInterestStatuses: isEs ? "Todos los intereses" : "All interests",
    interestInterested: isEs ? "Interesado" : "Interested",
    interestNotInterested: isEs ? "No interesado" : "Not interested",
    interestUnknown: isEs ? "Sin señal" : "No signal",
    interestOptOut: isEs ? "Opt-out" : "Opt-out",
    channelFilterLabel: isEs ? "Canal" : "Channel",
    allChannels: isEs ? "Todos los canales" : "All channels",
    commercialStatusLabel: isEs ? "Status comercial" : "Commercial status",
    channelEmail: "Email",
    channelWhatsapp: "WhatsApp",
    responseStatusLabel: isEs ? "Respuesta" : "Response",
    responseAtLabel: isEs ? "Respuesta registrada" : "Response at",
    marketingSignalsLoadFailed: isEs
      ? "No se pudieron cargar los estados comerciales y campañas para filtros avanzados."
      : "Could not load commercial states and campaigns for advanced filters.",
    campaignRecipientsLoading: isEs ? "Cargando destinatarios de campaña..." : "Loading campaign recipients...",
    noClientsFiltered: isEs ? "No hay clientes con esos filtros." : "No clients match those filters.",
    sentAtLabel: isEs ? "Enviado" : "Sent at",
    lastUpdateLabel: isEs ? "Actualización" : "Updated",
    lastSignalLabel: isEs ? "Última señal" : "Last signal",
    sendErrorLabel: isEs ? "Error" : "Error",
    goToAppointments: isEs ? "Ir a Appointments" : "Go to Appointments",
  };
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [directoryWarning, setDirectoryWarning] = useState("");
  const [clients, setClients] = useState([]);
  const [appointments, setAppointments] = useState([]);
  const [marketingAudience, setMarketingAudience] = useState([]);
  const [marketingCampaigns, setMarketingCampaigns] = useState([]);
  const [marketingSignalsError, setMarketingSignalsError] = useState("");
  const [search, setSearch] = useState("");
  const [interestFilter, setInterestFilter] = useState("all");
  const [campaignFilter, setCampaignFilter] = useState("all");
  const [channelFilter, setChannelFilter] = useState("all");
  const [campaignRecipientKeys, setCampaignRecipientKeys] = useState(null);
  const [campaignRecipientsLoading, setCampaignRecipientsLoading] = useState(false);
  const [showNewClient, setShowNewClient] = useState(false);
  const [ownerDefaultCode, setOwnerDefaultCode] = useState("+1");
  const [newClient, setNewClient] = useState({
    user_name: "",
    user_email: "",
    countryCode: "+1",
    localPhone: "",
  });

  const refreshData = async () => {
    if (!clientId) return;
    setLoading(true);
    setError("");
    try {
      const [clientsRes, appointmentsRes, profileRes] = await Promise.all([
        authFetch(`${API_BASE_URL}/appointments/clients?client_id=${clientId}`),
        authFetch(`${API_BASE_URL}/appointments/show?client_id=${clientId}`),
        authFetch(`${API_BASE_URL}/profile/${clientId}`),
      ]);

      const clientsPayload = clientsRes.ok ? await clientsRes.json() : { clients: [] };
      const appointmentsPayload = appointmentsRes.ok ? await appointmentsRes.json() : [];
      const profilePayload = profileRes.ok ? await profileRes.json() : {};

      const inferred = inferPhoneCountryCode({
        country: profilePayload?.profile?.country || "",
        timezone: profilePayload?.timezone || "",
      });
      setOwnerDefaultCode(inferred);
      setNewClient((prev) => ({ ...prev, countryCode: prev.localPhone ? prev.countryCode : inferred }));

      if (clientsRes.status === 503) {
        setDirectoryWarning(ui.directoryMissing503);
      } else if (clientsPayload?.directory_available === false) {
        setDirectoryWarning(ui.directoryUnavailable);
      } else {
        setDirectoryWarning("");
      }

      setClients(Array.isArray(clientsPayload?.clients) ? clientsPayload.clients : []);
      setAppointments(Array.isArray(appointmentsPayload) ? appointmentsPayload : []);

      if (showCampaignHistory) {
        const [audienceRes, campaignsRes] = await Promise.all([
          authFetch(`${API_BASE_URL}/marketing/audience?client_id=${clientId}`),
          authFetch(`${API_BASE_URL}/marketing/campaigns?client_id=${clientId}`),
        ]);

        const audiencePayload = await audienceRes.json().catch(() => ({}));
        const campaignsPayload = await campaignsRes.json().catch(() => ({}));

        if (!audienceRes.ok || !campaignsRes.ok) {
          setMarketingSignalsError(
            audiencePayload?.detail ||
              campaignsPayload?.detail ||
              ui.marketingSignalsLoadFailed
          );
          setMarketingAudience([]);
          setMarketingCampaigns([]);
        } else {
          setMarketingSignalsError("");
          setMarketingAudience(Array.isArray(audiencePayload?.items) ? audiencePayload.items : []);
          setMarketingCampaigns(Array.isArray(campaignsPayload?.items) ? campaignsPayload.items : []);
        }
      } else {
        setMarketingAudience([]);
        setMarketingCampaigns([]);
        setMarketingSignalsError("");
      }
    } catch (e) {
      console.error("Failed loading appointment clients", e);
      setError(ui.loadClientsError);
      setClients([]);
      setAppointments([]);
      setMarketingAudience([]);
      setMarketingCampaigns([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refreshData();
  }, [clientId]);

  const historyByKey = useMemo(() => {
    const map = new Map();
    for (const appt of appointments) {
      const key = buildContactMatchKey(appt || {});
      if (!key) continue;
      if (!map.has(key)) map.set(key, []);
      map.get(key).push(appt);
    }
    for (const [, list] of map) {
      list.sort((a, b) => String(b?.scheduled_time || "").localeCompare(String(a?.scheduled_time || "")));
    }
    return map;
  }, [appointments]);

  const audienceByRecipientKey = useMemo(() => {
    const map = new Map();
    for (const row of marketingAudience || []) {
      const key = String(row?.recipient_key || "").trim();
      if (!key) continue;
      map.set(key, row);
    }
    return map;
  }, [marketingAudience]);

  useEffect(() => {
    if (!showCampaignHistory || !clientId || campaignFilter === "all") {
      setCampaignRecipientKeys(null);
      setCampaignRecipientsLoading(false);
      return;
    }

    let active = true;
    const loadCampaignRecipients = async () => {
      setCampaignRecipientsLoading(true);
      try {
        const params = new URLSearchParams({ client_id: String(clientId) });
        const res = await authFetch(`${API_BASE_URL}/marketing/campaigns/${campaignFilter}?${params.toString()}`);
        const data = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(data?.detail || ui.marketingSignalsLoadFailed);
        if (!active) return;
        const nextKeys = new Set(
          (Array.isArray(data?.recipients) ? data.recipients : [])
            .map((row) => String(row?.recipient_key || "").trim())
            .filter(Boolean)
        );
        setMarketingSignalsError("");
        setCampaignRecipientKeys(nextKeys);
      } catch (e) {
        if (!active) return;
        setCampaignRecipientKeys(new Set());
        setMarketingSignalsError(e?.message || ui.marketingSignalsLoadFailed);
      } finally {
        if (active) setCampaignRecipientsLoading(false);
      }
    };

    loadCampaignRecipients();
    return () => {
      active = false;
    };
  }, [showCampaignHistory, clientId, campaignFilter, ui.marketingSignalsLoadFailed]);

  const filteredClients = useMemo(() => {
    const q = search.trim().toLowerCase();
    return (clients || [])
      .map((row) => {
        const matchKey = row.match_key || buildContactMatchKey(row);
        const recipientKey = buildMarketingRecipientKey({ ...row, match_key: matchKey });
        const marketingRow = audienceByRecipientKey.get(recipientKey) || {};
        return {
          ...row,
          match_key: matchKey,
          recipient_key: recipientKey,
          history: historyByKey.get(matchKey) || [],
          interest_status: normalizeInterestStatus(marketingRow?.interest_status),
          email_unsubscribed: Boolean(marketingRow?.email_unsubscribed),
          whatsapp_unsubscribed: Boolean(marketingRow?.whatsapp_unsubscribed),
          is_opted_out: Boolean(marketingRow?.is_opted_out),
          selection_blocked_reason: String(marketingRow?.selection_blocked_reason || ""),
          channels: Array.isArray(marketingRow?.channels) ? marketingRow.channels : [],
          marketing_state_last_seen_at: marketingRow?.marketing_state_last_seen_at || null,
        };
      })
      .filter((row) => {
        const matchesSearch =
          !q ||
          String(row.user_name || "").toLowerCase().includes(q) ||
          String(row.user_email || "").toLowerCase().includes(q) ||
          String(row.user_phone || "").toLowerCase().includes(q);
        if (!matchesSearch) return false;

        if (interestFilter !== "all") {
          const commercialStatus = resolveCommercialStatus(row);
          if (interestFilter === "opt_out") {
            if (commercialStatus !== "opt_out") return false;
          } else if (normalizeInterestStatus(row.interest_status) !== interestFilter) {
            return false;
          }
        }

        if (channelFilter !== "all") {
          const channels = Array.isArray(row.channels) && row.channels.length
            ? row.channels
            : [
                row.user_email ? "email" : null,
                row.user_phone ? "whatsapp" : null,
              ].filter(Boolean);
          if (!channels.includes(channelFilter)) return false;
        }

        if (
          showCampaignHistory &&
          campaignFilter !== "all" &&
          !campaignRecipientsLoading &&
          campaignRecipientKeys instanceof Set &&
          !campaignRecipientKeys.has(String(row.recipient_key || ""))
        ) {
          return false;
        }

        return true;
      });
  }, [
    audienceByRecipientKey,
    campaignFilter,
    campaignRecipientKeys,
    campaignRecipientsLoading,
    channelFilter,
    clients,
    historyByKey,
    interestFilter,
    search,
    showCampaignHistory,
  ]);

  const canCreateNewClient = (() => {
    const email = normalizeAppointmentEmail(newClient.user_email);
    const phone = composeE164Phone(newClient.countryCode || ownerDefaultCode, newClient.localPhone);
    const name = normalizeAppointmentName(newClient.user_name);
    return (
      name.length >= 2 &&
      isValidAppointmentEmail(email) &&
      isValidAppointmentPhone(phone) &&
      Boolean(email || phone)
    );
  })();

  const saveNewClient = async () => {
    if (!clientId || !canCreateNewClient || saving) return;
    setSaving(true);
    setError("");
    try {
      const payload = {
        client_id: clientId,
        user_name: normalizeAppointmentName(newClient.user_name),
        user_email: normalizeAppointmentEmail(newClient.user_email) || null,
        user_phone: composeE164Phone(newClient.countryCode || ownerDefaultCode, newClient.localPhone) || null,
      };
      const res = await authFetch(`${API_BASE_URL}/appointments/clients`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data?.detail || ui.saveClientFailed);
      }
      setShowNewClient(false);
      setNewClient({
        user_name: "",
        user_email: "",
        countryCode: ownerDefaultCode,
        localPhone: "",
      });
      await refreshData();
    } catch (e) {
      setError(e.message || ui.saveClientFailed);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={container}>
      <div style={headerRow}>
        <div>
          <h3 style={title}>{ui.title}</h3>
          <p style={hint}>
            {ui.subtitle}
          </p>
        </div>
        <div style={headerActions}>
          {appointmentsCtaHref ? (
            <button
              style={secondaryBtn}
              onClick={() => {
                window.location.href = appointmentsCtaHref;
              }}
              disabled={saving}
            >
              {appointmentsCtaLabel || ui.goToAppointments}
            </button>
          ) : null}
          <button style={primaryBtn(saving)} onClick={() => setShowNewClient((v) => !v)} disabled={saving}>
            {showNewClient ? ui.close : ui.newClient}
          </button>
        </div>
      </div>

      <div style={searchRow}>
        <input
          style={input}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder={ui.searchPlaceholder}
        />
        <button style={secondaryBtn} onClick={refreshData} disabled={loading}>
          {loading ? (t("loading") || "Loading") : ui.refresh}
        </button>
      </div>

      {showCampaignHistory ? (
        <div style={filtersBox}>
          <div style={filtersGrid}>
            <select style={{ ...input, marginBottom: 0 }} value={interestFilter} onChange={(e) => setInterestFilter(e.target.value)}>
              <option value="all">{ui.interestFilterLabel}: {ui.allInterestStatuses}</option>
              <option value="interested">{ui.interestInterested}</option>
              <option value="not_interested">{ui.interestNotInterested}</option>
              <option value="unknown">{ui.interestUnknown}</option>
              <option value="opt_out">{ui.interestOptOut}</option>
            </select>

            <select style={{ ...input, marginBottom: 0 }} value={campaignFilter} onChange={(e) => setCampaignFilter(e.target.value)}>
              <option value="all">{ui.campaignFilterLabel}: {ui.allCampaigns}</option>
              {(marketingCampaigns || []).map((campaign) => (
                <option key={campaign.id} value={campaign.id}>
                  {campaign.name}
                </option>
              ))}
            </select>

            <select style={{ ...input, marginBottom: 0 }} value={channelFilter} onChange={(e) => setChannelFilter(e.target.value)}>
              <option value="all">{ui.channelFilterLabel}: {ui.allChannels}</option>
              <option value="email">{ui.channelEmail}</option>
              <option value="whatsapp">{ui.channelWhatsapp}</option>
            </select>
          </div>
          {campaignFilter !== "all" && campaignRecipientsLoading ? (
            <p style={{ ...subtleText, marginTop: "0.55rem" }}>{ui.campaignRecipientsLoading}</p>
          ) : null}
        </div>
      ) : null}

      {directoryWarning && <div style={warningBox}>{directoryWarning}</div>}
      {error && <div style={errorBox}>{error}</div>}
      {marketingSignalsError && showCampaignHistory ? <div style={warningBox}>{marketingSignalsError}</div> : null}

      {showNewClient && (
        <div style={panel}>
          <h4 style={panelTitle}>{ui.createClientTitle}</h4>
          <input
            style={input}
            value={newClient.user_name}
            onChange={(e) => setNewClient((prev) => ({ ...prev, user_name: e.target.value }))}
            placeholder={ui.name}
          />
          <input
            style={input}
            value={newClient.user_email}
            onChange={(e) => setNewClient((prev) => ({ ...prev, user_email: e.target.value }))}
            placeholder="Email"
          />
          {newClient.user_email && !isValidAppointmentEmail(newClient.user_email) && (
            <p style={fieldHintError}>{ui.invalidEmail}</p>
          )}

          <PhoneInputRow
            countryCode={newClient.countryCode || ownerDefaultCode}
            localPhone={newClient.localPhone}
            onCountryCodeChange={(countryCode) => setNewClient((prev) => ({ ...prev, countryCode }))}
            onLocalPhoneChange={(localPhone) => setNewClient((prev) => ({ ...prev, localPhone }))}
            phonePlaceholder={ui.phonePlaceholder}
          />
          {composeE164Phone(newClient.countryCode || ownerDefaultCode, newClient.localPhone) &&
            !isValidAppointmentPhone(composeE164Phone(newClient.countryCode || ownerDefaultCode, newClient.localPhone)) && (
              <p style={fieldHintError}>{ui.invalidPhone}</p>
            )}
          <div style={actions}>
            <button style={secondaryBtn} onClick={() => setShowNewClient(false)} disabled={saving}>
              {ui.cancel}
            </button>
            <button style={primaryBtn(!canCreateNewClient || saving)} onClick={saveNewClient} disabled={!canCreateNewClient || saving}>
              {saving ? ui.saving : ui.saveClient}
            </button>
          </div>
        </div>
      )}

      {loading && <p style={hint}>{t("appointments_loading") || "Loading..."}</p>}

      {!loading && filteredClients.length === 0 && (
        <div style={emptyBox}>
          {search || interestFilter !== "all" || campaignFilter !== "all" || channelFilter !== "all"
            ? ui.noClientsFiltered
            : ui.noClients}
        </div>
      )}

      {!loading && filteredClients.length > 0 && (
        <div style={list}>
          {filteredClients.map((client) => (
            <AppointmentClientCard
              key={client.match_key || client.id || `${client.user_name || "client"}-${client.user_email || client.user_phone || "na"}`}
              clientId={clientId}
              client={client}
              ui={ui}
              uiLocale={uiLocale}
              onSaved={refreshData}
              showCampaignHistory={showCampaignHistory}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function AppointmentClientCard({ clientId, client, ui, uiLocale, onSaved, showCampaignHistory = false }) {
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [expanded, setExpanded] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [campaignLoading, setCampaignLoading] = useState(false);
  const [campaignError, setCampaignError] = useState("");
  const [campaignHistory, setCampaignHistory] = useState([]);
  const [loadedCampaignRecipientKey, setLoadedCampaignRecipientKey] = useState("");
  const initialPhone = splitE164Phone(client.user_phone || "");
  const [draft, setDraft] = useState({
    user_name: client.user_name || "",
    user_email: client.user_email || "",
    countryCode: initialPhone.countryCode,
    localPhone: initialPhone.localNumber,
  });

  useEffect(() => {
    const nextPhone = splitE164Phone(client.user_phone || "");
    setDraft({
      user_name: client.user_name || "",
      user_email: client.user_email || "",
      countryCode: nextPhone.countryCode,
      localPhone: nextPhone.localNumber,
    });
    setIsEditing(false);
    setCampaignLoading(false);
    setCampaignError("");
    setCampaignHistory([]);
    setLoadedCampaignRecipientKey("");
  }, [client.id, client.match_key, client.user_name, client.user_email, client.user_phone]);

  const fullPhone = composeE164Phone(draft.countryCode, draft.localPhone);
  const normalizedEmail = normalizeAppointmentEmail(draft.user_email);
  const normalizedName = normalizeAppointmentName(draft.user_name);
  const recipientKey = buildMarketingRecipientKey(client);
  const canSave =
    normalizedName.length >= 2 &&
    isValidAppointmentEmail(normalizedEmail) &&
    isValidAppointmentPhone(fullPhone) &&
    Boolean(normalizedEmail || fullPhone);

  useEffect(() => {
    if (!showCampaignHistory || !expanded || !clientId || !recipientKey) return;
    if (loadedCampaignRecipientKey === recipientKey) return;

    let active = true;
    const fetchCampaignHistory = async () => {
      setCampaignLoading(true);
      setCampaignError("");
      try {
        const params = new URLSearchParams({
          client_id: String(clientId),
          recipient_key: recipientKey,
        });
        const res = await authFetch(`${API_BASE_URL}/marketing/audience/history?${params.toString()}`);
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
          if (res.status === 503) throw new Error(ui.campaignsUnavailable);
          throw new Error(data?.detail || ui.campaignsLoadFailed);
        }
        if (!active) return;
        setCampaignHistory(Array.isArray(data?.items) ? data.items : []);
        setLoadedCampaignRecipientKey(recipientKey);
      } catch (e) {
        if (!active) return;
        setCampaignHistory([]);
        setCampaignError(e?.message || ui.campaignsLoadFailed);
      } finally {
        if (active) setCampaignLoading(false);
      }
    };

    fetchCampaignHistory();
    return () => {
      active = false;
    };
  }, [showCampaignHistory, expanded, clientId, recipientKey, loadedCampaignRecipientKey, ui.campaignsUnavailable, ui.campaignsLoadFailed]);

  const save = async () => {
    if (!canSave || !clientId || saving) return;
    setSaving(true);
    setError("");
    try {
      const body = {
        client_id: clientId,
        user_name: normalizedName,
        user_email: normalizedEmail || null,
        user_phone: fullPhone || null,
      };
      const url = client.id
        ? `${API_BASE_URL}/appointments/clients/${client.id}`
        : `${API_BASE_URL}/appointments/clients`;
      const method = client.id ? "PATCH" : "POST";

      const res = await authFetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data?.detail || ui.saveFailed);
      setIsEditing(false);
      await onSaved?.();
    } catch (e) {
      setError(e.message || ui.saveFailed);
    } finally {
      setSaving(false);
    }
  };

  const removeClient = async () => {
    if (!client?.id || !clientId || saving) return;
    if (!window.confirm(ui.deleteConfirm)) return;
    setSaving(true);
    setError("");
    try {
      const res = await authFetch(
        `${API_BASE_URL}/appointments/clients/${client.id}?client_id=${clientId}`,
        { method: "DELETE" }
      );
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data?.detail || ui.deleteFailed);
      setIsEditing(false);
      setExpanded(false);
      await onSaved?.();
    } catch (e) {
      setError(e.message || ui.deleteFailed);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={card}>
      <div style={contactRowCompact}>
        <div style={contactMain}>
          <strong style={{ color: "#274472" }}>{client.user_name || ui.clientFallback}</strong>
          <div style={contactInlineMeta}>
            {client.user_email && <span style={contactChip}>✉️ {client.user_email}</span>}
            {client.user_phone && <span style={contactChip}>📞 {client.user_phone}</span>}
            <span style={badge}>{ui.appointmentsCount(client.history?.length || client.appointments_count || 0)}</span>
            {showCampaignHistory ? (
              <span style={interestStatusPill(resolveCommercialStatus(client))}>
                {ui.commercialStatusLabel}: {interestStatusLabel(resolveCommercialStatus(client), ui)}
              </span>
            ) : null}
            {client.last_appointment_time && (
              <span style={subtleText}>{ui.lastLabel}: {formatDateTime(client.last_appointment_time, uiLocale)}</span>
            )}
            {showCampaignHistory && client.marketing_state_last_seen_at ? (
              <span style={subtleText}>{ui.lastSignalLabel}: {formatDateTime(client.marketing_state_last_seen_at, uiLocale)}</span>
            ) : null}
            {!client.id && <span style={ghostBadge}>{ui.derivedFromAppointments}</span>}
          </div>
        </div>
        <div style={rowActions}>
          <button style={secondaryBtn} onClick={() => setExpanded((v) => !v)}>
            {expanded ? ui.hideHistory : ui.viewHistory}
          </button>
          {client.id && (
            <button
              style={dangerIconBtn}
              title={ui.deleteTitle}
              onClick={removeClient}
              disabled={saving}
            >
              {saving ? "…" : "🗑️"}
            </button>
          )}
          <button
            style={iconBtn}
            title={isEditing ? ui.closeEditTitle : ui.editTitle}
            onClick={() => setIsEditing((v) => !v)}
            disabled={saving}
          >
            ✏️
          </button>
        </div>
      </div>

      {isEditing && (
        <div style={editPanel}>
          <div style={grid}>
            <input
              style={input}
              value={draft.user_name}
              onChange={(e) => setDraft((prev) => ({ ...prev, user_name: e.target.value }))}
              placeholder={ui.name}
            />
            <input
              style={input}
              value={draft.user_email}
              onChange={(e) => setDraft((prev) => ({ ...prev, user_email: e.target.value }))}
              placeholder="Email"
            />
          </div>
          {draft.user_email && !isValidAppointmentEmail(draft.user_email) && <p style={fieldHintError}>{ui.invalidEmail}</p>}

          <PhoneInputRow
            countryCode={draft.countryCode}
            localPhone={draft.localPhone}
            onCountryCodeChange={(countryCode) => setDraft((prev) => ({ ...prev, countryCode }))}
            onLocalPhoneChange={(localPhone) => setDraft((prev) => ({ ...prev, localPhone }))}
            phonePlaceholder={ui.phonePlaceholder}
          />
          {fullPhone && !isValidAppointmentPhone(fullPhone) && (
            <p style={fieldHintError}>{ui.invalidPhone}</p>
          )}

          {error && <p style={fieldHintError}>{error}</p>}

          <div style={actions}>
            <button style={secondaryBtn} onClick={() => setIsEditing(false)} disabled={saving}>
              {ui.cancel}
            </button>
            <button style={primaryBtn(!canSave || saving)} disabled={!canSave || saving} onClick={save}>
              {saving ? ui.saving : client.id ? ui.saveChanges : ui.saveInClients}
            </button>
          </div>
        </div>
      )}

      {expanded && (
        <div style={historyBox}>
          <div style={historyTitle}>{ui.historyTitle}</div>
          {client.history?.length ? (
            <div style={historyList}>
              {client.history.map((item) => {
                const internalNotes = String(item.internal_notes || "").trim();
                return (
                  <div key={item.id} style={historyItem}>
                    <div style={historyMetaRow}>
                      <span>{formatDateTime(item.scheduled_time, uiLocale)}</span>
                      <span>{String(item.status || "confirmed")}</span>
                      <span>{String(item.appointment_type || "general")}</span>
                    </div>
                    {internalNotes && (
                      <div style={historyNote}>
                        <strong>{ui.internalNotesLabel}:</strong> {internalNotes}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          ) : (
            <p style={subtleText}>{ui.noHistory}</p>
          )}

          {showCampaignHistory && (
            <div style={campaignHistoryBox}>
              <div style={historyTitle}>{ui.campaignsTitle}</div>
              {!recipientKey ? (
                <p style={subtleText}>{ui.campaignsNeedsContact}</p>
              ) : campaignLoading ? (
                <p style={subtleText}>{ui.campaignsLoading}</p>
              ) : campaignError ? (
                <p style={fieldHintError}>{campaignError}</p>
              ) : campaignHistory.length ? (
                <div style={historyList}>
                  {campaignHistory.map((item, idx) => (
                    <div key={`${item.campaign_id || "campaign"}-${item.updated_at || idx}`} style={historyItem}>
                      <div style={campaignHeaderRow}>
                        <strong style={{ color: "#274472" }}>
                          {item.campaign_name || `${ui.campaignLabel} ${item.campaign_id || ""}`}
                        </strong>
                        <span style={contactChip}>{String(item.campaign_channel || "—").toUpperCase()}</span>
                        <span style={campaignStatusPill}>{String(item.send_status || "unknown")}</span>
                        <span style={interestStatusPill(item.response_status || "unknown")}>
                          {ui.responseStatusLabel}: {interestStatusLabel(item.response_status, ui)}
                        </span>
                      </div>
                      <div style={campaignMetaText}>
                        {ui.sentAtLabel}: {formatDateTime(item.sent_at, uiLocale)}
                      </div>
                      {item.response_status && item.response_status !== "unknown" ? (
                        <div style={campaignMetaText}>
                          {ui.responseAtLabel}: {formatDateTime(item.response_at, uiLocale)}
                        </div>
                      ) : null}
                      <div style={campaignMetaText}>
                        {ui.lastUpdateLabel}: {formatDateTime(item.updated_at, uiLocale)}
                      </div>
                      {item.send_error && (
                        <div style={campaignErrorText}>
                          <strong>{ui.sendErrorLabel}:</strong> {String(item.send_error)}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <p style={subtleText}>{ui.noCampaignHistory}</p>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function buildMarketingRecipientKey(client) {
  const matchKey = String(client?.match_key || "").trim();
  if (matchKey.startsWith("email:") || matchKey.startsWith("phone:")) {
    return matchKey;
  }

  const normalizedEmail = normalizeAppointmentEmail(client?.user_email || "");
  if (normalizedEmail) return `email:${normalizedEmail}`;

  const normalizedPhone = String(client?.user_phone || "").trim();
  if (isValidAppointmentPhone(normalizedPhone)) return `phone:${normalizedPhone}`;

  return "";
}

function normalizeInterestStatus(value) {
  const normalized = String(value || "unknown").trim().toLowerCase();
  if (normalized === "interested" || normalized === "not_interested" || normalized === "opt_out") {
    return normalized;
  }
  return "unknown";
}

function resolveCommercialStatus(client) {
  if (
    client?.is_opted_out ||
    client?.email_unsubscribed ||
    client?.whatsapp_unsubscribed ||
    String(client?.selection_blocked_reason || "").toLowerCase() === "opt_out"
  ) {
    return "opt_out";
  }
  return normalizeInterestStatus(client?.interest_status);
}

function interestStatusLabel(status, ui) {
  if (String(status || "").trim().toLowerCase() === "opt_out") return ui.interestOptOut;
  const normalized = normalizeInterestStatus(status);
  if (normalized === "interested") return ui.interestInterested;
  if (normalized === "not_interested") return ui.interestNotInterested;
  return ui.interestUnknown;
}

function PhoneInputRow({ countryCode, localPhone, onCountryCodeChange, onLocalPhoneChange, phonePlaceholder = "Phone" }) {
  return (
    <div style={phoneRow}>
      <select
        style={{ ...input, marginBottom: 0, flex: "0 0 190px" }}
        value={countryCode}
        onChange={(e) => onCountryCodeChange?.(e.target.value)}
      >
        {PHONE_COUNTRY_OPTIONS.map((opt) => (
          <option key={opt.code} value={opt.code}>
            {opt.label}
          </option>
        ))}
      </select>
      <input
        style={{ ...input, marginBottom: 0, flex: 1 }}
        value={localPhone}
        onChange={(e) => onLocalPhoneChange?.(sanitizePhoneLocalInput(e.target.value))}
        placeholder={phonePlaceholder}
        inputMode="tel"
      />
    </div>
  );
}

function formatDateTime(value, locale = "en-US") {
  try {
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return String(value || "");
    return d.toLocaleString(locale, {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return String(value || "");
  }
}

const container = {
  padding: "clamp(0.75rem, 0.6rem + 0.8vw, 1.1rem)",
  border: "1px solid #EDEDED",
  borderRadius: 14,
  background: "#FFFFFF",
};

const headerRow = {
  display: "flex",
  justifyContent: "space-between",
  gap: "0.75rem",
  alignItems: "flex-start",
  flexWrap: "wrap",
};

const title = { margin: 0, color: "#274472", fontSize: "1.1rem" };
const hint = { margin: "0.35rem 0 0", color: "#6b7280", fontSize: "0.9rem" };
const headerActions = { display: "flex", gap: "0.6rem", flexWrap: "wrap", alignItems: "center" };

const searchRow = {
  display: "flex",
  gap: "0.6rem",
  flexWrap: "wrap",
  marginTop: "0.9rem",
  marginBottom: "0.9rem",
};

const filtersBox = {
  border: "1px solid #EDEDED",
  backgroundColor: "#FAFBFC",
  borderRadius: 12,
  padding: "0.8rem",
  marginBottom: "0.9rem",
};

const filtersGrid = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
  gap: "0.6rem",
};

const input = {
  width: "100%",
  padding: "0.6rem 0.7rem",
  border: "1px solid #EDEDED",
  borderRadius: 10,
  marginBottom: "0.6rem",
  color: "#274472",
  backgroundColor: "#FFFFFF",
};

const phoneRow = {
  display: "flex",
  gap: "0.6rem",
  flexWrap: "wrap",
  marginBottom: "0.6rem",
};

const panel = {
  border: "1px solid #EDEDED",
  backgroundColor: "#FAFBFC",
  borderRadius: 12,
  padding: "0.9rem",
  marginBottom: "0.9rem",
};

const panelTitle = { margin: "0 0 0.6rem", color: "#274472" };

const list = { display: "flex", flexDirection: "column", gap: "0.85rem" };

const card = {
  border: "1px solid #EDEDED",
  borderRadius: 12,
  padding: "0.9rem",
  backgroundColor: "#FFFFFF",
};

const contactRowCompact = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "flex-start",
  gap: "0.75rem",
  flexWrap: "wrap",
};

const contactMain = {
  flex: "1 1 420px",
  minWidth: 0,
};

const contactInlineMeta = {
  marginTop: "0.35rem",
  display: "flex",
  gap: "0.35rem",
  flexWrap: "wrap",
  alignItems: "center",
};

const contactChip = {
  backgroundColor: "#F8FAFC",
  border: "1px solid #E5E7EB",
  color: "#334155",
  borderRadius: 999,
  padding: "0.2rem 0.55rem",
  fontSize: "0.8rem",
};

const rowActions = {
  display: "flex",
  gap: "0.45rem",
  alignItems: "center",
  flexWrap: "wrap",
};

const iconBtn = {
  backgroundColor: "#FFFFFF",
  border: "1px solid #E5E7EB",
  color: "#274472",
  borderRadius: 10,
  padding: "0.5rem 0.65rem",
  cursor: "pointer",
  lineHeight: 1,
};

const dangerIconBtn = {
  backgroundColor: "#FFF1F2",
  border: "1px solid #FECACA",
  color: "#BE123C",
  borderRadius: 10,
  padding: "0.5rem 0.65rem",
  cursor: "pointer",
  lineHeight: 1,
};

const editPanel = {
  marginTop: "0.75rem",
  paddingTop: "0.75rem",
  borderTop: "1px dashed #E5E7EB",
};

const cardHeader = {
  display: "flex",
  justifyContent: "space-between",
  gap: "0.75rem",
  alignItems: "flex-start",
  flexWrap: "wrap",
  marginBottom: "0.7rem",
};

const metaLine = {
  marginTop: "0.35rem",
  display: "flex",
  gap: "0.4rem",
  flexWrap: "wrap",
  alignItems: "center",
};

const badge = {
  backgroundColor: "#EAF7F0",
  border: "1px solid #CDEBDB",
  color: "#1F6B4A",
  borderRadius: 999,
  padding: "0.2rem 0.6rem",
  fontSize: "0.78rem",
  fontWeight: 700,
};

const ghostBadge = {
  backgroundColor: "#FFF7EA",
  border: "1px solid #FFD8A8",
  color: "#7A4D00",
  borderRadius: 999,
  padding: "0.2rem 0.6rem",
  fontSize: "0.78rem",
  fontWeight: 700,
};

const subtleText = { color: "#6b7280", fontSize: "0.83rem", margin: 0 };

const grid = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
  gap: "0.6rem",
};

const actions = { display: "flex", justifyContent: "flex-end", gap: "0.6rem", flexWrap: "wrap" };

const primaryBtn = (disabled) => ({
  backgroundColor: disabled ? "#BDE9DF" : "#2EB39A",
  color: "#FFFFFF",
  border: "none",
  borderRadius: 10,
  padding: "0.55rem 0.9rem",
  cursor: disabled ? "not-allowed" : "pointer",
});

const secondaryBtn = {
  backgroundColor: "#F3F4F6",
  color: "#274472",
  border: "1px solid #E5E7EB",
  borderRadius: 10,
  padding: "0.55rem 0.9rem",
  cursor: "pointer",
};

const warningBox = {
  border: "1px solid #FFD8A8",
  backgroundColor: "#FFF8ED",
  color: "#7A4D00",
  borderRadius: 10,
  padding: "0.7rem 0.8rem",
  marginBottom: "0.75rem",
  fontSize: "0.88rem",
};

const errorBox = {
  border: "1px solid #fecdd3",
  backgroundColor: "#fff1f2",
  color: "#be123c",
  borderRadius: 10,
  padding: "0.7rem 0.8rem",
  marginBottom: "0.75rem",
  fontSize: "0.88rem",
};

const fieldHintError = { margin: "0 0 0.5rem", color: "#be123c", fontSize: "0.82rem" };

const emptyBox = {
  border: "1px dashed #D1D5DB",
  borderRadius: 12,
  padding: "1rem",
  color: "#6b7280",
  textAlign: "center",
};

const historyBox = {
  marginTop: "0.9rem",
  borderTop: "1px solid #F0F1F3",
  paddingTop: "0.8rem",
};

const campaignHistoryBox = {
  marginTop: "0.9rem",
  borderTop: "1px dashed #E5E7EB",
  paddingTop: "0.75rem",
};

const historyTitle = { color: "#274472", fontWeight: 700, marginBottom: "0.45rem" };
const historyList = { display: "flex", flexDirection: "column", gap: "0.35rem" };

const historyItem = {
  display: "flex",
  flexDirection: "column",
  gap: "0.4rem",
  alignItems: "stretch",
  padding: "0.45rem 0.55rem",
  border: "1px solid #F0F1F3",
  borderRadius: 8,
};

const historyMetaRow = {
  display: "grid",
  gridTemplateColumns: "minmax(150px, 1.6fr) 1fr 1fr",
  gap: "0.45rem",
  alignItems: "center",
  fontSize: "0.83rem",
  color: "#374151",
};

const historyNote = {
  borderTop: "1px dashed #E5E7EB",
  paddingTop: "0.35rem",
  fontSize: "0.82rem",
  color: "#2B4058",
  lineHeight: 1.35,
  whiteSpace: "pre-wrap",
};

const campaignHeaderRow = {
  display: "flex",
  gap: "0.4rem",
  alignItems: "center",
  flexWrap: "wrap",
};

const campaignMetaText = {
  margin: 0,
  fontSize: "0.82rem",
  color: "#475569",
};

const campaignStatusPill = {
  backgroundColor: "#EEF2FF",
  border: "1px solid #C7D2FE",
  color: "#3730A3",
  borderRadius: 999,
  padding: "0.18rem 0.55rem",
  fontSize: "0.75rem",
  fontWeight: 700,
};

const campaignErrorText = {
  borderTop: "1px dashed #E5E7EB",
  paddingTop: "0.35rem",
  fontSize: "0.8rem",
  color: "#BE123C",
  whiteSpace: "pre-wrap",
};

const interestStatusPill = (status) => {
  const normalized = normalizeInterestStatus(status);
  if (normalized === "interested") {
    return {
      backgroundColor: "#EAF7F0",
      border: "1px solid #CDEBDB",
      color: "#1F6B4A",
      borderRadius: 999,
      padding: "0.2rem 0.55rem",
      fontSize: "0.78rem",
      fontWeight: 700,
    };
  }
  if (normalized === "not_interested") {
    return {
      backgroundColor: "#FFF7EA",
      border: "1px solid #FFD8A8",
      color: "#9A6700",
      borderRadius: 999,
      padding: "0.2rem 0.55rem",
      fontSize: "0.78rem",
      fontWeight: 700,
    };
  }
  if (status === "opt_out") {
    return {
      backgroundColor: "#FFF1F2",
      border: "1px solid #FECACA",
      color: "#BE123C",
      borderRadius: 999,
      padding: "0.2rem 0.55rem",
      fontSize: "0.78rem",
      fontWeight: 700,
    };
  }
  return {
    backgroundColor: "#F8FAFC",
    border: "1px solid #E5E7EB",
    color: "#475569",
    borderRadius: 999,
    padding: "0.2rem 0.55rem",
    fontSize: "0.78rem",
    fontWeight: 700,
  };
};
