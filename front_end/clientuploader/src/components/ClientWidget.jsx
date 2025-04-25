// src/components/ClientWidget.jsx
import { useEffect, useState } from "react";
import ChatWidget from "./ChatWidget";

export default function ClientWidget() {
  const [clientId, setClientId] = useState("");

  useEffect(() => {
    const urlParams = new URLSearchParams(window.location.search);
    const id = urlParams.get("client_id");
    if (id) setClientId(id);
  }, []);

  if (!clientId) return <p style={{ padding: "1rem" }}>❌ Client ID no encontrado.</p>;

  return (
    <div style={{
      width: "100%",
      height: "100%",
      backgroundColor: "#ffffff"
    }}>
      <ChatWidget clientId={clientId} />
    </div>
  );
}
