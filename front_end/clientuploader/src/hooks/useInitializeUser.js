import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { supabase } from "../lib/supabaseClient";

export function useInitializeUser() {
  const [session, setSession] = useState(null);
  const [clientId, setClientId] = useState(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    const fetchSessionAndClient = async () => {
      let retries = 0;
      let session = null;

      console.log("🔄 Iniciando recuperación de sesión...");

      // 🔁 Intentamos hidratar la sesión hasta 5 veces si viene de magic link
      while (!session && retries < 5) {
        const result = await supabase.auth.getSession();
        session = result.data.session;
        if (session) break;
        await new Promise((res) => setTimeout(res, 300));
        retries++;
      }

      if (!session || !session.user) {
        console.warn("⛔ No hay sesión activa. Redirigiendo a /verify-mfa");
        setSession(null);
        setClientId(null);
        setLoading(false);
        navigate("/verify-mfa");
        return;
      }

      console.log("✅ Sesión obtenida:", session.user.email);

      try {
        const res = await fetch("http://localhost:8000/initialize_user", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            auth_user_id: session.user.id,
            email: session.user.email,
          }),
        });

        const data = await res.json();

        console.log("📡 Respuesta de /initialize_user:", data);

        if (!res.ok) {
          console.error("❌ Error al inicializar usuario:", data.error);
          setLoading(false);
          return;
        }

        setSession(session);
        setClientId(data.client_id);
        localStorage.setItem("client_id", data.client_id);
        localStorage.setItem("user_id", session.user.id);
        setLoading(false);

        // 🚀 Redirigir si es nuevo usuario, solo una vez por sesión
        if (data.is_new_user && !sessionStorage.getItem("alreadyRedirected")) {
          console.log("📥 Usuario nuevo detectado → Redirigiendo a /welcome");
          sessionStorage.setItem("alreadyRedirected", "true");
          navigate("/welcome");
        } else {
          console.log("✅ Usuario existente o ya redirigido. Continúa en dashboard.");
        }

      } catch (err) {
        console.error("❌ Error de red al llamar a /initialize_user:", err);
        setLoading(false);
      }
    };

    fetchSessionAndClient();
  }, [navigate]);

  return { session, clientId, loading };
}
