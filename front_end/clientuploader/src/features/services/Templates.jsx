import { useState } from "react";
import { useClientId } from "../../hooks/useClientId";
import { useLanguage } from "../../contexts/LanguageContext";
import CreateTemplateModal from "./CreateTemplateModal";
import TemplatesList from "./TemplatesList";
import "../../components/ui/internal-admin-responsive.css";

export default function Templates() {
  const clientId = useClientId();
  const { t } = useLanguage();
  const [showModal, setShowModal] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);

  return (
    <div className="ia-page">
      <div className="ia-shell ia-services-shell">
        <section className="ia-card" style={{ marginBottom: 0 }}>
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "flex-start",
              gap: "0.75rem",
              flexWrap: "wrap",
            }}
          >
            <div>
              <h1 className="ia-header-title">📝 {t("templates_title")}</h1>
              <p className="ia-header-subtitle">
                Email templates are created here. WhatsApp templates are synced from Meta and tracked by status.
              </p>
            </div>

            <button onClick={() => setShowModal(true)} className="ia-button ia-button-warning">
              ➕ Create Template
            </button>
          </div>

          <TemplatesList clientId={clientId} refreshKey={refreshKey} />

          {showModal && (
            <CreateTemplateModal
              clientId={clientId}
              onClose={() => setShowModal(false)}
              onCreated={() => {
                setShowModal(false);
                setRefreshKey((k) => k + 1);
              }}
            />
          )}
        </section>
      </div>
    </div>
  );
}
