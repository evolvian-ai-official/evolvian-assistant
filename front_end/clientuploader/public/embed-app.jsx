import React from "react";
import ReactDOM from "react-dom/client";
import ChatWidget from "./ChatWidget";

// ✅ Obtener public_client_id desde la URL
const params = new URLSearchParams(window.location.search);
const publicClientId = params.get("public_client_id");

const container = document.getElementById("evolvian-chat-widget");

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

if (container && publicClientId) {
  ReactDOM.createRoot(container).render(
    <ChatWidget clientId={publicClientId} />
  );
} else {
  console.error("❌ Evolvian Widget: No se encontró container o public_client_id");
}
