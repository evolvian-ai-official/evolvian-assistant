import { supabase } from "./supabaseClient";

export async function getAuthHeaders(extraHeaders = {}) {
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session?.access_token) {
    throw new Error("No active session");
  }

  return {
    ...extraHeaders,
    Authorization: `Bearer ${session.access_token}`,
  };
}

export async function authFetch(url, options = {}) {
  const headers = await getAuthHeaders(options.headers || {});
  return fetch(url, { ...options, headers });
}
