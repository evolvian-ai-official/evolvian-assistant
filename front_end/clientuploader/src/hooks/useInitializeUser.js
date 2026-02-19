import { useEffect, useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { supabase } from "../lib/supabaseClient";

// 🔑 Usa backend directo en dev y API_URL en producción
const API_URL =
  import.meta.env.MODE === "development"
    ? "http://localhost:8001"
    : import.meta.env.VITE_API_URL;

export function useInitializeUser() {
  const [session, setSession] = useState(null);
  const [clientId, setClientId] = useState(null);
  const [publicClientId, setPublicClientId] = useState(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();
  const location = useLocation();

  const publicRoutes = [
    "/", "/login", "/register", "/confirm",
    "/forgot-password", "/reset-password", "/verify-mfa",
    "/welcome", "/chat-widget", "/widget", "/widget-preview"
  ];

  useEffect(() => {
    const fetchSessionAndClient = async () => {
      let retries = 0;
      let currentSession = null;

      console.log("%c🔄 Buscando sesión activa...", "color: #4a90e2; font-weight: bold");

      while (!currentSession && retries < 5) {
        const result = await supabase.auth.getSession();
        currentSession = result.data.session;
        if (currentSession) break;
        await new Promise((res) => setTimeout(res, 300));
        retries++;
      }

      if (!currentSession || !currentSession.user) {
        console.warn("%c⛔ No hay sesión. Redirigiendo a /verify-mfa", "color: #e74c3c; font-weight: bold");
        setSession(null);
        setClientId(null);
        setPublicClientId(null);
        setLoading(false);
        if (!["/login", "/register", "/forgot-password", "/reset-password"].includes(location.pathname)) {
          navigate("/verify-mfa", { replace: true });
        }
        return;
      }

      console.log(`%c✅ Sesión activa como: ${currentSession.user.email}`, "color: #2ecc71; font-weight: bold");

      try {
        const res = await fetch(`${API_URL}/initialize_user`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${currentSession.access_token}`,
          },
          body: JSON.stringify({
            auth_user_id: currentSession.user.id,
            email: currentSession.user.email,
          }),
        });

        let data = {};
        try {
          data = await res.json();
        } catch (jsonError) {
          console.error("%c❌ Error parsing JSON:", "color: #e74c3c", jsonError);
          data = {};
        }

        if (!res.ok) {
          console.error("%c❌ Error en /initialize_user:", "color: #e74c3c; font-weight: bold", data);
          setLoading(false);
          return;
        }

        console.log("%c📡 Datos de /initialize_user:", "color: #3498db; font-weight: bold", data);

        setSession(currentSession);
        setClientId(data.client_id);
        setPublicClientId(data.public_client_id);

        localStorage.setItem("client_id", data.client_id);
        localStorage.setItem("public_client_id", data.public_client_id);
        localStorage.setItem("user_id", currentSession.user.id);

        setLoading(false);

        const alreadyRedirected = sessionStorage.getItem("alreadyRedirected");

        if (publicRoutes.includes(location.pathname)) {
          if (data.is_new_user && !alreadyRedirected) {
            console.log("%c📥 Usuario nuevo → Redirigiendo a /welcome", "color: #f5a623; font-weight: bold");
            sessionStorage.setItem("alreadyRedirected", "true");
            navigate("/welcome", { replace: true });
          } else if (!alreadyRedirected && location.pathname === "/login") {
            console.log("%c🏠 Usuario existente. Redirigiendo a /dashboard", "color: #f5a623; font-weight: bold");
            navigate("/dashboard", { replace: true });
          } else {
            console.log("%c🛑 Ruta pública correcta, no redirigir:", "color: #3498db", location.pathname);
          }
        } else {
          console.log("%c🛑 Ruta privada detectada. No redirigir.", "color: #3498db");
        }

      } catch (err) {
        console.error("%c❌ Error de red al llamar a /initialize_user:", "color: #e74c3c; font-weight: bold", err);
        setLoading(false);
      }
    };

    fetchSessionAndClient();
  }, [navigate, location.pathname]);

  return { session, clientId, publicClientId, loading };
}
//ttt
