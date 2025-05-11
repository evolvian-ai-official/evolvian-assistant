<script>
(function () {
  const clientId = document.currentScript.getAttribute("data-client-id");

  if (!clientId) {
    console.warn("❌ No se proporcionó data-client-id al script de Evolvian.");
    return;
  }

  // 🌐 Base URL definida por entorno
  const isLocalhost =
    window.location.hostname.includes("localhost") ||
    window.location.hostname.includes("127.0.0.1");

  const baseUrl = isLocalhost
    ? "http://localhost:5173" // Desarrollo local
    : "https://clientuploader.onrender.com"; // Producción

  console.log("🌐 Evolvian Widget baseUrl:", baseUrl);
  console.log("📦 public_client_id:", clientId);

  // Crear contenedor flotante
  const wrapper = document.createElement("div");
  wrapper.id = "evolvian-widget-wrapper";
  Object.assign(wrapper.style, {
    position: "fixed",
    bottom: "20px",
    right: "20px",
    zIndex: "9999",
    display: "flex",
    flexDirection: "column",
    alignItems: "flex-end",
  });
  document.body.appendChild(wrapper);

  // Crear botón flotante
  const button = document.createElement("button");
  button.innerText = "💬";
  button.title = "Chatea con Evolvian";
  Object.assign(button.style, {
    backgroundColor: "#4a90e2",
    color: "white",
    fontSize: "24px",
    border: "none",
    borderRadius: "50%",
    width: "56px",
    height: "56px",
    cursor: "pointer",
    boxShadow: "0 4px 8px rgba(0,0,0,0.3)",
    transition: "all 0.3s ease",
  });
  wrapper.appendChild(button);

  // Crear contenedor del iframe
  const widgetContainer = document.createElement("div");
  widgetContainer.id = "evolvian-chat-widget";
  Object.assign(widgetContainer.style, {
    display: "none",
    marginTop: "10px",
    width: "400px",
    height: "500px",
    border: "none",
    borderRadius: "12px",
    boxShadow: "0 4px 12px rgba(0,0,0,0.2)",
    overflow: "hidden",
    background: "white",
  });
  wrapper.appendChild(widgetContainer);

  // Mostrar/ocultar widget
  let visible = false;
  button.addEventListener("click", () => {
    visible = !visible;
    widgetContainer.style.display = visible ? "block" : "none";
  });

  // Crear iframe
  const iframe = document.createElement("iframe");
  iframe.src = `${baseUrl}/chat-widget?public_client_id=${clientId}`;
  Object.assign(iframe.style, {
    width: "100%",
    height: "100%",
    border: "none",
    borderRadius: "12px",
  });
  iframe.setAttribute("title", "Evolvian AI Widget");
  iframe.setAttribute("allow", "clipboard-write; microphone");
  iframe.setAttribute("loading", "lazy");

  widgetContainer.appendChild(iframe);
})();
</script>
