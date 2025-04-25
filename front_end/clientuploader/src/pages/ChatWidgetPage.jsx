import { useSearchParams } from "react-router-dom";
import ChatWidget from "../components/ChatWidget";

export default function ChatWidgetPage() {
  const [searchParams] = useSearchParams();
  const clientId = searchParams.get("client_id");

  if (!clientId) {
    return (
      <div
        style={{
          padding: "2rem",
          fontFamily: "system-ui, sans-serif",
          color: "#e74c3c",
          textAlign: "center",
        }}
      >
        ⚠️ No se proporcionó un client_id.
      </div>
    );
  }

  return (
    <div
      style={{
        margin: 0,
        padding: 0,
        width: "100vw",
        height: "100vh",
        backgroundColor: "#ededed",
        fontFamily: "system-ui, sans-serif",
        display: "flex",
        justifyContent: "center",
        alignItems: "center",
      }}
    >
      <div
        style={{
          width: "360px",
          height: "520px",
          backgroundColor: "#ffffff",
          border: "2px solid #4a90e2",
          borderRadius: "16px",
          boxShadow: "0 6px 24px rgba(0,0,0,0.15)",
          overflow: "hidden",
        }}
      >
        <ChatWidget clientId={clientId} />
      </div>
    </div>
  );
}