// src/components/ClientWidget.jsx es un wrapper simplificado que sirve para pruebas rápidas: detecta client_id o public_client_id en la URL y monta el chat ocupando todo el espacio disponible.
import { useEffect, useState } from "react";
import ChatWidget from "./ChatWidget";

export default function ClientWidget() {
  const [clientId, setClientId] = useState("");

  useEffect(() => {
    const urlParams = new URLSearchParams(window.location.search);
    const id = urlParams.get("client_id") || urlParams.get("public_client_id"); // ✅ Arreglado
    if (id) setClientId(id);
  }, []);

  if (!clientId) return <p style={{ padding: "1rem" }}>❌ Client ID no encontrado.</p>;

  return (
    <div
      style={{
        width: "100%",
        minHeight: "100dvh",
        boxSizing: "border-box",
        paddingTop: "env(safe-area-inset-top, 0px)",
        paddingRight: "env(safe-area-inset-right, 0px)",
        paddingBottom: "env(safe-area-inset-bottom, 0px)",
        paddingLeft: "env(safe-area-inset-left, 0px)",
        backgroundColor: "#ffffff",
      }}
    >
      <ChatWidget clientId={clientId} />
    </div>
  );
}
