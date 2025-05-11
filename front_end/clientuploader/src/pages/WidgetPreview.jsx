// src/pages/WidgetPreview.jsx
import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import ChatWidget from "../components/ChatWidget";

export default function WidgetPreview() {
  const [searchParams] = useSearchParams();
  const publicClientId = searchParams.get("public_client_id"); // ✅ CORREGIDO

  const [settings, setSettings] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!publicClientId) {
      console.warn("⚠️ No se encontró public_client_id en la URL");
      return;
    }

    const fetchSettings = async () => {
      try {
        const res = await fetch(`${import.meta.env.VITE_API_URL}/client_settings?public_client_id=${publicClientId}`); // ✅
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
  }, [publicClientId]);

  if (!publicClientId) return <p>❌ No hay public_client_id en la URL. Usa <code>?public_client_id=...</code></p>;
  if (loading) return <p>🔄 Cargando configuración del cliente...</p>;
  if (!settings) return <p>⚠️ No se pudo cargar la configuración del asistente.</p>;

  return (
    <div style={{ height: "100vh", padding: "1rem", fontFamily: "sans-serif" }}>
      <ChatWidget
        clientId={publicClientId} // ✅
        requireEmail={settings.require_email}
        requirePhone={settings.require_phone}
        requireTerms={settings.require_terms}
      />
    </div>
  );
}
