// src/components/InternalSupportWidget.jsx
import { useEffect, useState } from "react";
import ChatWidget from "./ChatWidget";
import { INTERNAL_PUBLIC_CLIENT_ID } from "../constants/clientIds";

export default function InternalSupportWidget() {
  const [isOpen, setIsOpen] = useState(false);
  const [isMobile, setIsMobile] = useState(() =>
    typeof window !== "undefined"
      ? window.matchMedia("(max-width: 768px)").matches
      : false
  );
  const publicClientId = INTERNAL_PUBLIC_CLIENT_ID;

  useEffect(() => {
    if (typeof window === "undefined") return undefined;
    const mediaQuery = window.matchMedia("(max-width: 768px)");
    const onChange = (event) => setIsMobile(event.matches);

    setIsMobile(mediaQuery.matches);
    if (mediaQuery.addEventListener) {
      mediaQuery.addEventListener("change", onChange);
      return () => mediaQuery.removeEventListener("change", onChange);
    }
    mediaQuery.addListener(onChange);
    return () => mediaQuery.removeListener(onChange);
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") return undefined;
    const onOpenSupport = () => setIsOpen(true);
    window.addEventListener("evolvian:open-support-widget", onOpenSupport);
    return () => window.removeEventListener("evolvian:open-support-widget", onOpenSupport);
  }, []);

  return (
    <>
      <button
        onClick={() => setIsOpen(!isOpen)}
        style={{
          position: "fixed",
          bottom: "calc(env(safe-area-inset-bottom, 0px) + 16px)",
          right: isMobile
            ? "calc(env(safe-area-inset-right, 0px) + 12px)"
            : isOpen
            ? "392px"
            : "24px",
          zIndex: 10000,
          borderRadius: "50%",
          width: isMobile ? "56px" : "64px",
          height: isMobile ? "56px" : "64px",
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
        <div style={isMobile ? styles.mobileContainer : styles.container}>
          <ChatWidget clientId={publicClientId} />
        </div>
      )}
    </>
  );
}

const styles = {
  container: {
    position: "fixed",
    bottom: "calc(env(safe-area-inset-bottom, 0px) + 24px)",
    right: "24px",
    width: "360px",
    height: "500px",
    backgroundColor: "#ffffff",
    borderRadius: "16px",
    boxShadow: "0 6px 24px rgba(0,0,0,0.2)",
    zIndex: 9999,
    overflow: "hidden",
  },
  mobileContainer: {
    position: "fixed",
    top: "calc(env(safe-area-inset-top, 0px) + 10px)",
    right: "calc(env(safe-area-inset-right, 0px) + 10px)",
    bottom: "calc(env(safe-area-inset-bottom, 0px) + 74px)",
    left: "calc(env(safe-area-inset-left, 0px) + 10px)",
    backgroundColor: "#ffffff",
    borderRadius: "14px",
    boxShadow: "0 6px 24px rgba(0,0,0,0.2)",
    zIndex: 9999,
    overflow: "hidden",
  },
};
