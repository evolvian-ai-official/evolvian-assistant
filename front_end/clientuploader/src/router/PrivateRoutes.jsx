// src/router/PrivateRoutes.jsx
import { useInitializeUser } from "../hooks/useInitializeUser";
import ProtectedRoute from "../components/ProtectedRoute";
import { useEffect, useState } from "react";

export default function PrivateRoutes({ children }) {
  const { session, clientId, loading } = useInitializeUser();
  const [animateLogo, setAnimateLogo] = useState(false);
  const [dots, setDots] = useState("");

  // 🔄 Efectos: animación del logo + puntos suspensivos del texto
  useEffect(() => {
    setTimeout(() => setAnimateLogo(true), 150);

    const dotsInterval = setInterval(() => {
      setDots((prev) => (prev.length < 3 ? prev + "." : ""));
    }, 500);

    if (!document.getElementById("pulseGlow")) {
      const style = document.createElement("style");
      style.id = "pulseGlow";
      style.textContent = `
        @keyframes pulseGlow {
          0%, 100% { box-shadow: 0 0 15px rgba(74,144,226,0.4); }
          50% { box-shadow: 0 0 25px rgba(163,217,177,0.7); }
        }
      `;
      document.head.appendChild(style);
    }

    return () => clearInterval(dotsInterval);
  }, []);

  // 🌀 Loader visual mientras se carga la sesión
  if (loading) {
    return (
      <div style={styles.container}>
        <div style={styles.card}>
          <div style={styles.logoWrapper}>
            <div
              style={{
                ...styles.logoCircle,
                transform: animateLogo ? "rotate(360deg)" : "rotate(0deg)",
                transition: "transform 1.2s ease-in-out",
                animation: "pulseGlow 4s ease-in-out infinite",
              }}
            >
              <img
                src="/logo-evolvian.svg"
                alt="Evolvian Logo"
                style={styles.logoFull}
              />
            </div>
          </div>
          <p style={styles.text}>🔄 Loading session{dots}</p>
        </div>
      </div>
    );
  }

  // 🚫 Mensaje de sesión inválida
  if (!session || !clientId) {
    return (
      <div style={styles.container}>
        <div style={styles.card}>
          <div style={styles.logoWrapper}>
            <div
              style={{
                ...styles.logoCircle,
                transform: animateLogo ? "rotate(360deg)" : "rotate(0deg)",
                transition: "transform 1.2s ease-in-out",
                animation: "pulseGlow 4s ease-in-out infinite",
              }}
            >
              <img
                src="/logo-evolvian.svg"
                alt="Evolvian Logo"
                style={styles.logoFull}
              />
            </div>
          </div>
          <p style={styles.error}>⛔ Invalid session. Please log in again.</p>
        </div>
      </div>
    );
  }

  // ✅ Si hay sesión y clientId, renderiza el contenido protegido
  return <ProtectedRoute>{children}</ProtectedRoute>;
}

/* 🎨 Estilos Evolvian */
const styles = {
  container: {
    height: "100vh",
    width: "100vw",
    backgroundColor: "#f9fafb",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontFamily: "Inter, system-ui, sans-serif",
  },
  card: {
    backgroundColor: "#ffffff",
    borderRadius: "20px",
    padding: "2.5rem",
    maxWidth: "400px",
    width: "90%",
    textAlign: "center",
    boxShadow: "0 8px 40px rgba(39,68,114,0.1)",
    border: "1px solid #e5e7eb",
  },
  logoWrapper: {
    display: "flex",
    justifyContent: "center",
    marginBottom: "1.2rem",
  },
  logoCircle: {
    width: "80px",
    height: "80px",
    borderRadius: "50%",
    background: "radial-gradient(circle, #a3d9b1 0%, #4a90e2 100%)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    overflow: "hidden",
  },
  logoFull: {
    width: "100%",
    height: "100%",
    objectFit: "cover",
  },
  text: {
    color: "#274472",
    fontSize: "1rem",
    fontWeight: "500",
    marginTop: "0.8rem",
  },
  error: {
    color: "#e63946",
    fontSize: "1rem",
    fontWeight: "600",
    marginTop: "0.8rem",
  },
};
