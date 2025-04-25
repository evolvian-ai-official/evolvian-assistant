import { useState } from "react";
import { supabase } from "../lib/supabaseClient";
import { toast } from "sonner";

export default function VerifyMfa() {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);

  const handleSendOtp = async (e) => {
    e.preventDefault();
    setLoading(true);

    const { error } = await supabase.auth.signInWithOtp({
      email,
      options: {
        redirectTo: `${window.location.origin}/dashboard`,
      },
    });

    if (error) {
      toast.error("Error al enviar el enlace de acceso por correo electrónico");
    } else {
      toast.success("📩 Revisa tu correo para continuar");
      setSuccess(true);
    }

    setLoading(false);
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
        <div style={{ textAlign: "center", marginBottom: "1.5rem" }}>
          <img
            src="/logo-evolvian.svg"
            alt="Logo Evolvian"
            style={{ width: "64px", margin: "0 auto 1rem" }}
          />
          <h1 style={{ fontSize: "1.5rem", fontWeight: "bold" }}>Verificación de acceso</h1>
          <p style={{ fontSize: "0.9rem", color: "#ccc" }}>
            Por seguridad, confirma tu correo para continuar
          </p>
        </div>

        {success ? (
          <p style={{ textAlign: "center", color: "#ededed" }}>
            Te hemos enviado un enlace. Haz clic en él para volver a entrar a tu cuenta.
          </p>
        ) : (
          <form onSubmit={handleSendOtp} style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
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
              {loading ? "Enviando..." : "Enviar enlace de acceso"}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
