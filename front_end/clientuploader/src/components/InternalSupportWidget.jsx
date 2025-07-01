// src/components/InternalSupportWidget.jsx
import { useState } from "react";
import ChatWidget from "./ChatWidget";
import { INTERNAL_PUBLIC_CLIENT_ID } from "../constants/clientIds"; // ✅ (crear este archivo)

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
          backgroundColor: "#4a90e2",
          color: "white",
          borderRadius: "50%",
          width: "48px",
          height: "48px",
          border: "none",
          fontSize: "20px",
          cursor: "pointer",
        }}
      >
        {isOpen ? "×" : "💬"}
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
