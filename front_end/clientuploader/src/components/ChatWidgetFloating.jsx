import { useState } from "react";
import ChatWidget from "./ChatWidget";
import { useClientId } from "../hooks/useClientId";

export default function ChatWidgetFloating() {
  const clientId = useClientId();
  const [isOpen, setIsOpen] = useState(false);

  if (!clientId) return null;

  return (
    <>
      {/* Botón flotante para abrir/cerrar */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        style={{
          position: "fixed",
          bottom: "24px",
          right: isOpen ? "384px" : "24px", // corre el botón si está abierto
          zIndex: 10000,
          backgroundColor: "#4a90e2",
          color: "white",
          border: "none",
          borderRadius: "50%",
          width: "48px",
          height: "48px",
          fontSize: "20px",
          cursor: "pointer",
          boxShadow: "0 4px 12px rgba(0, 0, 0, 0.2)",
        }}
        title={isOpen ? "Cerrar asistente" : "Abrir asistente"}
      >
        {isOpen ? "×" : "💬"}
      </button>

      {/* Widget visible solo si isOpen */}
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
