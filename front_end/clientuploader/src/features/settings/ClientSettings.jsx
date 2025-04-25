import { useEffect, useState } from "react";
import { useClientId } from "../../hooks/useClientId";

export default function ClientSettings() {
  const clientId = useClientId();
  console.log("🧠 clientId:", clientId);

  const [formData, setFormData] = useState({
    assistant_name: "",
    language: "es",
    temperature: 0.7,
    plan: null,
    show_powered_by: true,
    custom_prompt: "",
    require_email: false,
    require_phone: false,
    require_terms: false
  });

  const [status, setStatus] = useState({ message: "", type: "" });
  const [loading, setLoading] = useState(true);

  const DEFAULT_PROMPT = "Eres un asistente de IA diseñado para ayudar con preguntas sobre los documentos cargados por el cliente. Responde de forma clara, útil y en el idioma del usuario.";
  const MAX_PROMPT_LENGTH = 2000;
  const promptLength = (formData.custom_prompt || DEFAULT_PROMPT).length;
  const isPromptTooLong = promptLength > MAX_PROMPT_LENGTH;

  useEffect(() => {
    const fetchSettings = async () => {
      if (!clientId) {
        console.warn("⚠️ clientId no disponible");
        return;
      }
      try {
        const res = await fetch(`http://localhost:8000/client_settings?client_id=${clientId}`);
        const data = await res.json();
        console.log("📥 Respuesta del backend:", data);
        if (res.ok) {
          setFormData(prev => ({
            ...data,
            plan: {
              ...data.plan,
              plan_features: data.plan?.plan_features
            }
          }));
        }
      } catch (err) {
        console.error("❌ Error en la petición:", err);
      } finally {
        setLoading(false);
      }
    };

    fetchSettings();
  }, [clientId]);

  const handleChange = (e) => {
    const { name, type, checked, value } = e.target;
    const newValue = type === "checkbox" ? checked : value;
    console.log("✏️ Cambio en formulario:", name, newValue);
    setFormData(prev => ({ ...prev, [name]: newValue }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setStatus({ message: "", type: "" });

    if (formData.custom_prompt?.length > MAX_PROMPT_LENGTH) {
      setStatus({ message: "❌ El prompt personalizado supera el límite de 2000 caracteres.", type: "error" });
      return;
    }

    const payload = {
      client_id: clientId,
      assistant_name: formData.assistant_name,
      language: formData.language,
      temperature: formData.temperature,
      custom_prompt: formData.custom_prompt,
      require_email: formData.require_email,
      require_phone: formData.require_phone,
      require_terms: formData.require_terms
    };

    console.log("📤 Payload a enviar:", payload);
    try {
      const res = await fetch("http://localhost:8000/client_settings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });

      const data = await res.json();
      console.log("📥 Respuesta del backend:", data);
      if (!res.ok) throw new Error(data.error || "Error al guardar");

      setStatus({ message: "✅ Configuración guardada con éxito", type: "success" });
    } catch (err) {
      console.error("❌ Error en la petición:", err);
      setStatus({ message: `❌ ${err.message}`, type: "error" });
    }
  };

  const featurePlans = {
    chat_widget: ["free", "starter", "premium"],
    email_support: ["starter", "premium"],
    whatsapp_integration: ["premium"],
    custom_greeting: ["starter", "premium"],
    white_labeling: ["white_label"],
    custom_prompt_editing: ["premium", "white_label"]
  };

  const planHierarchy = ["free", "starter", "premium", "white_label"];
  const currentPlanId = formData.plan?.id?.toLowerCase() ?? "free";

  const isFeatureIncludedByPlan = (featureKey, currentPlan) => {
    const allowedPlans = featurePlans[featureKey];
    if (!allowedPlans) return false;
    const currentIndex = planHierarchy.indexOf(currentPlan);
    return allowedPlans.some(plan => planHierarchy.indexOf(plan) <= currentIndex);
  };

  const getRequiredPlan = (featureKey) => {
    const plans = featurePlans[featureKey];
    if (!plans || plans.length === 0) return "—";
    if (plans.includes("free")) return "Free";
    if (plans.includes("starter")) return "Starter";
    if (plans.includes("premium")) return "Premium";
    return plans[0];
  };

  const hasPromptFeature = formData.plan?.plan_features?.some(f =>
    typeof f === "string"
      ? f === "custom_prompt_editing"
      : f?.feature?.toLowerCase()?.replace(/\s+/g, "_") === "custom_prompt_editing"
  );

  if (!clientId) return <p style={{ padding: "1rem", color: "red" }}>⚠️ No se ha identificado el cliente.</p>;
  if (loading) return <p style={{ padding: "1rem" }}>🔄 Cargando configuración...</p>;

  return (
    <div style={{ padding: "2rem", maxWidth: "700px", margin: "0 auto", fontFamily: "sans-serif" }}>
      <h2 style={{ fontSize: "1.8rem", color: "#274472", marginBottom: "1.5rem" }}>⚙️ Configuración del Cliente</h2>

      <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
        <div>
          <label>Nombre del asistente</label>
          <input
            name="assistant_name"
            value={formData.assistant_name || ""}
            onChange={handleChange}
            style={{ width: "100%", padding: "8px", borderRadius: "6px", border: "1px solid #ccc", marginTop: "4px" }}
          />
        </div>

        <div>
          <label>Prompt personalizado</label>
          <textarea
            name="custom_prompt"
            value={formData.custom_prompt || DEFAULT_PROMPT}
            onChange={handleChange}
            readOnly={!hasPromptFeature}
            rows={6}
            style={{
              width: "100%",
              padding: "8px",
              borderRadius: "6px",
              border: isPromptTooLong ? "2px solid #e53935" : "1px solid #ccc",
              marginTop: "4px",
              fontFamily: "inherit"
            }}
          />
          <div style={{ display: "flex", justifyContent: "space-between", marginTop: "4px" }}>
            {!hasPromptFeature && (
              <p style={{ color: "#888", fontSize: "0.85rem" }}>
                Este prompt solo es editable con planes Premium o superiores.
              </p>
            )}
            <p style={{ fontSize: "0.85rem", color: isPromptTooLong ? "#e53935" : "#666" }}>
              {promptLength} / {MAX_PROMPT_LENGTH} caracteres
            </p>
          </div>
        </div>

        <div>
          <label>Idioma</label>
          <select
            name="language"
            value={formData.language || "es"}
            onChange={handleChange}
            style={{ width: "100%", padding: "8px", borderRadius: "6px", border: "1px solid #ccc", marginTop: "4px" }}
          >
            <option value="es">Español</option>
            <option value="en">Inglés</option>
          </select>
        </div>

        <div>
          <label>Creatividad (temperature)</label>
          <input
            type="number"
            step="0.1"
            min="0"
            max="1"
            name="temperature"
            value={formData.temperature ?? 0.7}
            onChange={handleChange}
            style={{ width: "100%", padding: "8px", borderRadius: "6px", border: "1px solid #ccc", marginTop: "4px" }}
          />
        </div>

        <div>
          <label>
            <input
              type="checkbox"
              name="require_email"
              checked={formData.require_email}
              onChange={handleChange}
            /> Solicitar email en el widget
          </label>
        </div>

        <div>
          <label>
            <input
              type="checkbox"
              name="require_phone"
              checked={formData.require_phone}
              onChange={handleChange}
            /> Solicitar teléfono en el widget
          </label>
        </div>

        <div>
          <label>
            <input
              type="checkbox"
              name="require_terms"
              checked={formData.require_terms}
              onChange={handleChange}
            /> Mostrar Términos y Condiciones
          </label>
        </div>

        <button
          type="submit"
          disabled={isPromptTooLong}
          style={{
            backgroundColor: "#4a90e2",
            color: "white",
            padding: "10px 16px",
            border: "none",
            borderRadius: "6px",
            cursor: isPromptTooLong ? "not-allowed" : "pointer",
            fontWeight: "bold",
            width: "fit-content"
          }}
        >
          Guardar configuración
        </button>
      </form>

      {status.message && (
        <p style={{
          marginTop: "1.5rem",
          fontWeight: "bold",
          color: status.type === "error" ? "#e53935" : "#2e7d32"
        }}>
          {status.message}
        </p>
      )}

      




      {/* PLAN ACTUAL */}
      <div style={{
        marginTop: "2rem",
        backgroundColor: "white",
        border: "1px solid #4a90e2",
        borderRadius: "16px",
        padding: "1.5rem",
        boxShadow: "0 4px 10px rgba(0,0,0,0.08)"
      }}>
        <div style={{
          display: "flex", justifyContent: "space-between",
          alignItems: "center", marginBottom: "1rem"
        }}>
          <h3 style={{ color: "#274472", fontSize: "1.2rem", fontWeight: "bold" }}>🧾 Tu plan actual</h3>
          <span style={{
            backgroundColor: "#4a90e2", color: "white", padding: "4px 12px",
            borderRadius: "999px", fontSize: "0.85rem", textTransform: "capitalize"
          }}>
            {formData.plan?.name || formData.plan?.id || "—"}
          </span>
        </div>

        <ul style={{ fontSize: "0.95rem", paddingLeft: "1rem", marginBottom: "1rem", lineHeight: "1.8" }}>
          <li><strong style={{ color: "#4a90e2" }}>💬 Mensajes incluidos:</strong>{" "}
            <span style={{ color: "#1b2a41" }}>
              {formData.plan?.is_unlimited ? "Ilimitados" : formData.plan?.max_messages ?? "—"}
            </span>
          </li>
          <li><strong style={{ color: "#4a90e2" }}>📄 Documentos permitidos:</strong>{" "}
            <span style={{ color: "#1b2a41" }}>
              {formData.plan?.is_unlimited ? "Ilimitados" : formData.plan?.max_documents ?? "—"}
            </span>
          </li>
          <li><strong style={{ color: "#4a90e2" }}>🔖 Branding activo:</strong>{" "}
            <span style={{ color: "#1b2a41" }}>
              {formData.show_powered_by ? "Sí" : "No"}
            </span>
          </li>
        </ul>

        <div style={{ textAlign: "right" }}>
          <a href="/settings" style={{
            color: "#f5a623", fontWeight: "bold", fontSize: "0.9rem"
          }}>
            🔁 Cambiar o actualizar plan
          </a>
        </div>
      </div>

      {/* FUNCIONALIDADES INCLUIDAS */}
      <div style={{
        marginTop: "2rem",
        backgroundColor: "white",
        border: "1px solid #4a90e2",
        borderRadius: "16px",
        padding: "1.5rem",
        boxShadow: "0 4px 10px rgba(0,0,0,0.08)"
      }}>
        <h4 style={{
          fontSize: "1.1rem", fontWeight: "bold",
          color: "#274472", marginBottom: "1rem"
        }}>
          🧩 Funcionalidades incluidas
        </h4>

        <ul style={{ listStyle: "none", padding: 0, margin: 0, fontSize: "0.95rem" }}>
          {[
            { key: "chat_widget", label: "Widget de chat", icon: "💬" },
            { key: "email_support", label: "Soporte por correo", icon: "✉️" },
            { key: "whatsapp_integration", label: "WhatsApp", icon: "📱" },
            { key: "custom_greeting", label: "Mensaje personalizado", icon: "👋" },
            { key: "white_labeling", label: "White-label sin branding", icon: "🏷️" }
          ].map((feature) => {
            const isIncluded = isFeatureIncludedByPlan(feature.key, currentPlanId);
            return (
              <li key={feature.key} style={{
                display: "flex", alignItems: "center", gap: "8px",
                marginBottom: "0.5rem", color: isIncluded ? "#4a90e2" : "#999"
              }}>
                <span>{feature.icon}</span>
                <span>{feature.label}</span>
                <span style={{
                  marginLeft: "auto",
                  backgroundColor: isIncluded ? "#a3d9b1" : "#f5a623",
                  color: "#1b2a41", fontSize: "0.7rem", padding: "2px 6px",
                  borderRadius: "999px", fontWeight: "bold"
                }}>
                  {isIncluded ? "Incluido en tu plan" : `Desde ${getRequiredPlan(feature.key)}`}
                </span>
              </li>
            );
          })}
        </ul>
      </div>

      
    </div>
  );
}
