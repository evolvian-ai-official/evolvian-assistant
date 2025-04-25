// src/layouts/MainLayout.jsx
import Sidebar from "../components/Sidebar";
import InternalSupportWidget from "../components/InternalSupportWidget"; // ✅ CORRECTO

export default function MainLayout({ children }) {
  return (
    <div style={{ display: "flex", minHeight: "100vh", position: "relative" }}>
      <Sidebar />
      <main style={{ flex: 1, padding: "2rem" }}>
        {children}
      </main>

      {/* ✅ Widget de soporte técnico Evolvian (no de clientes) */}
      <InternalSupportWidget />
    </div>
  );
}
