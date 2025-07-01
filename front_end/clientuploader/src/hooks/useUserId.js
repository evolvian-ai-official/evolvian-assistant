import { useEffect, useState } from "react";
import { supabase } from "../lib/supabaseClient";

export function useUserId() {
  const [userId, setUserId] = useState(null);

  useEffect(() => {
    const getUser = async () => {
      const { data, error } = await supabase.auth.getUser();
      if (error) {
        console.error("❌ Error obteniendo el usuario:", error.message);
      } else {
        setUserId(data?.user?.id || null);
      }
    };

    getUser();
  }, []);

  return userId;
}
