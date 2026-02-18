import { useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { supabase } from "../lib/supabaseClient";

export default function ProtectedRoute({ children }) {
  const [loading, setLoading] = useState(true);
  const [shouldRedirect, setShouldRedirect] = useState(false);

  useEffect(() => {
    const checkSession = async () => {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) {
        setShouldRedirect(true);
      }
      setLoading(false);
    };

    checkSession();
  }, []);

  if (loading) return <p className="p-6">🔐 Verificando sesión...</p>;

  if (shouldRedirect) {
    alert("⚠️ Debes iniciar sesión para acceder a esta sección.");
    return <Navigate to="/login" replace />;
  }

  return children;
}
