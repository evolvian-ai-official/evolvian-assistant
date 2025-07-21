import React from "react";
import ReactDOM from "react-dom/client";
import ChatWidget from "./components/ChatWidget";
import { LanguageProvider } from "./contexts/LanguageContext";

const params = new URLSearchParams(window.location.search);
const clientId = params.get("public_client_id");

const rootElement = document.getElementById("root");

if (!clientId || !rootElement) {
  console.error("❌ No se pudo inicializar el widget. Faltan parámetros o contenedor.");
} else {
  ReactDOM.createRoot(rootElement).render(
    <LanguageProvider>
      <ChatWidget clientId={clientId} />
    </LanguageProvider>
  );
}
/*hh*/