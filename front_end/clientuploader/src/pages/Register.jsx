import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { supabase } from "../lib/supabaseClient";
import { toast } from "sonner";

export default function Register() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const navigate = useNavigate();

  const handleRegister = async (e) => {
    e.preventDefault();

    try {
      const checkRes = await fetch("http://localhost:8000/check_email_exists", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });

      const checkData = await checkRes.json();
      if (checkData.exists) {
        toast.error(`Este correo ya está registrado con: ${checkData.provider}`);
        return;
      }

      const { data, error } = await supabase.auth.signUp({ email, password });

      if (error) {
        toast.error("Error al crear cuenta: " + error.message);
        return;
      }

      const { data: { session }, error: sessionError } = await supabase.auth.getSession();

      if (!session || !session.user || sessionError) {
        toast.success("✅ Cuenta creada. Revisa tu correo para confirmarla.");
        setTimeout(() => navigate("/login"), 3000);
        return;
      }

      const initRes = await fetch("http://localhost:8000/initialize_user", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          auth_user_id: session.user.id,
          email: session.user.email,
        }),
      });

      if (!initRes.ok) {
        toast.error("❌ Error inicializando cuenta.");
        return;
      }

      toast.success("🎉 Cuenta creada correctamente. Redirigiendo...");
      setTimeout(() => navigate("/dashboard"), 2000);
    } catch (err) {
      console.error(err);
      toast.error("Ocurrió un error inesperado.");
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
          color: "white",
          borderRadius: "1.5rem",
          padding: "2rem",
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
          <h1 style={{ fontSize: "1.75rem", fontWeight: "bold" }}>Crear cuenta</h1>
        </div>

        <form onSubmit={handleRegister} style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
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
          <input
            type="password"
            placeholder="Contraseña"
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
            Crear cuenta
          </button>
        </form>

        <p style={{ textAlign: "center", fontSize: "0.875rem", color: "#bbb", marginTop: "2rem" }}>
          ¿Ya tienes cuenta?{" "}
          <Link
            to="/login"
            style={{
              color: "#f5a623",
              fontWeight: "bold",
              textDecoration: "underline",
            }}
          >
            Inicia sesión aquí
          </Link>
        </p>
      </div>
    </div>
  );
}
