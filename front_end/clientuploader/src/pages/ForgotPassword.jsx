import { useState } from "react";
import { supabase } from "../lib/supabaseClient";
import { toast } from "sonner";
import { Link } from "react-router-dom";

export default function ForgotPassword() {
  const [email, setEmail] = useState("");

  const handleReset = async (e) => {
    e.preventDefault();

    const { error } = await supabase.auth.resetPasswordForEmail(email, {
  redirectTo: `${window.location.origin}/reset-password`, // ✅
});


    if (error) {
      console.error("❌ Error al enviar reset:", error.message);
      toast.error("Error al enviar el correo de recuperación");
    } else {
      toast.success("📩 Revisa tu correo para cambiar la contraseña");
    }
  };

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
        <div style={{ textAlign: "center", marginBottom: "2rem" }}>
          <img
            src="/logo-evolvian.svg"
            alt="Logo Evolvian"
            style={{ width: "64px", margin: "0 auto 1rem" }}
          />
          <h1 style={{ fontSize: "1.5rem", fontWeight: "bold" }}>Recuperar contraseña</h1>
          <p style={{ fontSize: "0.9rem", color: "#ccc" }}>
            Ingresa tu correo para restablecer tu contraseña
          </p>
        </div>

        <form onSubmit={handleReset} style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
          <input
            type="email"
            placeholder="Correo electrónico"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
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
            style={{
              backgroundColor: "#2eb39a",
              padding: "0.7rem",
              color: "white",
              borderRadius: "8px",
              fontWeight: "bold",
              border: "none",
              cursor: "pointer",
              fontSize: "1rem",
            }}
          >
            Enviar correo
          </button>
        </form>

        <p
          style={{
            textAlign: "center",
            fontSize: "0.875rem",
            color: "#bbb",
            marginTop: "2rem",
          }}
        >
          ¿Ya tienes acceso?{" "}
          <Link
            to="/login"
            style={{
              color: "#f5a623",
              fontWeight: "bold",
              textDecoration: "underline",
            }}
          >
            Inicia sesión
          </Link>
        </p>
      </div>
    </div>
  );
}
