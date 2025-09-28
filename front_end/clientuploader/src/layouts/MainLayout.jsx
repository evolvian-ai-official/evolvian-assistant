import Sidebar from "../components/Sidebar";
import InternalSupportWidget from "../components/InternalSupportWidget"; // ✅ Widget interno para soporte técnico

export default function MainLayout({ children }) {
  return (
    <div style={outerContainer}>
      {/* Header */}
      <header style={headerStyle}>
        Evolvian™
      </header>

      {/* Contenido principal con sidebar */}
      <div style={layoutContainer}>
        <Sidebar />
        <main style={mainContent}>
          {children}
        </main>
      </div>

      {/* Footer legal */}
      <footer style={footerStyle}>
        <div>
          Evolvian™ is a pending trademark application filed with the USPTO. All rights reserved.
        </div>
        <div>
          Version v1.0 —{" "}
          <a href="https://evolvianai.com" target="_blank" rel="noopener noreferrer" style={{ textDecoration: "underline", color: "#a3d9b1" }}>
            Visit Public Site
          </a>{" "}
          |{" "}
          <a href="/terms" style={{ textDecoration: "underline", color: "#a3d9b1" }}>
            Terms & Conditions
          </a>
        </div>
      </footer>

      {/* Widget de ayuda interna para clientes Evolvian */}
      <InternalSupportWidget />
    </div>
  );
}

// 🎨 Estilos inline

const outerContainer = {
  display: "flex",
  flexDirection: "column",
  minHeight: "100vh",
  backgroundColor: "#0f1c2e",
  color: "white",
};

const headerStyle = {
  padding: "1rem",
  fontSize: "1.5rem",
  fontWeight: "bold",
  color: "#f5a623",
  backgroundColor: "#1b2a41",
  textAlign: "center",
};

const layoutContainer = {
  display: "flex",
  flex: 1,
};

const mainContent = {
  flex: 1,
  padding: "2rem",
  overflowY: "auto",
};

const footerStyle = {
  textAlign: "center",
  padding: "1rem",
  fontSize: "0.875rem",
  backgroundColor: "#1b2a41",
  color: "#ededed",
};
