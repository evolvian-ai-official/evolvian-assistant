import { useState, useEffect } from "react";
import { useClientId } from "../../hooks/useClientId";
import { useLanguage } from "../../contexts/LanguageContext";
import { authFetch } from "../../lib/authFetch";
import "../../components/ui/internal-admin-responsive.css";

export default function Upload() {
  const [file, setFile] = useState(null);
  const [message, setMessage] = useState("");
  const [messageType, setMessageType] = useState("info");
  const [uploadedFiles, setUploadedFiles] = useState([]);
  const [limitReached, setLimitReached] = useState(false);
  const [loading, setLoading] = useState(true);
  const clientId = useClientId();
  const { t } = useLanguage();

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
      console.error("Error al listar archivos:", err);
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
      setMessage(t("invalid_client_id"));
      setMessageType("error");
      return;
    }

    if (!file) {
      setMessage(t("please_select_file"));
      setMessageType("warning");
      return;
    }

    const formData = new FormData();
    formData.append("client_id", clientId);
    formData.append("file", file);

    try {
      const res = await authFetch(`${import.meta.env.VITE_API_URL}/upload_document`, {
        method: "POST",
        body: formData,
      });

      if (res.status === 403) {
        const errorData = await res.json();
        const detail = errorData?.detail || "";
        setLimitReached(true);

        if (detail === "limit_reached") {
          setMessage(t("limit_reached_error"));
        } else {
          setMessage(detail || t("unknown_upload_error"));
        }
        setMessageType("error");

        return;
      }

      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.detail || t("unknown_upload_error"));
      }

      const data = await res.json();
      console.log("Respuesta backend:", data);
      setMessage(data.message || t("file_uploaded_success"));
      setMessageType("success");
      setFile(null);
      fetchFiles();
    } catch (err) {
      console.error("Error al subir archivo:", err);
      setMessage(err.message);
      setMessageType("error");
    }
  };

  const handleDelete = async (storagePath) => {
    if (!window.confirm(`${t("confirm_delete_file")} ${storagePath}?`)) return;

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
      console.log("Respuesta backend:", data);

      setMessage(data.message || t("file_deleted_success"));
      setMessageType("success");
      fetchFiles();
    } catch (err) {
      console.error("Error al borrar archivo:", err);
      setMessage(err.message);
      setMessageType("error");
    }
  };

  const getMessageColor = (type) => {
    if (type === "success") return "#2EB39A";
    if (type === "warning") return "#F5A623";
    if (type === "error") return "#E74C3C";
    return "#274472";
  };

  if (loading) {
    return (
      <div className="ia-page">
        <div className="ia-loader">
          <div className="ia-spinner" />
          <p style={{ color: "#274472", marginTop: "1rem" }}>{t("loading") || "Loading..."}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="ia-page">
      <div className="ia-shell ia-upload-shell">
        <section className="ia-card" style={{ marginBottom: 0 }}>
          <h1 className="ia-upload-title">{t("upload_document")}</h1>

          {limitReached && (
            <div className="ia-upload-limit-banner">
              <strong>{t("limit_reached_title") || "Limit reached"}</strong>
              <span style={{ display: "block", marginTop: 6 }}>{t("limit_reached_error")}</span>
            </div>
          )}

          <form onSubmit={handleSubmit}>
            <div style={{ marginBottom: "1.2rem" }}>
              <label className="ia-upload-label">{t("select_file_label")}</label>

              <input
                type="file"
                accept=".pdf,.txt"
                onChange={(e) => setFile(e.target.files[0])}
                disabled={limitReached}
                className="ia-upload-input"
                style={{
                  opacity: limitReached ? 0.6 : 1,
                  cursor: limitReached ? "not-allowed" : "pointer",
                }}
              />
              <p className="ia-upload-help">
                {t("supported_formats") || "Supported formats"}: .pdf, .txt -{" "}
                <span style={{ color: "#274472" }}>{t("max_file_size") || "Max file size"}: 10MB</span>
              </p>
            </div>

            <button
              type="submit"
              disabled={limitReached}
              className="ia-button ia-button-primary"
              style={{ backgroundColor: limitReached ? "#9BBCE6" : "#4A90E2" }}
            >
              {t("upload_file")}
            </button>
          </form>

          {message && (
            <p className="ia-upload-message" style={{ color: getMessageColor(messageType) }}>
              {message}
            </p>
          )}

          {uploadedFiles.length > 0 && (
            <div className="ia-upload-section">
              <h3 className="ia-upload-subtitle">{t("uploaded_files")}</h3>
              <ul className="ia-upload-file-list">
                {uploadedFiles.map((f, idx) => (
                  <li key={idx} className="ia-upload-file-row">
                    <div className="ia-upload-file-meta ia-break-anywhere">
                      <strong>{f.name}</strong> <span className="ia-upload-size">- {f.size_kb} KB</span>
                    </div>
                    <button
                      type="button"
                      onClick={() => handleDelete(f.storage_path)}
                      className="ia-button ia-button-danger"
                    >
                      {t("delete")}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="ia-upload-info">
            <h3 className="ia-upload-subtitle" style={{ marginBottom: 8 }}>
              {t("readiness_tips_title") || "Document Requirements for Best AI Readiness"}
            </h3>
            <ul className="ia-upload-info-list">
              <li>
                {t("tip_clear_formatting") ||
                  "Use clear, well-formatted text (avoid scans or images of text)."}
              </li>
              <li>{t("tip_supported_formats") || "Supported formats: .pdf and .txt."}</li>
              <li>{t("tip_size") || "Keep each file under 10MB for optimal processing."}</li>
              <li>
                {t("tip_one_topic") ||
                  "Organize content by topic (one manual/policy/FAQ per file)."}
              </li>
              <li>
                {t("tip_ready_soon") ||
                  "The assistant learns from your files within minutes after upload."}
              </li>
              <li>{t("tip_reupload") || "You can delete and re-upload updated versions anytime."}</li>
            </ul>
            <p className="ia-upload-tip">
              {t("tip_text_heavy") || "Text-heavy and structured documents yield the most accurate answers."}
            </p>
          </div>
        </section>
      </div>
    </div>
  );
}
