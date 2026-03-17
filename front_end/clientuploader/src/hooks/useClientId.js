import { useEffect, useState } from "react";

function readStoredClientId() {
  try {
    const stored = localStorage.getItem("client_id");
    return stored && stored !== "undefined" && stored !== "null" ? stored : null;
  } catch {
    return null;
  }
}

export function useClientId() {
  const [clientId, setClientId] = useState(() => readStoredClientId());

  useEffect(() => {
    const syncClientId = () => {
      setClientId(readStoredClientId());
    };

    const handleStorageChange = (event) => {
      if (!event.key || event.key === "client_id") syncClientId();
    };

    syncClientId();
    window.addEventListener("storage", handleStorageChange);
    window.addEventListener("focus", syncClientId);
    document.addEventListener("visibilitychange", syncClientId);

    return () => {
      window.removeEventListener("storage", handleStorageChange);
      window.removeEventListener("focus", syncClientId);
      document.removeEventListener("visibilitychange", syncClientId);
    };
  }, []);

  return clientId;
}
