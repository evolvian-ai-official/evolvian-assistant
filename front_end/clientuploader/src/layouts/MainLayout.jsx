import Sidebar from "../components/Sidebar";
import InternalSupportWidget from "../components/InternalSupportWidget"; // ✅ Widget interno para soporte técnico

export default function MainLayout({ children }) {
  return (
    <div style={outerContainer}>
      {/* Header */}
      <header style={headerStyle}>Evolvian™</header>

      {/* Contenido principal con sidebar */}
      <div style={layoutContainer}>
        <Sidebar />
        <main style={mainContent}>{children}</main>
      </div>

      {/* Footer legal */}
      <footer style={footerStyle}>
        <div>
          Evolvian™ is a pending trademark application filed with the USPTO. All rights reserved.
        </div>
        <div style={{ marginTop: "0.5rem" }}>
          Version v1.0 —{" "}
          <a
            href="https://evolvianai.com"
            target="_blank"
            rel="noopener noreferrer"
            style={linkStyle}
          >
            Visit Public Site
          </a>{" "}
          |{" "}
          <a href="/terms" style={linkStyle}>
            Terms & Conditions
          </a>{" "}
          |{" "}
          <a href="/privacypolicy" style={linkStyle}>
            Privacy Policy
          </a>
        </div>
      </footer>

      {/* Widget de ayuda interna para clientes Evolvian */}
      <InternalSupportWidget />
    </div>
  );
}

// 🎨 Estilos inline con nueva paleta Evolvian
const outerContainer = {
  display: "flex",
  flexDirection: "column",
  minHeight: "100vh",
  backgroundColor: "#f8fafc", // más limpio y moderno
  color: "#274472", // texto principal azul oscuro
  fontFamily: "Inter, system-ui, sans-serif",
};

const headerStyle = {
  padding: "1rem",
  fontSize: "1.5rem",
  fontWeight: "bold",
  color: "#4a90e2", // azul brillante Evolvian
  backgroundColor: "#ffffff", // header blanco elegante
  textAlign: "center",
  borderBottom: "1px solid #e5e7eb",
  boxShadow: "0 2px 8px rgba(0,0,0,0.05)",
};

const layoutContainer = {
  display: "flex",
  flex: 1,
  backgroundColor: "#ffffff",
};

const mainContent = {
  flex: 1,
  padding: "2rem",
  overflowY: "auto",
  backgroundColor: "#f8fafc",
  borderLeft: "1px solid #e5e7eb",
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
  color: "#4a90e2", // acento azul
  fontWeight: 500,
};
