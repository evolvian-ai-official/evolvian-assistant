import React from "react";
import ReactDOM from "react-dom/client";
import ChatWidget from "./ChatWidget";

const container = document.getElementById("evolvian-chat-widget");
const clientId = container?.dataset?.clientId;

// ✅ Asegurar tamaño mínimo si no está definido
if (container && (!container.style.height || container.style.height === "0px")) {
  container.style.height = "500px";
}
if (container && (!container.style.width || container.style.width === "0px")) {
  container.style.width = "320px";
}

// ✅ Forzar fondo blanco del contenedor del widget (por seguridad)
if (container) {
  container.style.backgroundColor = "#ffffff";
  container.style.border = "none";
  container.style.boxShadow = "none";
  container.style.overflow = "hidden";
}

if (container && clientId) {
  ReactDOM.createRoot(container).render(
    <ChatWidget clientId={clientId} />
  );
} else {
  console.error("❌ Evolvian Widget: No se encontró container o clientId");
}
