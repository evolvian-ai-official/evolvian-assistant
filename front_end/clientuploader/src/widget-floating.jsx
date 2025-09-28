import React from "react";
import ReactDOM from "react-dom/client";
import ChatWidgetFloating from "./components/ChatWidgetFloating";

const clientId = document.currentScript.getAttribute("public_client_id");

if (!clientId) {
  console.error("❌ Evolvian Floating: public_client_id no encontrado");
} else {
  const container = document.createElement("div");
  container.id = "evolvian-floating-widget";
  document.body.appendChild(container);

  ReactDOM.createRoot(container).render(
    <ChatWidgetFloating clientId={clientId} />
  );
}
