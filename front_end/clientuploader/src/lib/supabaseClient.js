// src/supabaseClient.js
import { createClient } from "@supabase/supabase-js";

// Asegúrate de tener estas variables en tu archivo .env.local
const supabaseUrl = import.meta.env.VITE_SUPABASE_URL;
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY;

// Validación opcional
if (!supabaseUrl || !supabaseAnonKey) {
  throw new Error("❌ Supabase URL o Anon Key no definidos en .env");
}

export const supabase = createClient(supabaseUrl, supabaseAnonKey);
