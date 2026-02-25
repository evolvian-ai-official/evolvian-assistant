import { useEffect, useState } from "react";
import Sidebar from "../components/Sidebar";
import InternalSupportWidget from "../components/InternalSupportWidget";
import { useLanguage } from "../contexts/LanguageContext";

const MOBILE_BREAKPOINT = 1024;

export default function MainLayout({ children }) {
  const { t } = useLanguage();
  const [isMobile, setIsMobile] = useState(
    typeof window !== "undefined" ? window.innerWidth < MOBILE_BREAKPOINT : false
  );
  const [sidebarOpen, setSidebarOpen] = useState(false);

  useEffect(() => {
    const handleResize = () => {
      setIsMobile(window.innerWidth < MOBILE_BREAKPOINT);
    };

    handleResize();
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  useEffect(() => {
    if (!isMobile) setSidebarOpen(false);
  }, [isMobile]);

  useEffect(() => {
    if (!isMobile) return undefined;

    const previousOverflow = document.body.style.overflow;
    if (sidebarOpen) document.body.style.overflow = "hidden";

    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, [isMobile, sidebarOpen]);

  return (
    <div style={outerContainer}>
      <header style={headerStyle}>
        <div style={headerInner}>
          {isMobile ? (
            <button
              type="button"
              aria-label={t("main_layout_open_menu")}
              onClick={() => setSidebarOpen(true)}
              style={menuButtonStyle}
            >
              ☰
            </button>
          ) : (
            <div style={headerSpacer} />
          )}

          <div style={brandStyle}>Evolvian™</div>
          <div style={headerSpacer} />
        </div>
      </header>

      <div style={layoutContainer}>
        {!isMobile && <Sidebar />}
        <main style={isMobile ? mobileMainContent : mainContent}>{children}</main>
      </div>

      <footer style={footerStyle}>
        <div>
          {t("main_layout_footer_trademark")}
        </div>
        <div style={{ marginTop: "0.5rem" }}>
          {t("main_layout_footer_version_label")} v1.0 {t("main_layout_footer_separator")}{" "}
          <a
            href="https://evolvianai.com"
            target="_blank"
            rel="noopener noreferrer"
            style={linkStyle}
          >
            {t("main_layout_footer_visit_public_site")}
          </a>{" "}
          |{" "}
          <a href="/terms" style={linkStyle}>
            {t("main_layout_footer_terms")}
          </a>{" "}
          |{" "}
          <a href="/PrivacyPolicy" style={linkStyle}>
            {t("main_layout_footer_privacy")}
          </a>
        </div>
      </footer>

      {isMobile && sidebarOpen && (
        <>
          <button
            type="button"
            aria-label={t("main_layout_close_menu")}
            onClick={() => setSidebarOpen(false)}
            style={backdropStyle}
          />
          <aside style={mobileDrawerStyle}>
            <Sidebar mobile onNavigate={() => setSidebarOpen(false)} />
          </aside>
        </>
      )}

      <InternalSupportWidget />
    </div>
  );
}

const outerContainer = {
  display: "flex",
  flexDirection: "column",
  minHeight: "100dvh",
  backgroundColor: "#f8fafc",
  color: "#274472",
  fontFamily: "Inter, system-ui, sans-serif",
};

const headerStyle = {
  position: "sticky",
  top: 0,
  zIndex: 20,
  backgroundColor: "#ffffff",
  borderBottom: "1px solid #e5e7eb",
  boxShadow: "0 2px 8px rgba(0,0,0,0.05)",
};

const headerInner = {
  minHeight: "64px",
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  gap: "0.75rem",
  padding: "0.75rem 1rem",
};

const brandStyle = {
  fontSize: "1.25rem",
  fontWeight: "700",
  color: "#4a90e2",
  textAlign: "center",
  whiteSpace: "nowrap",
};

const menuButtonStyle = {
  width: "40px",
  height: "40px",
  borderRadius: "10px",
  border: "1px solid #d9e2ee",
  background: "#ffffff",
  color: "#274472",
  fontSize: "1.25rem",
  lineHeight: 1,
  cursor: "pointer",
};

const headerSpacer = {
  width: "40px",
  height: "40px",
};

const layoutContainer = {
  display: "flex",
  flex: 1,
  backgroundColor: "#ffffff",
  minHeight: 0,
};

const mainContent = {
  flex: 1,
  padding: "2rem",
  overflowY: "auto",
  backgroundColor: "#f8fafc",
  borderLeft: "1px solid #e5e7eb",
  minHeight: 0,
};

const mobileMainContent = {
  ...mainContent,
  padding: "1rem",
  borderLeft: "none",
};

const mobileDrawerStyle = {
  position: "fixed",
  top: 0,
  left: 0,
  height: "100dvh",
  width: "min(88vw, 320px)",
  background: "#ffffff",
  zIndex: 32,
  boxShadow: "0 12px 30px rgba(0, 0, 0, 0.22)",
};

const backdropStyle = {
  position: "fixed",
  inset: 0,
  border: "none",
  background: "rgba(15, 28, 46, 0.45)",
  zIndex: 31,
  cursor: "pointer",
};

const footerStyle = {
  textAlign: "center",
  padding: "1rem",
  fontSize: "0.875rem",
  backgroundColor: "#ffffff",
  color: "#6b7280",
  borderTop: "1px solid #e5e7eb",
};

const linkStyle = {
  textDecoration: "underline",
  color: "#4a90e2",
  fontWeight: 500,
};
