import { useEffect, useState } from "react";
import axios from "axios";
import { useClientId } from "../../hooks/useClientId";

export default function History() {
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshTrigger, setRefreshTrigger] = useState(0);
  const clientId = useClientId();

  useEffect(() => {
    const fetchHistory = async () => {
      if (!clientId) return;
      setLoading(true);
      try {
        const res = await axios.get(`http://localhost:8000/history?client_id=${clientId}`);
        setHistory(res.data.history || []);
      } catch (err) {
        console.error("Error cargando historial", err);
        setHistory([]);
      } finally {
        setLoading(false);
      }
    };

    fetchHistory();
  }, [clientId, refreshTrigger]);

  return (
    <div
      style={{
        backgroundColor: "#0f1c2e",
        minHeight: "100vh",
        padding: "2rem",
        fontFamily: "system-ui, sans-serif",
        color: "white",
        display: "flex",
        justifyContent: "center",
        alignItems: "flex-start",
      }}
    >
      <div
        style={{
          maxWidth: "800px",
          width: "100%",
          backgroundColor: "#1b2a41",
          padding: "2rem",
          borderRadius: "16px",
          boxShadow: "0 10px 30px rgba(0,0,0,0.2)",
          border: "1px solid #274472",
        }}
      >
        <h2 style={{ fontSize: "1.8rem", fontWeight: "bold", color: "#f5a623", marginBottom: "1.5rem" }}>
          📚 Historial de Preguntas
        </h2>

        {loading ? (
          <p style={{ color: "#ededed" }}>🔄 Cargando historial...</p>
        ) : history.length === 0 ? (
          <p style={{ color: "#ededed" }}>Aún no has hecho ninguna pregunta.</p>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
            {history.map((item) => (
              <div
                key={item.id}
                style={{
                  backgroundColor: "#ededed",
                  color: "#1b2a41",
                  padding: "1rem",
                  borderRadius: "12px",
                  boxShadow: "0 4px 12px rgba(0,0,0,0.1)",
                  border: "1px solid #a3d9b1",
                }}
              >
                <p style={{ marginBottom: "0.5rem" }}>
                  <strong>🧠 Pregunta:</strong> {item.question}
                </p>
                <p style={{ marginBottom: "0.5rem" }}>
                  <strong>🤖 Respuesta:</strong> {item.answer}
                </p>
                <p style={{ fontSize: "0.85rem", color: "#4a90e2" }}>
                  🕒 {new Date(item.created_at).toLocaleString()}
                </p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
