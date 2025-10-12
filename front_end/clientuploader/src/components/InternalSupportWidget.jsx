// src/components/InternalSupportWidget.jsx
import { useState } from "react";
import ChatWidget from "./ChatWidget";
import { INTERNAL_PUBLIC_CLIENT_ID } from "../constants/clientIds";

export default function InternalSupportWidget() {
  const [isOpen, setIsOpen] = useState(false);
  const publicClientId = INTERNAL_PUBLIC_CLIENT_ID;

  return (
    <>
      <button
        onClick={() => setIsOpen(!isOpen)}
        style={{
          position: "fixed",
          bottom: isOpen ? "540px" : "24px",
          right: "24px",
          zIndex: 10000,
          borderRadius: "50%",
          width: "64px",
          height: "64px",
          border: "none",
          cursor: "pointer",
          overflow: "hidden", // ✅ asegura que el logo se mantenga redondo
          padding: 0,
        }}
      >
        {isOpen ? (
          <span style={{ fontSize: "32px", color: "white", background: "#4a90e2", width: "100%", height: "100%", display: "flex", alignItems: "center", justifyContent: "center" }}>
            ×
          </span>
        ) : (
          <img
            src="/e1.png"
            alt="Evolvian Logo"
            style={{
              width: "100%",
              height: "100%",
              objectFit: "cover", // ✅ el logo llena el círculo
              borderRadius: "50%",
            }}
          />
        )}
      </button>

      {isOpen && (
        <div style={styles.container}>
          <ChatWidget clientId={publicClientId} />
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
    backgroundColor: "#ffffff",
    borderRadius: "16px",
    boxShadow: "0 6px 24px rgba(0,0,0,0.2)",
    zIndex: 9999,
    overflow: "hidden",
  },
};
