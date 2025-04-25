import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { supabase } from "../lib/supabaseClient";
import { toast } from "sonner";

export default function ResetPassword() {
  const navigate = useNavigate();
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [tokenLoaded, setTokenLoaded] = useState(false);

  useEffect(() => {
    const hash = window.location.hash;
    const accessToken = hash.includes("access_token");
    if (!accessToken) {
      toast.error("Token no válido. Solicita un nuevo enlace.");
      navigate("/forgot-password");
    } else {
      setTokenLoaded(true);
    }
  }, [navigate]);

  const handleUpdate = async (e) => {
    e.preventDefault();
    setLoading(true);

    const { error } = await supabase.auth.updateUser({ password });

    if (error) {
      toast.error("❌ Error al actualizar contraseña: " + error.message);
    } else {
      toast.success("🔒 Contraseña actualizada correctamente");
      navigate("/login");
    }

    setLoading(false);
  };

  if (!tokenLoaded) return null;

  return (
    <div
      style={{
        height: "100vh",
        width: "100vw",
        backgroundColor: "#0f1c2e",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "1rem",
        fontFamily: "system-ui, Avenir, Helvetica, Arial, sans-serif",
      }}
    >
      <div
        style={{
          width: "100%",
          maxWidth: "400px",
          backgroundColor: "#1b2a41",
          borderRadius: "1.5rem",
          padding: "2rem",
          color: "white",
          boxShadow: "0 15px 40px rgba(0,0,0,0.3)",
          border: "1px solid #274472",
        }}
      >
        <div style={{ textAlign: "center", marginBottom: "1.5rem" }}>
          <img
            src="/logo-evolvian.svg"
            alt="Logo Evolvian"
            style={{ width: "64px", margin: "0 auto 1rem" }}
          />
          <h1 style={{ fontSize: "1.5rem", fontWeight: "bold" }}>Nueva contraseña</h1>
          <p style={{ fontSize: "0.9rem", color: "#ccc" }}>
            Ingresa tu nueva contraseña para continuar
          </p>
        </div>

        <form onSubmit={handleUpdate} style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
          <input
            type="password"
            placeholder="Nueva contraseña"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            style={{
              padding: "0.6rem 1rem",
              background: "transparent",
              border: "1px solid #274472",
              borderRadius: "8px",
              color: "white",
              fontSize: "1rem",
            }}
          />

          <button
            type="submit"
            disabled={loading}
            style={{
              backgroundColor: "#2eb39a",
              padding: "0.7rem",
              color: "white",
              borderRadius: "8px",
              fontWeight: "bold",
              border: "none",
              cursor: loading ? "not-allowed" : "pointer",
              fontSize: "1rem",
              opacity: loading ? 0.7 : 1,
            }}
          >
            {loading ? "Actualizando..." : "Actualizar contraseña"}
          </button>
        </form>
      </div>
    </div>
  );
}
