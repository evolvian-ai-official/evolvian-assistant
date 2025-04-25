import { useState } from "react";
import { supabase } from "../lib/supabaseClient";
import { useNavigate } from "react-router-dom";

export default function Register() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [status, setStatus] = useState("");
  const navigate = useNavigate();

  const handleRegister = async () => {
    setStatus("");

    try {
      // Verifica si el email ya existe
      const res = await fetch("http://localhost:8000/check_email_exists", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });

      const data = await res.json();
      if (data.exists) {
        setStatus(`❌ Ya existe una cuenta con este correo usando: ${data.provider}`);
        return;
      }

      // Registro en Supabase
      const { error } = await supabase.auth.signUp({ email, password });
      if (error) {
        setStatus(`❌ ${error.message}`);
        return;
      }

      // Obtiene sesión
      const {
        data: { session },
      } = await supabase.auth.getSession();

      // Llama a /initialize_user
      await fetch("http://localhost:8000/initialize_user", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          auth_user_id: session.user.id,
          email: session.user.email,
        }),
      });

      // Redirige
      setStatus("✅ Cuenta creada con éxito");
      navigate("/dashboard");
    } catch (err) {
      console.error(err);
      setStatus("❌ Ocurrió un error al registrar");
    }
  };

  return (
    <div style={{ padding: "2rem", fontFamily: "sans-serif", maxWidth: "400px", margin: "auto" }}>
      <h1>📝 Crear cuenta</h1>

      <input
        type="email"
        placeholder="Correo"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        className="w-full border rounded px-3 py-2 mt-2 mb-2"
      />

      <input
        type="password"
        placeholder="Contraseña"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        className="w-full border rounded px-3 py-2 mb-4"
      />

      <button
        onClick={handleRegister}
        className="bg-[#4a90e2] text-white px-4 py-2 rounded hover:bg-blue-600"
      >
        Crear cuenta
      </button>

      {status && <p className="mt-4 font-semibold">{status}</p>}
    </div>
  );
}
