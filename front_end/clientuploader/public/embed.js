(function () {
  const clientId = document.currentScript.getAttribute("data-client-id");

  if (!clientId) {
    console.warn("❌ No se proporcionó data-client-id al script de Evolvian.");
    return;
  }

  // 🔧 Fuerza entorno local para pruebas
  const baseUrl = "http://localhost:5173"; // ✅ Solo para desarrollo

  // Crear wrapper flotante (👇 POSICIÓN DERECHA)
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

  // Crear contenedor del widget
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

  // Toggle visibilidad
  let visible = false;
  button.addEventListener("click", () => {
    visible = !visible;
    widgetContainer.style.display = visible ? "block" : "none";
  });

  // Insertar iframe del widget
  const iframe = document.createElement("iframe");
  iframe.src = `${baseUrl}/chat-widget?client_id=${clientId}`;
  console.log("📦 clientId en embed.js:", clientId);
  Object.assign(iframe.style, {
    width: "100%",
    height: "100%",
    border: "none",
    borderRadius: "12px",
  });
  widgetContainer.appendChild(iframe);
})();
