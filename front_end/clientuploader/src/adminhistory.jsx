import { useState, useEffect } from "react";
import { supabase } from "./supabaseClient";
import axios from "axios";

function AdminHistory() {
  const [user, setUser] = useState(null);
  const [clientId, setClientId] = useState("");
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);

  // Obtener usuario autenticado y client_id
  useEffect(() => {
    const fetchUser = async () => {
      const { data: { session } } = await supabase.auth.getSession();
      if (session?.user) {
        const { id, email } = session.user;
        setUser(session.user);

        try {
          const res = await axios.post("http://localhost:8000/create_or_get_client", {
            auth_user_id: id,
            email: email,
          });
          setClientId(res.data.client_id);
        } catch (err) {
          console.error("❌ Error creando/obteniendo cliente:", err);
        }
      } else {
        console.log("🔒 Usuario no autenticado");
      }
    };

    fetchUser();
  }, []);

  // Cargar historial
  useEffect(() => {
    const fetchHistory = async () => {
      if (!clientId) return;
      try {
        const res = await axios.get(`http://localhost:8000/history?client_id=${clientId}`);
        setHistory(res.data.history || []);
      } catch (err) {
        console.error("❌ Error al obtener el historial:", err);
        setHistory([]);
      } finally {
        setLoading(false);
      }
    };
    fetchHistory();
  }, [clientId]);

  const handleLogout = async () => {
    await supabase.auth.signOut();
    window.location.reload(); // Refresca para volver al login
  };

  return (
    <div style={{ padding: "2rem", fontFamily: "sans-serif", maxWidth: 800, margin: "0 auto" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h2 style={{ color: "#274472" }}>📚 Historial de Preguntas</h2>
        <button
          onClick={handleLogout}
          style={{
            backgroundColor: "#f5a623",
            color: "white",
            border: "none",
            borderRadius: "8px",
            padding: "0.5rem 1rem",
            cursor: "pointer"
          }}
        >
          Cerrar sesión
        </button>
      </div>

      {loading ? (
        <p>🔄 Cargando historial...</p>
      ) : history.length === 0 ? (
        <p>No hay historial para este cliente.</p>
      ) : (
        <ul style={{ listStyle: "none", padding: 0 }}>
          {history.map((item) => (
            <li key={item.id} style={{
              backgroundColor: "#ededed",
              marginBottom: "1rem",
              padding: "1rem",
              borderRadius: "12px"
            }}>
              <p><strong>🧠 Pregunta:</strong> {item.question}</p>
              <p><strong>🤖 Respuesta:</strong> {item.answer}</p>
              <p style={{ fontSize: "0.8rem", color: "#666" }}>
                🕒 {new Date(item.created_at).toLocaleString()}
              </p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default AdminHistory;

