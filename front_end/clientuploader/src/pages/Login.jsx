import { useState } from "react";
import { supabase } from "../lib/supabaseClient";
import { useNavigate, Link } from "react-router-dom";
import { FaGoogle } from "react-icons/fa";

export default function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [errorMsg, setErrorMsg] = useState("");
  const navigate = useNavigate();

  const handleGoogleLogin = async () => {
    const { error } = await supabase.auth.signInWithOAuth({
      provider: "google",
      options: {
        redirectTo: `${window.location.origin}/dashboard`,
        queryParams: {
          prompt: "select_account"
        }
      },
    });
    if (error) console.error("❌ Error al iniciar sesión con Google:", error);
  };

  const handleEmailLogin = async (e) => {
    e.preventDefault();
    setErrorMsg("");

    const { error } = await supabase.auth.signInWithPassword({ email, password });
    if (error) {
      setErrorMsg("Correo o contraseña incorrectos.");
      return;
    }

    const { data: { session } } = await supabase.auth.getSession();
    await fetch("http://localhost:8000/initialize_user", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        auth_user_id: session.user.id,
        email: session.user.email,
      }),
    });

    navigate("/dashboard");
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
          <img src="/logo-evolvian.svg" alt="Logo Evolvian" style={{ width: "64px", margin: "0 auto 1rem" }} />
          <h1 style={{ fontSize: "1.75rem", fontWeight: "bold" }}>Evolvian</h1>
        </div>

        <form onSubmit={handleEmailLogin} style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
          <input
            type="email"
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            style={{
              padding: "0.6rem 1rem",
              backgroundColor: "transparent",
              border: "1px solid #274472",
              borderRadius: "8px",
              color: "white",
              fontSize: "1rem",
            }}
          />
          <input
            type="password"
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            style={{
              padding: "0.6rem 1rem",
              backgroundColor: "transparent",
              border: "1px solid #274472",
              borderRadius: "8px",
              color: "white",
              fontSize: "1rem",
            }}
          />

          {errorMsg && (
            <p style={{ color: "#f87171", textAlign: "center", fontSize: "0.875rem" }}>
              {errorMsg}
            </p>
          )}

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
            Log in
          </button>

          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              fontSize: "0.875rem",
              color: "#ccc",
              marginTop: "0.5rem",
            }}
          >
            <label style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
              <input type="checkbox" />
              Remember me
            </label>
            <Link to="/forgot-password" style={{ color: "#a3d9b1", textDecoration: "underline" }}>
              Forgot password?
            </Link>
          </div>
        </form>

        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "1rem",
            margin: "2rem 0",
            color: "#888",
          }}
        >
          <div style={{ flex: 1, height: "1px", backgroundColor: "#555" }} />
          <span>or</span>
          <div style={{ flex: 1, height: "1px", backgroundColor: "#555" }} />
        </div>

        <button
          onClick={handleGoogleLogin}
          style={{
            width: "100%",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: "0.5rem",
            padding: "0.7rem",
            border: "1px solid white",
            borderRadius: "8px",
            backgroundColor: "transparent",
            color: "white",
            cursor: "pointer",
            fontSize: "1rem",
          }}
        >
          <FaGoogle />
          Log in with Google
        </button>

        <p
          style={{
            textAlign: "center",
            fontSize: "0.875rem",
            color: "#bbb",
            marginTop: "2rem",
          }}
        >
          ¿No tienes cuenta?{" "}
          <Link
            to="/register"
            style={{
              color: "#f5a623",
              fontWeight: "bold",
              textDecoration: "underline",
            }}
          >
            Regístrate aquí
          </Link>
        </p>
      </div>
    </div>
  );
}
