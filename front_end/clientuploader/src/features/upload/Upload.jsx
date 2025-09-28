import { useState, useEffect } from "react";
import { useClientId } from "../../hooks/useClientId";
import { useLanguage } from "../../contexts/LanguageContext";

export default function Upload() {
  const [file, setFile] = useState(null);
  const [message, setMessage] = useState("");
  const [uploadedFiles, setUploadedFiles] = useState([]);
  const [limitReached, setLimitReached] = useState(false);
  const clientId = useClientId();
  const { t } = useLanguage();

  const fetchFiles = async () => {
    if (!clientId) return;
    try {
      const res = await fetch(
        `${import.meta.env.VITE_API_URL}/list_files?client_id=${clientId}`
      );
      const data = await res.json();
      setUploadedFiles(data.files || []);
    } catch (err) {
      console.error("❌ Error al listar archivos:", err);
      setUploadedFiles([]);
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
      const res = await fetch(
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
      const res = await fetch(
        `${import.meta.env.VITE_API_URL}/api/delete_file?storage_path=${encodeURIComponent(
          storagePath
        )}`,
        {
          method: "DELETE",
        }
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

  return (
    <div
      style={{
        backgroundColor: "#0f1c2e",
        minHeight: "100vh",
        padding: "2rem",
        fontFamily: "system-ui, sans-serif",
        color: "white",
        display: "flex",
        justifyContent: "center",
        alignItems: "flex-start",
      }}
    >
      <div
        style={{
          backgroundColor: "#1b2a41",
          padding: "2rem",
          borderRadius: "16px",
          maxWidth: "600px",
          width: "100%",
          boxShadow: "0 10px 30px rgba(0,0,0,0.2)",
          border: "1px solid #274472",
        }}
      >
        <h1
          style={{ fontSize: "1.8rem", marginBottom: "1rem", color: "#f5a623" }}
        >
          📤 {t("upload_document")}
        </h1>

        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: "1.2rem" }}>
            <label
              style={{
                display: "block",
                marginBottom: "0.5rem",
                color: "#ededed",
              }}
            >
              📎 {t("select_file_label")}
            </label>
            <input
              type="file"
              accept=".pdf,.txt"
              onChange={(e) => setFile(e.target.files[0])}
              disabled={limitReached}
              style={{
                width: "100%",
                padding: "0.4rem",
                backgroundColor: "#0f1c2e",
                border: "1px solid #4a90e2",
                color: "white",
                borderRadius: "8px",
                cursor: limitReached ? "not-allowed" : "pointer",
              }}
            />
          </div>

          <button
            type="submit"
            disabled={limitReached}
            style={{
              backgroundColor: limitReached ? "#777" : "#4a90e2",
              padding: "0.7rem 1.2rem",
              color: "white",
              borderRadius: "8px",
              fontWeight: "bold",
              border: "none",
              cursor: limitReached ? "not-allowed" : "pointer",
              transition: "background 0.3s ease",
            }}
          >
            {t("upload_file")}
          </button>
        </form>

        {message && (
          <p
            style={{ marginTop: "1rem", fontWeight: "500", color: "#a3d9b1" }}
          >
            {message}
          </p>
        )}

        {uploadedFiles.length > 0 && (
          <div style={{ marginTop: "2rem" }}>
            <h3 style={{ color: "#f5a623", marginBottom: "0.75rem" }}>
              📂 {t("uploaded_files")}
            </h3>
            <ul style={{ listStyleType: "none", paddingLeft: 0 }}>
              {uploadedFiles.map((file, idx) => (
                <li
                  key={idx}
                  style={{
                    marginBottom: "0.8rem",
                    color: "#ededed",
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                  }}
                >
                  <span>
                    📄 {file.name} – {file.size_kb} KB
                  </span>
                  <button
                    onClick={() => handleDelete(file.storage_path)}
                    style={{
                      backgroundColor: "#e74c3c",
                      padding: "0.4rem 0.8rem",
                      color: "white",
                      borderRadius: "6px",
                      border: "none",
                      cursor: "pointer",
                      fontWeight: "bold",
                    }}
                  >
                    🗑️ {t("delete")}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}
