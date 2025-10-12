import React from "react";
import ReactDOM from "react-dom/client";
import ChatWidget from "./components/ChatWidget"; // 👈 ajusta la ruta si es diferente
import { LanguageProvider } from "./contexts/LanguageContext"; // 👈 ajusta la ruta si es diferente

// 🚀 Obtener clientId desde la query string (?public_client_id=xxx)
const params = new URLSearchParams(window.location.search);
const clientId = params.get("public_client_id");

// 🚀 Elemento root donde se inyectará el widget
const rootElement = document.getElementById("root");

if (!clientId) {
  console.error("❌ Evolvian Iframe: public_client_id no encontrado en la query string");
} else if (!rootElement) {
  console.error("❌ Evolvian Iframe: No se encontró #root en el documento");
} else {
  ReactDOM.createRoot(rootElement).render(
    <LanguageProvider>
      <ChatWidget clientId={clientId} />
    </LanguageProvider>
  );
}
