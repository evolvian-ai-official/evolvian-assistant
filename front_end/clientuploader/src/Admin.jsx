// src/Admin.jsx
import { useEffect, useState } from "react";
import { supabase } from "./supabaseClient";
import AdminHistory from "./AdminHistory";

function Admin() {
  const [loading, setLoading] = useState(true);
  const [userEmail, setUserEmail] = useState("");

  useEffect(() => {
    const checkSession = async () => {
      const { data } = await supabase.auth.getSession();
      const session = data.session;

      if (!session) {
        // 🔒 No autenticado → redirige al login
        window.location.href = "/login";
        return;
      }

      setUserEmail(session.user.email);
      setLoading(false);
    };

    checkSession();
  }, []);

  const handleLogout = async () => {
    await supabase.auth.signOut();
    localStorage.removeItem("client_id");
    window.location.href = "/login";
  };

  if (loading) return <p style={{ padding: "2rem" }}>Cargando...</p>;

  return (
    <div style={{ padding: "2rem", fontFamily: "sans-serif" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h1 style={{ color: "#274472" }}>🎛️ Panel de Cliente</h1>
        <div>
          <span style={{ marginRight: "1rem", color: "#4a90e2" }}>{userEmail}</span>
          <button
            onClick={handleLogout}
            style={{
              backgroundColor: "#f5a623",
              color: "white",
              border: "none",
              borderRadius: "8px",
              padding: "0.5rem 1rem",
              cursor: "pointer",
            }}
          >
            Cerrar sesión
          </button>
        </div>
      </div>

      <hr style={{ margin: "1rem 0", borderColor: "#ededed" }} />

      <AdminHistory />
    </div>
  );
}

export default Admin;

