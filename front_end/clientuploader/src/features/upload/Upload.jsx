import { useState, useEffect } from "react";
import { useClientId } from "../../hooks/useClientId";

export default function Upload() {
  const [file, setFile] = useState(null);
  const [message, setMessage] = useState("");
  const [uploadedFiles, setUploadedFiles] = useState([]);
  const [limitReached, setLimitReached] = useState(false);
  const clientId = useClientId();

  const fetchFiles = async () => {
    if (!clientId) return;
    try {
      const res = await fetch(`http://localhost:8000/list_files?client_id=${clientId}`);
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
      setMessage("❌ No se puede subir archivo: client_id inválido.");
      return;
    }

    if (!file) {
      setMessage("⚠️ Por favor selecciona un archivo.");
      return;
    }

    const formData = new FormData();
    formData.append("client_id", clientId);
    formData.append("file", file);

    try {
      const res = await fetch("http://localhost:8000/upload", {
        method: "POST",
        body: formData,
      });

      if (res.status === 403) {
        const errorData = await res.json();
        setLimitReached(true);
        throw new Error(errorData.error || "Has alcanzado el límite de tu plan.");
      }

      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.error || "Error desconocido al subir archivo.");
      }

      const data = await res.json();
      setMessage(`✅ ${data.message}`);
      setFile(null);
      fetchFiles();
    } catch (err) {
      console.error("❌ Error al subir archivo:", err);
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
        <h1 style={{ fontSize: "1.8rem", marginBottom: "1rem", color: "#f5a623" }}>
          📤 Subir Documento
        </h1>

        {limitReached && (
          <p style={{ color: "#f87171", marginBottom: "1rem", fontWeight: "bold" }}>
            🚫 Has alcanzado el límite de documentos permitidos en tu plan actual.
          </p>
        )}

        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: "1.2rem" }}>
            <label style={{ display: "block", marginBottom: "0.5rem", color: "#ededed" }}>
              📎 Archivo (.pdf o .txt):
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
            Subir archivo
          </button>
        </form>

        {message && (
          <p style={{ marginTop: "1rem", fontWeight: "500", color: "#a3d9b1" }}>{message}</p>
        )}

        {uploadedFiles.length > 0 && (
          <div style={{ marginTop: "2rem" }}>
            <h3 style={{ color: "#f5a623", marginBottom: "0.75rem" }}>📂 Archivos subidos:</h3>
            <ul style={{ listStyleType: "none", paddingLeft: 0 }}>
              {uploadedFiles.map((file, idx) => (
                <li key={idx} style={{ marginBottom: "0.5rem", color: "#ededed" }}>
                  📄 {file}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}
