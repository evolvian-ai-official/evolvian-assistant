// src/router/PrivateRoutes.jsx

import { useInitializeUser } from "../hooks/useInitializeUser";
import ProtectedRoute from "../components/ProtectedRoute";

export default function PrivateRoutes({ children }) {
  const { session, clientId, loading } = useInitializeUser();

  if (loading) {
    return <div style={{ padding: "2rem", color: "white" }}>🔄 Cargando sesión...</div>;
  }

  if (!session || !clientId) {
    // Aquí podrías agregar un Navigate a /login si quieres manejar usuarios no autorizados.
    return <div style={{ padding: "2rem", color: "white" }}>⛔ Sesión no válida. Por favor inicia sesión.</div>;
  }

  return <ProtectedRoute>{children}</ProtectedRoute>;
}
