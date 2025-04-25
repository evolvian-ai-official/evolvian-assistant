
import { useEffect, useState } from "react";

export function useClientId() {
  const [clientId, setClientId] = useState(() => {
    const stored = localStorage.getItem("client_id");
    return stored && stored !== "undefined" && stored !== "null" ? stored : null;
  });

  useEffect(() => {
    const checkClientId = () => {
      const stored = localStorage.getItem("client_id");
      if (stored && stored !== "undefined" && stored !== "null") {
        setClientId(stored);
      }
    };

    // ⏱ Revisa cada 500ms por cambios de manera simple
    const interval = setInterval(checkClientId, 500);

    return () => clearInterval(interval);
  }, []);

  return clientId;
}
