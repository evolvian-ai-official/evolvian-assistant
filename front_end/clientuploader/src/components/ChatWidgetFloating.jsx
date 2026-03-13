import { useEffect, useMemo, useState } from "react";
import ChatWidget from "./ChatWidget";

const CLOSE_ANIMATION_MS = 300;
const MOBILE_SHEET_CLOSE_THRESHOLD = 96;
const MOBILE_SHEET_MAX_DRAG = 220;
const MOBILE_HEADER_DRAG_ZONE = 84;
const DESKTOP_PANEL_HEIGHT = 500;

export default function ChatWidgetFloating({ publicClientId: propPublicClientId }) {
  const apiBaseUrl = getWidgetApiBaseUrl();
  const defaultLauncherIconUrl = getDefaultLauncherIconUrl(apiBaseUrl);
  const [isOpen, setIsOpen] = useState(false);
  const [shouldRenderPanel, setShouldRenderPanel] = useState(false);
  const [isMobile, setIsMobile] = useState(() =>
    typeof window !== "undefined"
      ? window.matchMedia("(max-width: 640px)").matches
      : false
  );
  const [prefersReducedMotion, setPrefersReducedMotion] = useState(false);
  const [isSheetDragging, setIsSheetDragging] = useState(false);
  const [sheetDragOffset, setSheetDragOffset] = useState(0);
  const [sheetDragStartY, setSheetDragStartY] = useState(null);
  const [launcherIconUrl, setLauncherIconUrl] = useState(defaultLauncherIconUrl);
  const params = new URLSearchParams(window.location.search);
  const urlPublicClientId = params.get("public_client_id");
  const publicClientId = propPublicClientId || urlPublicClientId;

  useEffect(() => {
    setLauncherIconUrl(defaultLauncherIconUrl);
  }, [defaultLauncherIconUrl]);

  useEffect(() => {
    if (typeof window === "undefined") return undefined;
    const mediaQuery = window.matchMedia("(max-width: 640px)");
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
    const mediaQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
    const onChange = (event) => setPrefersReducedMotion(event.matches);

    setPrefersReducedMotion(mediaQuery.matches);
    if (mediaQuery.addEventListener) {
      mediaQuery.addEventListener("change", onChange);
      return () => mediaQuery.removeEventListener("change", onChange);
    }

    mediaQuery.addListener(onChange);
    return () => mediaQuery.removeListener(onChange);
  }, []);

  useEffect(() => {
    if (isOpen) return undefined;
    if (!shouldRenderPanel) return undefined;

    const timeout = window.setTimeout(
      () => setShouldRenderPanel(false),
      prefersReducedMotion ? 0 : CLOSE_ANIMATION_MS
    );
    return () => window.clearTimeout(timeout);
  }, [isOpen, shouldRenderPanel, prefersReducedMotion]);

  useEffect(() => {
    if (!isOpen) return undefined;
    const onKeyDown = (event) => {
      if (event.key === "Escape") setIsOpen(false);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [isOpen]);

  useEffect(() => {
    const onMessage = (event) => {
      if (event?.data?.type === "EVOLVIAN_WIDGET_CLOSE") {
        setIsOpen(false);
      }
    };
    window.addEventListener("message", onMessage);
    return () => window.removeEventListener("message", onMessage);
  }, []);

  useEffect(() => {
    if (!publicClientId) return undefined;

    let cancelled = false;

    const fetchLauncherIcon = async () => {
      try {
        const response = await fetch(
          `${apiBaseUrl}/client_settings?public_client_id=${encodeURIComponent(publicClientId)}`
        );
        if (!response.ok) return;
        const data = await response.json();
        if (cancelled) return;
        const nextIconUrl = String(data?.launcher_icon_url || "").trim();
        setLauncherIconUrl(nextIconUrl || defaultLauncherIconUrl);
      } catch (error) {
        if (!cancelled) setLauncherIconUrl(defaultLauncherIconUrl);
        console.error("⚠️ Error loading floating widget icon:", error);
      }
    };

    fetchLauncherIcon();
    return () => {
      cancelled = true;
    };
  }, [apiBaseUrl, defaultLauncherIconUrl, publicClientId]);

  useEffect(() => {
    if (isOpen && isMobile) return;
    if (sheetDragOffset !== 0) setSheetDragOffset(0);
    if (isSheetDragging) setIsSheetDragging(false);
    if (sheetDragStartY !== null) setSheetDragStartY(null);
  }, [isOpen, isMobile, isSheetDragging, sheetDragOffset, sheetDragStartY]);

  const motionTransition = prefersReducedMotion
    ? "none"
    : "opacity 240ms ease, transform 300ms cubic-bezier(0.22, 1, 0.36, 1), clip-path 300ms cubic-bezier(0.22, 1, 0.36, 1)";
  const dragProgress = Math.min(Math.max(sheetDragOffset / MOBILE_SHEET_MAX_DRAG, 0), 1);

  const panelStyle = useMemo(() => {
    const base = isMobile ? styles.mobileContainer : styles.container;

    return {
      ...base,
      opacity: isOpen ? 1 : 0,
      pointerEvents: isOpen ? "auto" : "none",
      transform: isOpen
        ? isMobile
          ? `translateY(${sheetDragOffset}px) scale(${1 - dragProgress * 0.045})`
          : "translateY(0) scale(1)"
        : isMobile
        ? "translateY(16px) scale(0.94)"
        : "translateY(14px) scale(0.8)",
      clipPath: isOpen
        ? `inset(0% 0% 0% 0% round ${isMobile ? "14px" : "16px"})`
        : isMobile
        ? "circle(34px at calc(100% - 36px) calc(100% + 34px))"
        : "circle(32px at calc(100% - 36px) calc(100% + 10px))",
      transition: isSheetDragging ? "none" : motionTransition,
    };
  }, [dragProgress, isMobile, isOpen, isSheetDragging, motionTransition, sheetDragOffset]);

  const backdropStyle = useMemo(
    () => ({
      ...styles.backdrop,
      opacity: isOpen ? Math.max(0, 1 - dragProgress * 1.1) : 0,
      pointerEvents: isOpen ? "auto" : "none",
      transition: isSheetDragging
        ? "none"
        : prefersReducedMotion
        ? "none"
        : "opacity 220ms ease",
    }),
    [dragProgress, isOpen, isSheetDragging, prefersReducedMotion]
  );

  const openWidget = () => {
    setShouldRenderPanel(true);
    setIsOpen(true);
  };

  const closeWidget = () => {
    setIsOpen(false);
  };

  const onSheetTouchStart = (event) => {
    if (!isMobile || !isOpen) return;
    const touch = event.touches?.[0];
    if (!touch) return;
    const panelRect = event.currentTarget?.getBoundingClientRect?.();
    const localY = panelRect ? touch.clientY - panelRect.top : Number.POSITIVE_INFINITY;
    const interactiveSelector = "button, a, input, textarea, select, [role='button']";
    const touchedInteractive = event.target?.closest?.(interactiveSelector);

    if (localY > MOBILE_HEADER_DRAG_ZONE) return;
    if (touchedInteractive) return;

    setIsSheetDragging(true);
    setSheetDragStartY(touch.clientY);
  };

  const onSheetTouchMove = (event) => {
    if (!isSheetDragging || sheetDragStartY === null) return;
    const touch = event.touches?.[0];
    if (!touch) return;

    event.preventDefault();
    const deltaY = Math.max(0, touch.clientY - sheetDragStartY);
    setSheetDragOffset(Math.min(deltaY, MOBILE_SHEET_MAX_DRAG));
  };

  const onSheetTouchEnd = () => {
    if (!isSheetDragging) return;

    const shouldClose = sheetDragOffset >= MOBILE_SHEET_CLOSE_THRESHOLD;
    setIsSheetDragging(false);
    setSheetDragStartY(null);
    setSheetDragOffset(0);
    if (shouldClose) closeWidget();
  };

  const launcherStyle = useMemo(
    () => ({
      position: "fixed",
      bottom: "calc(env(safe-area-inset-bottom, 0px) + 16px)",
      right: isMobile
        ? "calc(env(safe-area-inset-right, 0px) + 12px)"
        : "24px",
      zIndex: 10000,
      background: "linear-gradient(135deg, #ffffff 0%, #f1f7ff 100%)",
      border: "1px solid rgba(32, 64, 112, 0.12)",
      borderRadius: "50%",
      width: isMobile ? "52px" : "56px",
      height: isMobile ? "52px" : "56px",
      padding: "6px",
      cursor: "pointer",
      boxShadow: "0 10px 22px rgba(21, 45, 79, 0.24)",
      transform: isOpen ? "scale(0.82)" : "scale(1)",
      opacity: isOpen ? 0 : 1,
      pointerEvents: isOpen ? "none" : "auto",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      backdropFilter: "blur(8px)",
      transition: prefersReducedMotion
        ? "none"
        : "opacity 180ms ease, transform 200ms ease, box-shadow 180ms ease",
    }),
    [isMobile, isOpen, prefersReducedMotion]
  );

  const closeButtonStyle = useMemo(
    () => ({
      position: "fixed",
      zIndex: 10001,
      width: isMobile ? 40 : 42,
      height: isMobile ? 40 : 42,
      borderRadius: 14,
      border: "1px solid rgba(31, 62, 105, 0.18)",
      background: "linear-gradient(155deg, rgba(255,255,255,0.96) 0%, rgba(241,247,255,0.92) 100%)",
      color: "#1f3e69",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      boxShadow: "0 12px 28px rgba(21, 45, 79, 0.26)",
      cursor: "pointer",
      backdropFilter: "blur(10px)",
      top: isMobile
        ? "calc(env(safe-area-inset-top, 0px) + 16px)"
        : "auto",
      right: isMobile
        ? "calc(env(safe-area-inset-right, 0px) + 16px)"
        : "calc(env(safe-area-inset-right, 0px) + 8px)",
      bottom: isMobile
        ? "auto"
        : `calc(env(safe-area-inset-bottom, 0px) + ${DESKTOP_PANEL_HEIGHT + 8}px)`,
      opacity: isOpen ? 1 : 0,
      transform: isOpen ? "scale(1)" : "scale(0.85)",
      pointerEvents: isOpen ? "auto" : "none",
      transition: prefersReducedMotion
        ? "none"
        : "opacity 180ms ease, transform 180ms ease, box-shadow 180ms ease",
    }),
    [isMobile, isOpen, prefersReducedMotion]
  );

  if (!publicClientId) return null;

  return (
    <>
      {shouldRenderPanel && <div style={backdropStyle} onClick={closeWidget} />}

      {shouldRenderPanel && (
        <div
          style={panelStyle}
          onTouchStart={onSheetTouchStart}
          onTouchMove={onSheetTouchMove}
          onTouchEnd={onSheetTouchEnd}
          onTouchCancel={onSheetTouchEnd}
        >
          {isMobile && (
            <div style={styles.mobileGrabZone} role="presentation">
              <div
                style={{
                  ...styles.mobileHandle,
                  opacity: Math.max(0.42, 1 - dragProgress),
                  transform: `translateX(-50%) scale(${1 - dragProgress * 0.08})`,
                }}
              />
            </div>
          )}
          <ChatWidget clientId={publicClientId} />
        </div>
      )}

      {/* Botón flotante */}
      <button
        onClick={openWidget}
        aria-expanded={isOpen}
        aria-label="Abrir asistente"
        style={launcherStyle}
        title="Abrir asistente"
      >
        <span
          style={{
            position: "absolute",
            width: "100%",
            height: "100%",
            borderRadius: "50%",
            boxShadow: "0 0 0 8px rgba(74, 144, 226, 0.08)",
            transition: prefersReducedMotion ? "none" : "box-shadow 240ms ease",
            pointerEvents: "none",
          }}
        />
        <img
          src={launcherIconUrl}
          alt="Evolvian"
          style={{
            width: "36px",
            height: "36px",
            borderRadius: "50%",
            objectFit: "cover",
          }}
          onError={() => {
            if (launcherIconUrl !== defaultLauncherIconUrl) {
              setLauncherIconUrl(defaultLauncherIconUrl);
            }
          }}
        />
      </button>

      <button
        type="button"
        onClick={closeWidget}
        aria-label="Cerrar asistente"
        style={closeButtonStyle}
        title="Cerrar asistente"
      >
        <span style={{ fontSize: 24, lineHeight: 1, fontWeight: 500 }}>×</span>
      </button>
    </>
  );
}

const styles = {
  backdrop: {
    position: "fixed",
    inset: 0,
    zIndex: 9997,
    background: "linear-gradient(180deg, rgba(10, 20, 36, 0.08) 0%, rgba(10, 20, 36, 0.22) 100%)",
    backdropFilter: "blur(3px)",
  },
  container: {
    position: "fixed",
    bottom: "calc(env(safe-area-inset-bottom, 0px) + 24px)",
    right: "24px",
    width: "360px",
    height: "500px",
    zIndex: 9999,
    borderRadius: "16px",
    overflow: "hidden",
    background: "rgba(255, 255, 255, 0.76)",
    border: "1px solid rgba(31, 62, 105, 0.14)",
    boxShadow: "0 20px 50px rgba(21, 45, 79, 0.28)",
    backdropFilter: "blur(12px)",
    transformOrigin: "bottom right",
  },
  mobileContainer: {
    position: "fixed",
    top: "calc(env(safe-area-inset-top, 0px) + 10px)",
    right: "calc(env(safe-area-inset-right, 0px) + 10px)",
    bottom: "calc(env(safe-area-inset-bottom, 0px) + 74px)",
    left: "calc(env(safe-area-inset-left, 0px) + 10px)",
    zIndex: 9999,
    borderRadius: "14px",
    overflow: "hidden",
    background: "rgba(255, 255, 255, 0.8)",
    border: "1px solid rgba(31, 62, 105, 0.14)",
    boxShadow: "0 18px 44px rgba(21, 45, 79, 0.3)",
    backdropFilter: "blur(12px)",
    transformOrigin: "bottom right",
  },
  mobileHandle: {
    position: "absolute",
    top: 9,
    left: "50%",
    transform: "translateX(-50%)",
    width: 46,
    height: 4,
    borderRadius: 999,
    background: "rgba(71, 97, 132, 0.35)",
    zIndex: 2,
    pointerEvents: "none",
  },
  mobileGrabZone: {
    position: "absolute",
    top: 0,
    left: "50%",
    transform: "translateX(-50%)",
    width: 86,
    height: 28,
    zIndex: 3,
    pointerEvents: "none",
  },
};

function getWidgetApiBaseUrl() {
  if (typeof import.meta !== "undefined" && import.meta.env?.VITE_API_URL) {
    return String(import.meta.env.VITE_API_URL).replace(/\/$/, "");
  }
  if (typeof window !== "undefined" && window.location.hostname.includes("localhost")) {
    return "http://localhost:8001";
  }
  return "https://evolvian-assistant.onrender.com";
}

function getDefaultLauncherIconUrl(apiBaseUrl) {
  return `${String(apiBaseUrl).replace(/\/$/, "")}/static/logo-evolvian.svg`;
}
