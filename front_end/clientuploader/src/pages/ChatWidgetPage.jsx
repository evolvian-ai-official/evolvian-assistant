// src/pages/ChatWidgetPage.jsx - ESTA ES EL IFRAME
import { useSearchParams } from "react-router-dom";
import ChatWidget from "../components/ChatWidget";

export default function ChatWidgetPage() {
  const [searchParams] = useSearchParams();
  const publicClientId = searchParams.get("public_client_id"); // ✅ CAMBIO

  if (!publicClientId) {
    return (
      <div
        style={{
          padding: "2rem",
          fontFamily: "system-ui, sans-serif",
          color: "#e74c3c",
          textAlign: "center",
        }}
      >
        ⚠️ No se proporcionó un public_client_id.
      </div>
    );
  }

  return (
    <div
      style={{
        margin: 0,
        boxSizing: "border-box",
        width: "100vw",
        height: "100dvh",
        paddingTop: "calc(env(safe-area-inset-top, 0px) + 0.5rem)",
        paddingRight: "calc(env(safe-area-inset-right, 0px) + 0.5rem)",
        paddingBottom: "calc(env(safe-area-inset-bottom, 0px) + 0.5rem)",
        paddingLeft: "calc(env(safe-area-inset-left, 0px) + 0.5rem)",
        backgroundColor: "#ededed",
        fontFamily: "system-ui, sans-serif",
        display: "flex",
        justifyContent: "center",
        alignItems: "center",
      }}
    >
      <div
        style={{
          width: "min(100%, 420px)",
          height: "min(100%, 680px)",
          backgroundColor: "#ffffff",
          border: "1px solid #4a90e2",
          borderRadius: "clamp(12px, 2.5vw, 16px)",
          boxShadow: "0 6px 24px rgba(0,0,0,0.15)",
          overflow: "hidden",
        }}
      >
        <ChatWidget clientId={publicClientId} /> {/* ✅ CAMBIO */}
      </div>
    </div>
  );
}
