import { useEffect } from "react";
import { useNavigate } from "react-router-dom";

export default function Confirm() {
  const navigate = useNavigate();

  useEffect(() => {
    const timeout = setTimeout(() => {
      navigate("/login");
    }, 4000);

    return () => clearTimeout(timeout);
  }, [navigate]);

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
          backgroundColor: "#1b2a41",
          color: "#ffffff",
          padding: "2rem",
          borderRadius: "1.5rem",
          boxShadow: "0 15px 40px rgba(0,0,0,0.3)",
          textAlign: "center",
          maxWidth: "400px",
          width: "100%",
          border: "1px solid #274472",
        }}
      >
        <h2
          style={{
            fontSize: "1.25rem",
            fontWeight: "600",
            marginBottom: "0.75rem",
            color: "#a3d9b1",
          }}
        >
          ✅ ¡Correo confirmado exitosamente!
        </h2>
        <p
          style={{
            fontSize: "0.95rem",
            color: "#ededed",
          }}
        >
          En breve serás redirigido al inicio de sesión...
        </p>
      </div>
    </div>
  );
}
