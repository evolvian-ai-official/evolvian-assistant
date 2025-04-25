import React from "react";
import ReactDOM from "react-dom/client";
import ChatWidget from "./ChatWidget";

const clientId = "demo-client-id"; // puedes cambiarlo dinámicamente si lo deseas

const rootElement = document.getElementById("root");

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
