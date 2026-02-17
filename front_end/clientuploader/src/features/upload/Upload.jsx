// src/features/upload/Upload.jsx
import { useState, useEffect } from "react";
import { useClientId } from "../../hooks/useClientId";
import { useLanguage } from "../../contexts/LanguageContext";
import { authFetch } from "../../lib/authFetch";

export default function Upload() {
  const [file, setFile] = useState(null);
  const [message, setMessage] = useState("");
  const [uploadedFiles, setUploadedFiles] = useState([]);
  const [limitReached, setLimitReached] = useState(false);
  const [loading, setLoading] = useState(true);
  const clientId = useClientId();
  const { t } = useLanguage();

  // 🌀 Inject spinner animation keyframes (solo una vez)
  useEffect(() => {
    if (typeof document !== "undefined" && !document.getElementById("spin-keyframes")) {
      const style = document.createElement("style");
      style.id = "spin-keyframes";
      style.textContent = `
        @keyframes spin {
          0% { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }
      `;
      document.head.appendChild(style);
    }
  }, []);

  const fetchFiles = async () => {
    if (!clientId) return;
    try {
      setLoading(true);
      const res = await authFetch(
        `${import.meta.env.VITE_API_URL}/list_files?client_id=${clientId}`
      );
      const data = await res.json();
      setUploadedFiles(data.files || []);
    } catch (err) {
      console.error("❌ Error al listar archivos:", err);
      setUploadedFiles([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (clientId) fetchFiles();
  }, [clientId]);

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!clientId || clientId === "undefined" || clientId.trim() === "") {
      setMessage(`❌ ${t("invalid_client_id")}`);
      return;
    }

    if (!file) {
      setMessage(`⚠️ ${t("please_select_file")}`);
      return;
    }

    const formData = new FormData();
    formData.append("client_id", clientId);
    formData.append("file", file);

    try {
      const res = await authFetch(
        `${import.meta.env.VITE_API_URL}/upload_document`,
        {
          method: "POST",
          body: formData,
        }
      );

      if (res.status === 403) {
        const errorData = await res.json();
        const detail = errorData?.detail || "";
        setLimitReached(true);

        if (detail === "limit_reached") {
          setMessage(`🚫 ${t("limit_reached_error")}`);
        } else {
          setMessage(`🚫 ${detail || t("unknown_upload_error")}`);
        }

        return;
      }

      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.detail || t("unknown_upload_error"));
      }

      const data = await res.json();
      console.log("📥 Respuesta backend:", data);
      setMessage(`✅ ${data.message || t("file_uploaded_success")}`);
      setFile(null);
      fetchFiles();
    } catch (err) {
      console.error("❌ Error al subir archivo:", err);
      setMessage(`❌ ${err.message}`);
    }
  };

  const handleDelete = async (storagePath) => {
  if (!window.confirm(`⚠️ ${t("confirm_delete_file")} ${storagePath}?`)) return;

  try {
    const res = await authFetch(
      `${import.meta.env.VITE_API_URL}/delete_chunks?client_id=${clientId}&storage_path=${encodeURIComponent(
        storagePath
      )}`,
      { method: "DELETE" }
    );

    if (!res.ok) {
      const errorData = await res.json();
      throw new Error(errorData.detail || t("unknown_delete_error"));
    }

    const data = await res.json();
    console.log("🗑️ Respuesta backend:", data);

    setMessage(`✅ ${data.message || t("file_deleted_success")}`);
    fetchFiles();
  } catch (err) {
    console.error("❌ Error al borrar archivo:", err);
    setMessage(`❌ ${err.message}`);
  }
};


  // 🎨 Color del mensaje según tipo
  const getMessageColor = (msg) => {
    if (!msg) return "#274472";
    if (msg.startsWith("✅")) return "#2EB39A";
    if (msg.startsWith("⚠️")) return "#F5A623";
    if (msg.startsWith("🚫") || msg.startsWith("❌")) return "#E74C3C";
    return "#274472";
  };

  // 🌀 Loader (branding light)
  if (loading) {
    return (
      <div style={loaderContainer}>
        <div style={spinner}></div>
        <p style={{ color: "#274472", marginTop: "1rem" }}>
          {t("loading") || "Loading..."}
        </p>
      </div>
    );
  }

  return (
    <div style={pageContainer}>
      <div style={card}>
        <h1 style={title}>
          📤 {t("upload_document")}
        </h1>

        {/* Banner de límite alcanzado */}
        {limitReached && (
          <div style={limitBanner}>
            <strong>{t("limit_reached_title") || "Limit reached"}</strong>
            <span style={{ display: "block", marginTop: 6 }}>
              {t("limit_reached_error")}
            </span>
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: "1.2rem" }}>
            <label style={label}>
              📎 {t("select_file_label")}
            </label>

            <input
              type="file"
              accept=".pdf,.txt"
              onChange={(e) => setFile(e.target.files[0])}
              disabled={limitReached}
              style={{
                ...fileInput,
                opacity: limitReached ? 0.6 : 1,
                cursor: limitReached ? "not-allowed" : "pointer",
              }}
            />
            <p style={helpText}>
              {t("supported_formats") || "Supported formats"}: .pdf, .txt —{" "}
              <span style={{ color: "#274472" }}>
                {t("max_file_size") || "Max file size"}: 10MB
              </span>
            </p>
          </div>

          <button
            type="submit"
            disabled={limitReached}
            style={{
              ...primaryBtn,
              backgroundColor: limitReached ? "#9BBCE6" : "#4A90E2",
              cursor: limitReached ? "not-allowed" : "pointer",
            }}
          >
            {t("upload_file")}
          </button>
        </form>

        {message && (
          <p style={{ marginTop: "1rem", fontWeight: 600, color: getMessageColor(message) }}>
            {message}
          </p>
        )}

        {uploadedFiles.length > 0 && (
          <div style={{ marginTop: "2rem" }}>
            <h3 style={sectionTitle}>
              📂 {t("uploaded_files")}
            </h3>
            <ul style={{ listStyleType: "none", paddingLeft: 0, margin: 0 }}>
              {uploadedFiles.map((f, idx) => (
                <li key={idx} style={fileRow}>
                  <div style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    📄 <strong>{f.name}</strong>{" "}
                    <span style={{ color: "#6B7280" }}>— {f.size_kb} KB</span>
                  </div>
                  <button
                    onClick={() => handleDelete(f.storage_path)}
                    style={dangerBtn}
                  >
                    🗑️ {t("delete")}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* 🧠 Requisitos / Tips (branding light) */}
        <div style={infoBlock}>
          <h3 style={{ ...sectionTitle, marginBottom: 8 }}>
            🧠 {t("readiness_tips_title") || "Document Requirements for Best AI Readiness"}
          </h3>
          <ul style={infoList}>
            <li>{t("tip_clear_formatting") || "Use clear, well-formatted text (avoid scans or images of text)."}</li>
            <li>{t("tip_supported_formats") || "Supported formats: .pdf and .txt."}</li>
            <li>{t("tip_size") || "Keep each file under 10MB for optimal processing."}</li>
            <li>{t("tip_one_topic") || "Organize content by topic (one manual/policy/FAQ per file)."}</li>
            <li>{t("tip_ready_soon") || "The assistant learns from your files within minutes after upload."}</li>
            <li>{t("tip_reupload") || "You can delete and re-upload updated versions anytime."}</li>
          </ul>
          <p style={{ marginTop: 10, color: "#2EB39A" }}>
            💡 {t("tip_text_heavy") || "Text-heavy and structured documents yield the most accurate answers."}
          </p>
        </div>
      </div>
    </div>
  );
}

/* 🎨 Estilos (Evolvian Premium Light) */
const pageContainer = {
  backgroundColor: "#FFFFFF",
  minHeight: "100vh",
  padding: "2rem",
  fontFamily: "system-ui, sans-serif",
  color: "#274472",
  display: "flex",
  justifyContent: "center",
};

const card = {
  backgroundColor: "#FFFFFF",
  border: "1px solid #EDEDED",
  borderRadius: "16px",
  padding: "2rem",
  width: "100%",
  maxWidth: 760,
  boxShadow: "0 8px 24px rgba(0,0,0,0.06)",
};

const title = {
  fontSize: "1.8rem",
  marginBottom: "1rem",
  color: "#F5A623",
  fontWeight: 800,
};

const label = {
  display: "block",
  marginBottom: "0.5rem",
  color: "#274472",
  fontWeight: 600,
};

const fileInput = {
  width: "100%",
  padding: "0.55rem 0.75rem",
  backgroundColor: "#FFFFFF",
  border: "1px solid #CFE1F7",
  color: "#274472",
  borderRadius: "10px",
  outline: "none",
};

const helpText = {
  marginTop: 8,
  fontSize: "0.9rem",
  color: "#6B7280",
};

const primaryBtn = {
  backgroundColor: "#4A90E2",
  padding: "0.7rem 1.2rem",
  color: "white",
  borderRadius: "10px",
  fontWeight: 700,
  border: "none",
  transition: "transform 0.05s ease",
};

const dangerBtn = {
  backgroundColor: "#E74C3C",
  padding: "0.45rem 0.85rem",
  color: "white",
  borderRadius: "8px",
  border: "none",
  fontWeight: 700,
  cursor: "pointer",
};

const sectionTitle = {
  color: "#4A90E2",
  fontWeight: 800,
  fontSize: "1.1rem",
};

const fileRow = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  gap: "0.75rem",
  border: "1px solid #EDEDED",
  borderRadius: "12px",
  padding: "0.75rem 0.9rem",
  marginBottom: "0.7rem",
  background: "#FFFFFF",
};

const infoBlock = {
  marginTop: "2rem",
  padding: "1.2rem",
  backgroundColor: "#F9FAFB",
  border: "1px solid #EDEDED",
  borderRadius: "12px",
  color: "#374151",
  fontSize: "0.95rem",
  lineHeight: 1.6,
};

const infoList = {
  margin: 0,
  paddingLeft: "1.1rem",
  listStyle: "disc",
  display: "grid",
  gap: "0.35rem",
};

const limitBanner = {
  backgroundColor: "#FFF7E6",
  border: "1px solid #F5A623",
  color: "#7A4A00",
  padding: "10px 12px",
  borderRadius: "10px",
  marginBottom: "1rem",
};

/* Loader (light) */
const loaderContainer = {
  display: "flex",
  flexDirection: "column",
  alignItems: "center",
  justifyContent: "center",
  backgroundColor: "#FFFFFF",
  minHeight: "100vh",
  color: "#274472",
  fontFamily: "system-ui, sans-serif",
};

const spinner = {
  width: 40,
  height: 40,
  border: "4px solid #EDEDED",
  borderTop: "4px solid #4A90E2",
  borderRadius: "50%",
  animation: "spin 1s linear infinite",
};
