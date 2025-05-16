// src/WidgetApp.jsx
import React from "react";
import ReactDOM from "react-dom/client";
import ChatWidget from "./components/ChatWidget";
import { LanguageProvider } from "./contexts/LanguageContext"; // ✅ Ajusta la ruta si es distinta

const params = new URLSearchParams(window.location.search);
const clientId = params.get("public_client_id");

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <LanguageProvider>
      <ChatWidget clientId={clientId} />
    </LanguageProvider>
  </React.StrictMode>
);
