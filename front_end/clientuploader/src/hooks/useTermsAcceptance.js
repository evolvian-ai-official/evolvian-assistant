import { useEffect, useState } from "react";

export function useTermsAcceptance(clientId) {
  const [hasAccepted, setHasAccepted] = useState(null); // null = loading

  useEffect(() => {
    if (!clientId) return;

    const checkAcceptance = async () => {
      try {
        const res = await fetch(`http://localhost:8000/accepted_terms?client_id=${clientId}`);
        const data = await res.json();
        setHasAccepted(data.has_accepted); // ✅ usa la clave que devuelve el backend
      } catch (err) {
        console.error("❌ Error al verificar aceptación de términos:", err);
        setHasAccepted(false);
      }
    };

    checkAcceptance();
  }, [clientId]);

  const acceptTerms = async () => {
    try {
      const res = await fetch("http://localhost:8000/accept_terms", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          client_id: clientId, // ✅ solo este campo, según backend
        }),
      });

      if (!res.ok) throw new Error("Error al registrar aceptación");

      setHasAccepted(true);
    } catch (err) {
      console.error("❌ Error al aceptar términos:", err);
    }
  };

  return { hasAccepted, acceptTerms };
}
