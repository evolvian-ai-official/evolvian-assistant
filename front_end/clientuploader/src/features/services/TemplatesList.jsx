import { useEffect, useState } from "react";
import { useLanguage } from "../../contexts/LanguageContext";
import TemplatesUpdateDelete from "../services/Templates_update_delete";
import "../../components/ui/internal-admin-responsive.css";

const truncate = (text = "", max = 220) => {
  if (!text) return "—";
  return text.length > max ? `${text.slice(0, max)}…` : text;
};

export default function TemplatesList({ clientId, type, refreshKey }) {
  const { t } = useLanguage();
  const API = import.meta.env.VITE_API_URL;

  const [templates, setTemplates] = useState([]);
  const [loading, setLoading] = useState(true);

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [selectedTemplate, setSelectedTemplate] = useState(null);

  useEffect(() => {
    if (!clientId) return;
    fetchTemplates();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clientId, type, refreshKey]);

  const fetchTemplates = async () => {
    try {
      setLoading(true);

      const params = new URLSearchParams();
      params.append("client_id", clientId);
      if (type) params.append("type", type);

      const res = await fetch(`${API}/message_templates?${params.toString()}`);
      if (!res.ok) throw new Error();

      const list = await res.json();
      setTemplates(Array.isArray(list) ? list : []);
    } catch (err) {
      console.error("❌ Error loading templates", err);
      setTemplates([]);
    } finally {
      setLoading(false);
    }
  };

  const openEditModal = (template) => {
    setSelectedTemplate(template);
    setIsModalOpen(true);
  };

  if (loading) {
    return <p style={{ marginTop: "1.1rem", color: "#6B7280" }}>{t("loading") || "Loading"}...</p>;
  }

  if (templates.length === 0) {
    return (
      <div
        style={{
          marginTop: "1.1rem",
          padding: "1.1rem",
          border: "1px dashed #EDEDED",
          borderRadius: "12px",
          color: "#999",
        }}
      >
        {t("no_templates_created") || "No templates created yet."}
      </div>
    );
  }

  return (
    <>
      <div style={{ marginTop: "1rem", display: "grid", gap: "0.8rem" }}>
        {templates.map((tpl) => {
          const isMeta = tpl.is_meta_template;

          const templateTitle = tpl.meta_template_name || tpl.label || tpl.template_name || "—";

          const bodyPreview = isMeta ? truncate(tpl.meta_preview_body) : truncate(tpl.body);

          return (
            <div
              key={tpl.id}
              style={{
                border: "1px solid #EDEDED",
                borderRadius: "12px",
                padding: "0.95rem",
                backgroundColor: "#fff",
              }}
            >
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "flex-start",
                  gap: "0.7rem",
                  flexWrap: "wrap",
                }}
              >
                <h3 style={{ margin: 0, color: "#274472", overflowWrap: "anywhere" }}>{templateTitle}</h3>

                <span
                  style={{
                    fontSize: "0.75rem",
                    padding: "0.25rem 0.6rem",
                    borderRadius: "6px",
                    backgroundColor: tpl.channel === "whatsapp" ? "#25D36620" : "#4A90E220",
                    color: tpl.channel === "whatsapp" ? "#25D366" : "#4A90E2",
                    fontWeight: "bold",
                  }}
                >
                  {tpl.channel?.toUpperCase()}
                </span>
              </div>

              <div
                style={{
                  marginTop: "0.7rem",
                  padding: "0.75rem",
                  borderRadius: "10px",
                  backgroundColor: isMeta ? "#F8FAFC" : "#FAFAFA",
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
                  {bodyPreview}
                </p>

                {isMeta && tpl.meta_parameter_count && (
                  <small
                    style={{
                      display: "block",
                      marginTop: "0.5rem",
                      color: "#999",
                      fontSize: "0.75rem",
                    }}
                  >
                    🔒 Official Meta template • {tpl.meta_parameter_count} parameter(s)
                  </small>
                )}
              </div>

              <button
                type="button"
                onClick={() => openEditModal(tpl)}
                className="ia-button ia-button-ghost"
                style={{ marginTop: "0.75rem", width: "100%" }}
              >
                ✎ {t("edit") || "Edit"}
              </button>
            </div>
          );
        })}
      </div>

      <TemplatesUpdateDelete
        isOpen={isModalOpen}
        mode="edit"
        initialData={selectedTemplate}
        clientId={clientId}
        onClose={() => {
          setIsModalOpen(false);
          setSelectedTemplate(null);
        }}
        onSuccess={() => {
          fetchTemplates();
        }}
      />
    </>
  );
}
