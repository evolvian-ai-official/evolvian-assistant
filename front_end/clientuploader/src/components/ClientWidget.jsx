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
    <div style={{
      width: "100%",
      height: "100%",
      backgroundColor: "#ffffff"
    }}>
      <ChatWidget clientId={clientId} />
    </div>
  );
}
