// src/widget-app.jsx
import React from "react";
import ReactDOM from "react-dom/client";
import ChatWidget from "./components/ChatWidget";

// ✅ Detecta client_id desde query params (?public_client_id=xxxx)
function getClientIdFromQuery() {
  const params = new URLSearchParams(window.location.search);
  return params.get("public_client_id");
}

const clientId = getClientIdFromQuery() || "default-client";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <ChatWidget
      clientId={clientId}
      requireEmail={false}
      requirePhone={false}
      requireTerms={false}
      assistantName="Evolvian Assistant"
      showPoweredBy={true}
    />
  </React.StrictMode>
);