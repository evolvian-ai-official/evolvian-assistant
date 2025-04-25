// src/pages/WidgetPreview.jsx
import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import ChatWidget from "../components/ChatWidget";

export default function WidgetPreview() {
  const [searchParams] = useSearchParams();
  const clientId = searchParams.get("client_id");

  const [settings, setSettings] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!clientId) {
      console.warn("⚠️ No se encontró client_id en la URL");
      return;
    }

    const fetchSettings = async () => {
      try {
        const res = await fetch(`http://localhost:8000/client_settings?client_id=${clientId}`);
        const data = await res.json();
        console.log("⚙️ Settings cargados desde backend (crudo):\n", JSON.stringify(data, null, 2));

        const extracted = data?.settings || data;
        console.log("📌 Usando configuración extraída:", extracted);

        setSettings(extracted);
      } catch (err) {
        console.error("❌ Error al obtener settings:", err);
      } finally {
        setLoading(false);
      }
    };

    fetchSettings();
  }, [clientId]);

  if (!clientId) return <p>❌ No hay client_id en la URL. Usa <code>?client_id=...</code></p>;
  if (loading) return <p>🔄 Cargando configuración del cliente...</p>;
  if (!settings) return <p>⚠️ No se pudo cargar la configuración del asistente.</p>;

  return (
    <div style={{ height: "100vh", padding: "1rem", fontFamily: "sans-serif" }}>
      <ChatWidget
        clientId={clientId}
        requireEmail={settings.require_email}
        requirePhone={settings.require_phone}
        requireTerms={settings.require_terms}
      />
    </div>
  );
}
