// src/features/templates/Templates.jsx
import { useState } from "react";
import { useClientId } from "../../hooks/useClientId";
import { useLanguage } from "../../contexts/LanguageContext";
import CreateTemplateModal from "./CreateTemplateModal";
import TemplatesList from "./TemplatesList";

export default function Templates() {
  const clientId = useClientId();
  const { t } = useLanguage();
  const [showModal, setShowModal] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);

  return (
    <div style={{ padding: "2rem 3rem" }}>
      {/* Header */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <div>
          <h1 style={{ color: "#F5A623", fontSize: "1.8rem" }}>
            📝 {t("templates_title")}
          </h1>
          <p style={{ color: "#4A90E2", marginTop: "0.5rem" }}>
            {t("templates_subtitle")}
          </p>
        </div>

        <button
          onClick={() => setShowModal(true)}
          style={primaryButton}
        >
          ➕ {t("create_template_button")}
        </button>
      </div>

      {/* ✅ ALL templates */}
      <TemplatesList
        clientId={clientId}
        refreshKey={refreshKey}
      />

      {/* Modal */}
      {showModal && (
        <CreateTemplateModal
          clientId={clientId}
          onClose={() => setShowModal(false)}
          onCreated={() => {
            setShowModal(false);
            setRefreshKey((k) => k + 1); // 🔁 refetch limpio
          }}
        />
      )}
    </div>
  );
}

/* ======================================================
   Styles
====================================================== */

const primaryButton = {
  backgroundColor: "#F5A623",
  color: "#fff",
  border: "none",
  borderRadius: "8px",
  padding: "0.5rem 1rem",
  fontWeight: "bold",
  cursor: "pointer",
};
