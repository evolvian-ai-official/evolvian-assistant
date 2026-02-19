import React from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import AppRouter from "./router/AppRouter";
import { Toaster } from "sonner"; // ✅ Importar toaster
import { LanguageProvider } from "./contexts/LanguageContext"; // ✅ Importar LanguageProvider
import AppErrorBoundary from "./components/AppErrorBoundary";
import "./index.css";

createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <AppErrorBoundary>
      <LanguageProvider> {/* ✅ Aquí envolvemos todo */}
        <BrowserRouter>
          <>
            <AppRouter />
            <Toaster position="top-right" richColors /> {/* ✅ Mostrar toasts */}
          </>
        </BrowserRouter>
      </LanguageProvider>
    </AppErrorBoundary>
  </React.StrictMode>
);
