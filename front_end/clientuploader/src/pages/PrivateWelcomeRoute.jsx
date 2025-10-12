// src/pages/PrivateWelcomeRoute.jsx
import { Navigate } from "react-router-dom";
import { useInitializeUser } from "../hooks/useInitializeUser";

export default function PrivateWelcomeRoute({ children }) {
  const { loading, session, clientId, isNewUser } = useInitializeUser();

  if (loading) {
    return <div style={{ color: "white", padding: "2rem" }}>Cargando...</div>;
  }

  if (!session) {
    return <Navigate to="/login" replace />;
  }

  if (isNewUser) {
    return children;
  } else {
    return <Navigate to="/dashboard" replace />;
  }
}
