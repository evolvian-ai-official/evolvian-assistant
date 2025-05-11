import React from "react";
import ReactDOM from "react-dom/client";
import ChatWidget from "./ChatWidget";

// ✅ Obtener clientId dinámicamente desde la URL
const params = new URLSearchParams(window.location.search);
const clientId = params.get("public_client_id");

const rootElement = document.getElementById("root");

// ✅ Validar que existe clientId y rootElement
if (!clientId || !rootElement) {
  console.error("❌ No se pudo inicializar el widget. Faltan parámetros o contenedor.");
} else {
  // ✅ Aseguramos el fondo blanco del contenedor
  rootElement.style.backgroundColor = "#ffffff";
  rootElement.style.height = "100%";
  rootElement.style.margin = "0";
  rootElement.style.padding = "0";
  rootElement.style.overflow = "hidden";
  rootElement.style.display = "flex";
  rootElement.style.justifyContent = "center";
  rootElement.style.alignItems = "center";

  ReactDOM.createRoot(rootElement).render(
    <ChatWidget clientId={clientId} />
  );
}
