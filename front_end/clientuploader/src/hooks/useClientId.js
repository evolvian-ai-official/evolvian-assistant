import { useEffect, useState } from "react";

export function useClientId() {
  const [clientId, setClientId] = useState(() => {
    const stored = localStorage.getItem("client_id");
    return stored && stored !== "undefined" && stored !== "null" ? stored : null;
  });

  useEffect(() => {
    const handleStorageChange = (event) => {
      if (event.key === "client_id") {
        const value = event.newValue;
        if (value && value !== "undefined" && value !== "null") {
          setClientId(value);
        }
      }
    };

    window.addEventListener("storage", handleStorageChange);

    return () => window.removeEventListener("storage", handleStorageChange);
  }, []);

  return clientId;
}
