import React from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import AppRouter from "./router/AppRouter";
import { Toaster } from "sonner"; // ✅ Importar toaster
import "./index.css";

createRoot(document.getElementById("root")).render(
  <BrowserRouter>
    <>
      <AppRouter />
      <Toaster position="top-right" richColors /> {/* ✅ Mostrar toasts */}
    </>
  </BrowserRouter>
);
