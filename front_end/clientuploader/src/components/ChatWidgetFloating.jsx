import { useState } from "react";
import ChatWidget from "./ChatWidget";
import { useClientId } from "../hooks/useClientId";

export default function ChatWidgetFloating() {
  const clientId = useClientId();
  const [isOpen, setIsOpen] = useState(false);

  if (!clientId) return null;

  return (
    <>
      {/* Botón flotante */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        style={{
          position: "fixed",
          bottom: "24px",
          right: isOpen ? "384px" : "24px",
          zIndex: 10000,
          backgroundColor: "#ffffff",
          border: "none",
          borderRadius: "50%",
          width: "56px",
          height: "56px",
          padding: "6px",
          cursor: "pointer",
          boxShadow: "0 4px 12px rgba(0, 0, 0, 0.2)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
        title={isOpen ? "Cerrar asistente" : "Abrir asistente"}
      >
        {isOpen ? (
          <span style={{ fontSize: "28px", color: "#4a90e2" }}>×</span>
        ) : (
          <img
            src="/logo-evolvian.svg"
            alt="Evolvian"
            style={{
              width: "36px",
              height: "36px",
              borderRadius: "50%",
              objectFit: "cover",
            }}
          />
        )}
      </button>

      {/* Contenedor del widget */}
      {isOpen && (
        <div style={styles.container}>
          <ChatWidget clientId={clientId} />
        </div>
      )}
    </>
  );
}

const styles = {
  container: {
    position: "fixed",
    bottom: "24px",
    right: "24px",
    width: "360px",
    height: "500px",
    zIndex: 9999,
    borderRadius: "16px",
    overflow: "hidden",
    backgroundColor: "#ffffff",
    boxShadow: "0 6px 24px rgba(0, 0, 0, 0.15)",
  },
};
