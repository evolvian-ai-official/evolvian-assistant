import { useEffect, useMemo, useState } from "react";
import { useLanguage } from "../../contexts/LanguageContext";
import TemplatesUpdateDelete from "../services/Templates_update_delete";
import { authFetch } from "../../lib/authFetch";
import "../../components/ui/internal-admin-responsive.css";

const truncate = (text = "", max = 260) => {
  if (!text) return "—";
  return text.length > max ? `${text.slice(0, max)}…` : text;
};

const normalizeMetaStatus = (status) => {
  const value = String(status || "not_synced").trim().toLowerCase();
  if (["active", "approved", "ready"].includes(value)) return "ready";
  if (["pending", "pending_review", "in_review"].includes(value)) return "pending";
  if (["inactive", "rejected", "paused", "disabled", "archived", "deleted"].includes(value)) {
    return "inactive";
  }
  if (value === "not_synced") return "not_synced";
  return "unknown";
};

const metaStatusLabel = (status, t) => {
  if (status === "ready") return t("templates_meta_status_label_ready");
  if (status === "pending") return t("templates_meta_status_label_pending");
  if (status === "inactive") return t("templates_meta_status_label_inactive");
  if (status === "not_synced") return t("templates_meta_status_label_not_synced");
  return t("templates_meta_status_label_unknown");
};

const metaStatusPalette = (status) => {
  if (status === "ready") return { bg: "#E9F9EF", color: "#1F8F4D" };
  if (status === "pending") return { bg: "#FFF7E8", color: "#A66A00" };
  if (status === "inactive") return { bg: "#FDEBEC", color: "#B42318" };
  return { bg: "#EEF2F8", color: "#364152" };
};

const formatLanguageBadge = (value) => {
  const raw = String(value || "").trim();
  if (!raw) return null;
  if (raw.toLowerCase().startsWith("es")) return "ES";
  if (raw.toLowerCase().startsWith("en")) return "EN";
  return raw.toUpperCase();
};

export default function TemplatesList({ clientId, refreshKey, selectedLanguage = "es" }) {
  const { t } = useLanguage();
  const API = import.meta.env.VITE_API_URL;

  const [configuredTemplates, setConfiguredTemplates] = useState([]);
  const [metaTemplates, setMetaTemplates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [syncingMetaStatus, setSyncingMetaStatus] = useState(false);

  const [search, setSearch] = useState("");
  const [channelFilter, setChannelFilter] = useState("all");
  const [typeFilter, setTypeFilter] = useState("all");
  const [activityFilter, setActivityFilter] = useState("active");
  const [metaStatusFilter, setMetaStatusFilter] = useState("all");

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [selectedTemplate, setSelectedTemplate] = useState(null);

  const fetchTemplates = async () => {
    if (!clientId) return;

    try {
      setLoading(true);

      const configuredParams = new URLSearchParams();
      configuredParams.append("client_id", clientId);

      const metaParams = new URLSearchParams();
      metaParams.append("client_id", clientId);
      metaParams.append("channel", "whatsapp");
      metaParams.append("refresh_status", "false");
      metaParams.append("language_family", selectedLanguage === "en" ? "en" : "es");

      const [configuredRes, metaRes] = await Promise.all([
        authFetch(`${API}/message_templates?${configuredParams.toString()}`),
        authFetch(`${API}/meta_approved_templates?${metaParams.toString()}`),
      ]);

      if (!configuredRes.ok) throw new Error("Failed loading configured templates");
      if (!metaRes.ok) throw new Error("Failed loading Meta templates");

      const configuredData = await configuredRes.json();
      const metaData = await metaRes.json();

      setConfiguredTemplates(Array.isArray(configuredData) ? configuredData : []);
      setMetaTemplates(Array.isArray(metaData) ? metaData : []);
    } catch (err) {
      console.error("❌ Error loading templates", err);
      setConfiguredTemplates([]);
      setMetaTemplates([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTemplates();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clientId, refreshKey, selectedLanguage]);

  const allCards = useMemo(() => {
    const configuredMetaIds = new Set(
      configuredTemplates
        .map((row) => row?.meta_template_id)
        .filter((value) => Boolean(value))
    );

    const configuredCards = configuredTemplates
      .filter((tpl) => {
        if (tpl.channel === "email" && !tpl.is_active) return false;
        if (tpl.channel === "whatsapp" && !tpl.meta_template_id) return false;
        const langProbe = String(tpl.meta_language || tpl.locale_code || tpl.language_family || "").toLowerCase();
        if (!langProbe) return false;
        const family = langProbe.startsWith("en") ? "en" : "es";
        if (family !== (selectedLanguage === "en" ? "en" : "es")) return false;
        return true;
      })
      .map((tpl) => {
        const isWhatsApp = tpl.channel === "whatsapp";
        return {
        key: `msg-${tpl.id}`,
        source: "configured",
        canEdit: true,
        channel: tpl.channel || "unknown",
        type: tpl.type || "unknown",
        active: Boolean(tpl.is_active),
        title:
          (isWhatsApp ? tpl.meta_template_name : null) ||
          tpl.label ||
          tpl.template_name ||
          t("templates_default_title"),
        bodyPreview: isWhatsApp ? tpl.meta_preview_body : tpl.body,
        metaStatus: isWhatsApp ? normalizeMetaStatus(tpl.whatsapp_template_status) : null,
        billable: isWhatsApp ? Boolean(tpl.billable) : null,
        estimatedUnitCost: isWhatsApp ? Number(tpl.estimated_unit_cost || 0) : null,
        pricingCurrency: isWhatsApp ? tpl.pricing_currency || "USD" : null,
        metaParameterCount: tpl.meta_parameter_count,
        languageBadge: formatLanguageBadge(tpl.meta_language || tpl.locale_code || tpl.language_family),
        raw: tpl,
        };
      });

    const metaCatalogCards = metaTemplates
      .filter((tpl) => !configuredMetaIds.has(tpl.id))
      .map((tpl) => ({
        key: `meta-${tpl.id}`,
        source: "meta_catalog",
        canEdit: false,
        channel: "whatsapp",
        type: tpl.type || "unknown",
        active: Boolean(tpl.client_template_active),
        title: tpl.template_name || t("templates_meta_default_title"),
        bodyPreview: tpl.preview_body,
        metaStatus: normalizeMetaStatus(tpl.client_template_status),
        billable: Boolean(tpl.billable),
        estimatedUnitCost: Number(tpl.estimated_unit_cost || 0),
        pricingCurrency: tpl.pricing_currency || "USD",
        metaParameterCount: tpl.parameter_count,
        languageBadge: formatLanguageBadge(tpl.language),
        raw: tpl,
      }));

    const priority = {
      ready: 0,
      pending: 1,
      not_synced: 2,
      inactive: 3,
      unknown: 4,
    };

    return [...configuredCards, ...metaCatalogCards].sort((a, b) => {
      const aPriority = a.channel === "whatsapp" ? (priority[a.metaStatus] ?? 9) : 5;
      const bPriority = b.channel === "whatsapp" ? (priority[b.metaStatus] ?? 9) : 5;
      if (aPriority !== bPriority) return aPriority - bPriority;
      return String(a.title || "").localeCompare(String(b.title || ""));
    });
  }, [configuredTemplates, metaTemplates, selectedLanguage]);

  const availableTypes = useMemo(() => {
    const values = new Set(allCards.map((card) => card.type).filter(Boolean));
    return Array.from(values).sort();
  }, [allCards]);

  const filteredCards = useMemo(() => {
    const searchValue = search.trim().toLowerCase();
    return allCards.filter((card) => {
      if (channelFilter !== "all" && card.channel !== channelFilter) return false;
      if (typeFilter !== "all" && card.type !== typeFilter) return false;
      if (activityFilter === "active" && !card.active) return false;
      if (activityFilter === "inactive" && card.active) return false;

      if (metaStatusFilter !== "all") {
        if (card.channel !== "whatsapp") return false;
        if (card.metaStatus !== metaStatusFilter) return false;
      }

      if (!searchValue) return true;
      const haystack = `${card.title || ""} ${card.bodyPreview || ""} ${card.type || ""}`.toLowerCase();
      return haystack.includes(searchValue);
    });
  }, [allCards, search, channelFilter, typeFilter, activityFilter, metaStatusFilter]);

  const openEditModal = (card) => {
    if (!card?.canEdit) return;
    setSelectedTemplate(card.raw);
    setIsModalOpen(true);
  };

  const handleTemplateModalSuccess = (event) => {
    if (event?.action === "deactivated" && event?.templateId) {
      setConfiguredTemplates((prev) =>
        prev.map((row) =>
          row.id === event.templateId
            ? {
                ...row,
                is_active: false,
              }
            : row
        )
      );
    }

    fetchTemplates();
  };

  const refreshMetaStatuses = async () => {
    if (!clientId) return;

    try {
      setSyncingMetaStatus(true);
      const res = await authFetch(`${API}/api/whatsapp/templates/refresh_status`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          client_id: clientId,
          force_refresh: false,
        }),
      });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || t("templates_meta_refresh_failed_fallback"));
      }
      const summary = await res.json().catch(() => null);
      if (summary && summary.success === false) {
        const details = Array.isArray(summary.errors) && summary.errors.length
          ? summary.errors.join(", ")
          : t("templates_meta_refresh_failed_fallback");
        throw new Error(details);
      }
      await fetchTemplates();
    } catch (err) {
      console.error(err);
      const detail =
        err instanceof Error && err.message
          ? err.message
          : t("templates_meta_refresh_alert_prefix");
      alert(`${t("templates_meta_refresh_alert_prefix")} ${detail}`);
    } finally {
      setSyncingMetaStatus(false);
    }
  };

  if (loading) {
    return <p style={{ marginTop: "1.1rem", color: "#6B7280" }}>{t("loading") || "Loading"}...</p>;
  }

  return (
    <>
      <div
        style={{
          marginTop: "1rem",
          padding: "0.8rem",
          border: "1px solid #EDEDED",
          borderRadius: "12px",
          backgroundColor: "#FAFCFF",
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", gap: "0.6rem", flexWrap: "wrap" }}>
          <strong style={{ color: "#274472", fontSize: "0.92rem" }}>{t("templates_filters_title")}</strong>
          <button
            type="button"
            className="ia-button ia-button-ghost"
            onClick={refreshMetaStatuses}
            disabled={syncingMetaStatus}
            style={{ padding: "0.35rem 0.55rem", fontSize: "0.78rem" }}
          >
            {syncingMetaStatus ? t("templates_refreshing") : t("templates_refresh_meta_status")}
          </button>
        </div>

        <div style={{ marginTop: "0.65rem", display: "grid", gap: "0.55rem", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))" }}>
          <input
            className="ia-form-input"
            placeholder={t("templates_search_placeholder")}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />

          <select className="ia-form-input" value={channelFilter} onChange={(e) => setChannelFilter(e.target.value)}>
            <option value="all">{t("templates_filter_all_channels")}</option>
            <option value="whatsapp">{t("whatsapp")}</option>
            <option value="email">{t("email")}</option>
            <option value="widget">Widget</option>
          </select>

          <select className="ia-form-input" value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)}>
            <option value="all">{t("templates_filter_all_types")}</option>
            {availableTypes.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>

          <select className="ia-form-input" value={activityFilter} onChange={(e) => setActivityFilter(e.target.value)}>
            <option value="all">{t("templates_filter_all_activity")}</option>
            <option value="active">{t("templates_status_active")}</option>
            <option value="inactive">{t("templates_status_inactive")}</option>
          </select>

          <select className="ia-form-input" value={metaStatusFilter} onChange={(e) => setMetaStatusFilter(e.target.value)}>
            <option value="all">{t("templates_filter_any_meta_status")}</option>
            <option value="ready">{t("templates_meta_status_ready_short")}</option>
            <option value="pending">{t("templates_meta_status_pending_short")}</option>
            <option value="inactive">{t("templates_meta_status_inactive_short")}</option>
            <option value="not_synced">{t("templates_meta_status_not_synced_short")}</option>
            <option value="unknown">{t("templates_meta_status_unknown_short")}</option>
          </select>
        </div>
      </div>

      {filteredCards.length === 0 ? (
        <div
          style={{
            marginTop: "1rem",
            padding: "1rem",
            border: "1px dashed #EDEDED",
            borderRadius: "12px",
            color: "#667085",
          }}
        >
          {t("templates_no_results")}
        </div>
      ) : (
        <div style={{ marginTop: "1rem", display: "grid", gap: "0.8rem" }}>
          {filteredCards.map((card) => {
            const isWhatsApp = card.channel === "whatsapp";
            const statusColors = metaStatusPalette(card.metaStatus);
            const emailStatusActive = card.active;

            return (
              <div
                key={card.key}
                style={{
                  border: "1px solid #EDEDED",
                  borderRadius: "12px",
                  padding: "0.95rem",
                  backgroundColor: "#fff",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", gap: "0.7rem", flexWrap: "wrap" }}>
                  <h3 style={{ margin: 0, color: "#274472", overflowWrap: "anywhere" }}>{card.title}</h3>
                  <div style={{ display: "flex", gap: "0.35rem", flexWrap: "wrap" }}>
                    <span
                      style={{
                        fontSize: "0.72rem",
                        padding: "0.2rem 0.5rem",
                        borderRadius: "999px",
                        backgroundColor:
                          card.channel === "whatsapp"
                            ? "#25D36620"
                            : card.channel === "widget"
                            ? "#7C3AED20"
                            : "#4A90E220",
                        color:
                          card.channel === "whatsapp"
                            ? "#25D366"
                            : card.channel === "widget"
                            ? "#7C3AED"
                            : "#4A90E2",
                        fontWeight: 700,
                      }}
                    >
                      {card.channel?.toUpperCase()}
                    </span>
                    <span
                      style={{
                        fontSize: "0.72rem",
                        padding: "0.2rem 0.5rem",
                        borderRadius: "999px",
                        backgroundColor: "#EEF2FF",
                        color: "#344054",
                        fontWeight: 600,
                      }}
                    >
                      {card.type}
                    </span>
                    {card.languageBadge && (
                      <span
                        style={{
                          fontSize: "0.72rem",
                          padding: "0.2rem 0.5rem",
                          borderRadius: "999px",
                          backgroundColor: "#F3F4F6",
                          color: "#111827",
                          fontWeight: 700,
                        }}
                      >
                        {card.languageBadge}
                      </span>
                    )}
                  </div>
                </div>

                <div
                  style={{
                    marginTop: "0.7rem",
                    padding: "0.75rem",
                    borderRadius: "10px",
                    backgroundColor: "#FAFAFA",
                    border: "1px solid #EDEDED",
                  }}
                >
                  <p
                    style={{
                      margin: 0,
                      fontSize: "0.9rem",
                      color: "#555",
                      lineHeight: "1.5",
                      whiteSpace: "pre-line",
                      overflowWrap: "anywhere",
                    }}
                  >
                    {truncate(card.bodyPreview)}
                  </p>

                  <div style={{ marginTop: "0.55rem", display: "flex", gap: "0.45rem", flexWrap: "wrap" }}>
                    {isWhatsApp ? (
                      <span
                        style={{
                          display: "inline-flex",
                          fontSize: "0.72rem",
                          fontWeight: 700,
                          borderRadius: "999px",
                          padding: "0.2rem 0.5rem",
                          backgroundColor: statusColors.bg,
                          color: statusColors.color,
                        }}
                      >
                        {metaStatusLabel(card.metaStatus, t)}
                      </span>
                    ) : (
                      <span
                        style={{
                          display: "inline-flex",
                          fontSize: "0.72rem",
                          fontWeight: 700,
                          borderRadius: "999px",
                          padding: "0.2rem 0.5rem",
                          backgroundColor: emailStatusActive ? "#E9F9EF" : "#FDEBEC",
                          color: emailStatusActive ? "#1F8F4D" : "#B42318",
                        }}
                      >
                        {emailStatusActive ? t("templates_status_active") : t("templates_status_inactive")}
                      </span>
                    )}

                    {card.source === "meta_catalog" && (
                      <span
                        style={{
                          display: "inline-flex",
                          fontSize: "0.72rem",
                          fontWeight: 600,
                          borderRadius: "999px",
                          padding: "0.2rem 0.5rem",
                          backgroundColor: "#EEF2F8",
                          color: "#344054",
                        }}
                      >
                        {t("templates_meta_catalog")}
                      </span>
                    )}
                  </div>

                  {card.metaParameterCount ? (
                    <small style={{ display: "block", marginTop: "0.45rem", color: "#667085", fontSize: "0.75rem" }}>
                      {t("templates_parameters")}: {card.metaParameterCount}
                    </small>
                  ) : null}

                  {isWhatsApp && (
                    <small style={{ display: "block", marginTop: "0.35rem", color: "#617187", fontSize: "0.75rem" }}>
                      {card.billable
                        ? `${t("templates_estimated_meta_charge_prefix")} ~$${Number(card.estimatedUnitCost || 0).toFixed(3)} ${card.pricingCurrency || "USD"} / ${t("templates_per_message")}`
                        : t("templates_estimated_meta_charge_no_direct")}
                    </small>
                  )}
                </div>

                {card.canEdit ? (
                  <button
                    type="button"
                    onClick={() => openEditModal(card)}
                    className="ia-button ia-button-ghost"
                    style={{ marginTop: "0.75rem", width: "100%" }}
                  >
                    ✎ {t("edit") || "Edit"}
                  </button>
                ) : (
                  <button
                    type="button"
                    className="ia-button ia-button-ghost"
                    disabled
                    style={{ marginTop: "0.75rem", width: "100%", opacity: 0.7, cursor: "not-allowed" }}
                  >
                    {t("templates_managed_by_meta_sync")}
                  </button>
                )}
              </div>
            );
          })}
        </div>
      )}

      <TemplatesUpdateDelete
        isOpen={isModalOpen}
        mode="edit"
        initialData={selectedTemplate}
        clientId={clientId}
        onClose={() => {
          setIsModalOpen(false);
          setSelectedTemplate(null);
        }}
        onSuccess={handleTemplateModalSuccess}
      />
    </>
  );
}
