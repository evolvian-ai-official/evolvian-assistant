import { useEffect, useState } from "react";

export default function ChatSetup() {
  const [clientId, setClientId] = useState("");

  useEffect(() => {
    const storedId = localStorage.getItem("client_id");
    if (storedId) setClientId(storedId);
  }, []);

  const handleCopyId = () => {
    if (clientId) {
      navigator.clipboard.writeText(clientId);
      alert("✅ Tu client_id ha sido copiado: " + clientId);
    }
  };

  const handleCopyCode = (text) => {
    navigator.clipboard.writeText(text);
    alert("📋 Código copiado al portapapeles");
  };

  const iframeCode = `<iframe
  src="https://evolvian.app/widget?client_id=${clientId || "TU_CLIENT_ID"}"
  style="
    width: 360px;
    height: 520px;
    border: 2px solid #4a90e2;
    border-radius: 16px;
    background-color: #ededed;
    box-shadow: 0 6px 24px rgba(0, 0, 0, 0.15);
    position: fixed;
    bottom: 20px;
    right: 20px;
    z-index: 9999;"
  allow="clipboard-write; microphone"
  title="Evolvian AI Chat Widget"
></iframe>`;

  const scriptCode = `<script>
  (function () {
    const iframe = document.createElement("iframe");
    iframe.src = "https://evolvian.app/widget?client_id=${clientId || "TU_CLIENT_ID"}";
    iframe.style.position = "fixed";
    iframe.style.bottom = "20px";
    iframe.style.right = "20px";
    iframe.style.width = "360px";
    iframe.style.height = "520px";
    iframe.style.border = "2px solid #4a90e2";
    iframe.style.borderRadius = "16px";
    iframe.style.backgroundColor = "#ededed";
    iframe.style.boxShadow = "0 6px 24px rgba(0,0,0,0.15)";
    iframe.style.zIndex = "9999";
    iframe.setAttribute("title", "Evolvian AI Widget");
    iframe.setAttribute("allow", "clipboard-write; microphone");
    document.body.appendChild(iframe);
  })();
</script>`;

  return (
    <div
      style={{
        padding: "2rem 3rem",
        fontFamily: "system-ui, sans-serif",
        backgroundColor: "#0f1c2e",
        color: "#ffffff",
        minHeight: "100vh",
      }}
    >
      <div style={{ maxWidth: "1400px", margin: "0 auto" }}>
        <h2 style={{ fontSize: "2rem", color: "#f5a623", fontWeight: "bold", marginBottom: "1rem" }}>
          🧠 Configurar Chat Assistant
        </h2>

        <p style={{ color: "#ffffff", maxWidth: "700px", marginBottom: "2rem" }}>
          Puedes integrar el asistente de Evolvian AI en tu sitio web de dos maneras. A continuación te mostramos las instrucciones y el código para que lo pegues directamente en tu página:
        </p>

        {/* Client ID Box */}
        <div
          style={{
            backgroundColor: "#1b2a41",
            padding: "1rem",
            borderRadius: "12px",
            marginBottom: "2rem",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            maxWidth: "600px",
          }}
        >
          <div>
            <strong>Tu Client ID:</strong>{" "}
            <span style={{ color: "#a3d9b1" }}>{clientId || "No disponible"}</span>
          </div>
          <button
            onClick={handleCopyId}
            disabled={!clientId}
            style={{
              backgroundColor: "#4a90e2",
              color: "white",
              border: "none",
              borderRadius: "8px",
              padding: "0.5rem 1rem",
              fontWeight: "bold",
              cursor: clientId ? "pointer" : "not-allowed",
              opacity: clientId ? 1 : 0.5,
            }}
          >
            Copiar ID
          </button>
        </div>

        {/* Opciones lado a lado */}
        <div style={{ display: "flex", gap: "2rem", flexWrap: "wrap" }}>
          {/* IFRAME */}
          <div style={{ flex: 1, backgroundColor: "#1b2a41", padding: "1.5rem", borderRadius: "12px" }}>
            <h3 style={{ color: "#f5a623", fontSize: "1.2rem", marginBottom: "0.75rem" }}>
              🔹 Opción 1: IFRAME embebido
            </h3>
            <p>Inserta el chat como una sección fija dentro de tu página web.</p>
            <p style={{ fontSize: "0.85rem", color: "#a3d9b1", marginBottom: "1rem" }}>
              💡 Ideal para: sitios con CMS (WordPress, Wix, Shopify)
            </p>
            <ol style={{ fontSize: "0.85rem", marginBottom: "1rem" }}>
              <li>1. Copia el siguiente código.</li>
              <li>2. Tu ID ya está insertado.</li>
              <li>3. Pégalo antes del cierre <code>&lt;/body&gt;</code>.</li>
            </ol>
            <pre
              style={{
                background: "#ededed",
                color: "#274472",
                padding: "1rem",
                borderRadius: "8px",
                fontSize: "0.75rem",
                overflowX: "auto",
                marginBottom: "0.5rem",
              }}
            >
              {iframeCode}
            </pre>
            <button
              onClick={() => handleCopyCode(iframeCode)}
              style={{
                backgroundColor: "#f5a623",
                color: "#1b2a41",
                border: "none",
                borderRadius: "8px",
                padding: "0.5rem 1rem",
                fontWeight: "bold",
                fontSize: "0.85rem",
                cursor: "pointer",
              }}
            >
              Copiar código IFRAME
            </button>
          </div>

          {/* SCRIPT */}
          <div style={{ flex: 1, backgroundColor: "#1b2a41", padding: "1.5rem", borderRadius: "12px" }}>
            <h3 style={{ color: "#f5a623", fontSize: "1.2rem", marginBottom: "0.75rem" }}>
              🔹 Opción 2: SCRIPT con inserción automática
            </h3>
            <p>Este método inserta automáticamente el chat en la esquina inferior derecha.</p>
            <p style={{ fontSize: "0.85rem", color: "#a3d9b1", marginBottom: "1rem" }}>
              💡 Ideal para: desarrolladores o acceso directo al código HTML
            </p>
            <ol style={{ fontSize: "0.85rem", marginBottom: "1rem" }}>
              <li>1. Copia el siguiente script.</li>
              <li>2. Tu ID ya está insertado.</li>
              <li>3. Pégalo antes del cierre <code>&lt;/body&gt;</code>.</li>
            </ol>
            <pre
              style={{
                background: "#ededed",
                color: "#274472",
                padding: "1rem",
                borderRadius: "8px",
                fontSize: "0.75rem",
                overflowX: "auto",
                marginBottom: "0.5rem",
              }}
            >
              {scriptCode}
            </pre>
            <button
              onClick={() => handleCopyCode(scriptCode)}
              style={{
                backgroundColor: "#f5a623",
                color: "#1b2a41",
                border: "none",
                borderRadius: "8px",
                padding: "0.5rem 1rem",
                fontWeight: "bold",
                fontSize: "0.85rem",
                cursor: "pointer",
              }}
            >
              Copiar código SCRIPT
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
