import { authFetch } from "./authFetch";

export function trackEvent({ name, category = "interaction", label = "", value = "" }) {
  try {
    if (typeof window !== "undefined" && typeof window.gtag === "function") {
      window.gtag("event", name, {
        event_category: category,
        event_label: label,
        value,
      });
    }

    if (typeof window !== "undefined" && typeof window.fbq === "function") {
      window.fbq("trackCustom", name, { category, label, value });
    }

    if (import.meta.env.DEV) {
      console.log(`✅ [Client Tracking] ${name}`, { category, label, value });
    }
  } catch (error) {
    console.warn("⚠️ Client tracking error:", error);
  }
}

export async function trackClientEvent({
  clientId,
  name,
  category = "interaction",
  label = "",
  value = "",
  eventKey = null,
  metadata = {},
  dedupeLocal = false,
}) {
  trackEvent({ name, category, label, value });

  if (!clientId || !name) return;

  const localDedupeKey = `client_event_tracked:${clientId}:${eventKey || name}`;
  if (dedupeLocal && typeof window !== "undefined" && localStorage.getItem(localDedupeKey) === "1") {
    return;
  }

  try {
    await authFetch(`${import.meta.env.VITE_API_URL}/client_event_log`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        client_id: clientId,
        event_name: name,
        event_category: category,
        event_label: label,
        event_value: value,
        event_key: eventKey,
        metadata,
      }),
    });

    if (dedupeLocal && typeof window !== "undefined") {
      localStorage.setItem(localDedupeKey, "1");
    }
  } catch (error) {
    if (import.meta.env.DEV) {
      console.warn("⚠️ Failed to persist client event:", error);
    }
  }
}
