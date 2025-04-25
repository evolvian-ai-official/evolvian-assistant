// src/router/PrivateRoutes.jsx
import { useInitializeUser } from "../hooks/useInitializeUser";
import ProtectedRoute from "../components/ProtectedRoute";

export default function PrivateRoutes({ children }) {
  const { session, loading, clientId } = useInitializeUser();

  if (loading || !session || !clientId) {
    return <p style={{ padding: "2rem" }}>🔄 Cargando sesión y cliente...</p>;
  }

  return <ProtectedRoute>{children}</ProtectedRoute>;
}
