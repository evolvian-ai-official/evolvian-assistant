// src/WidgetApp.jsx
import React from "react";
import ReactDOM from "react-dom/client";
import ChatWidget from "./components/ChatWidget";

const params = new URLSearchParams(window.location.search);
const clientId = params.get("public_client_id");

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <ChatWidget clientId={clientId} />
  </React.StrictMode>
);
