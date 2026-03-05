import { Routes, Route, Navigate } from "react-router-dom";
import Login from "../pages/Login";
import Register from "../pages/Register";
import Confirm from "../pages/Confirm";
import ForgotPassword from "../pages/ForgotPassword";
import ResetPassword from "../pages/ResetPassword";
import VerifyMfa from "../pages/VerifyMfa";
import Welcome from "../pages/Welcome";
import NotFound from "../pages/NotFound";
import ChatWidgetPage from "../pages/ChatWidgetPage";
import ClientWidget from "../components/ClientWidget";
import Dashboard from "../pages/Dashboard";
import Upload from "../features/upload/Upload";
import History from "../features/history/History";
import WhatsAppSetup from "../features/services/WhatsAppSetup";
import ServicesDashboard from "../features/services/ServicesDashboard";
import ChatSetup from "../features/services/ChatSetup";
import EmailSetup from "../features/services/EmailSetup";
import GoogleCalendar from "../features/services/GoogleCalendar";
import ClientSettings from "../features/settings/ClientSettings";
import MainLayout from "../layouts/MainLayout";
import PrivateRoutes from "./PrivateRoutes";
import WidgetPreview from "../pages/WidgetPreview";
import Terms from "../pages/Terms";
import PrivacyPolicy from "../pages/PrivacyPolicy";
import InboxHandoff from "../pages/InboxHandoff";

/* ✅ NUEVO */
import Templates from "../features/services/Templates";
import MarketingCampaigns from "../features/services/MarketingCampaigns";
import ClientsHub from "../features/services/ClientsHub";

export default function AppRouter() {
  return (
    <Routes>
      {/* Rutas públicas */}
      <Route path="/" element={<Navigate to="/login" />} />
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route path="/confirm" element={<Confirm />} />
      <Route path="/forgot-password" element={<ForgotPassword />} />
      <Route path="/reset-password" element={<ResetPassword />} />
      <Route path="/verify-mfa" element={<VerifyMfa />} />
      <Route path="/welcome" element={<Welcome />} />
      <Route path="/terms" element={<Terms />} />
      <Route path="/PrivacyPolicy" element={<PrivacyPolicy />} />

      <Route path="/chat-widget" element={<ChatWidgetPage />} />
      <Route path="/widget" element={<ClientWidget />} />
      <Route path="/widget-preview" element={<WidgetPreview />} />

      {/* Rutas protegidas */}
      <Route
        path="/dashboard"
        element={
          <PrivateRoutes>
            <MainLayout>
              <Dashboard />
            </MainLayout>
          </PrivateRoutes>
        }
      />

      <Route
        path="/inbox-handoff"
        element={
          <PrivateRoutes>
            <MainLayout>
              <InboxHandoff />
            </MainLayout>
          </PrivateRoutes>
        }
      />

      <Route
        path="/upload"
        element={
          <PrivateRoutes>
            <MainLayout>
              <Upload />
            </MainLayout>
          </PrivateRoutes>
        }
      />

      <Route
        path="/history"
        element={
          <PrivateRoutes>
            <MainLayout>
              <History />
            </MainLayout>
          </PrivateRoutes>
        }
      />

      <Route
        path="/services"
        element={
          <PrivateRoutes>
            <MainLayout>
              <ServicesDashboard />
            </MainLayout>
          </PrivateRoutes>
        }
      />

      <Route
        path="/services/chat"
        element={
          <PrivateRoutes>
            <MainLayout>
              <ChatSetup />
            </MainLayout>
          </PrivateRoutes>
        }
      />

      <Route
        path="/services/email"
        element={
          <PrivateRoutes>
            <MainLayout>
              <EmailSetup />
            </MainLayout>
          </PrivateRoutes>
        }
      />

      <Route
        path="/services/whatsapp"
        element={
          <PrivateRoutes>
            <MainLayout>
              <WhatsAppSetup />
            </MainLayout>
          </PrivateRoutes>
        }
      />

      <Route
        path="/services/calendar"
        element={
          <PrivateRoutes>
            <MainLayout>
              <GoogleCalendar />
            </MainLayout>
          </PrivateRoutes>
        }
      />

      {/* ✅ NUEVA RUTA: Templates */}
      <Route
        path="/services/templates"
        element={
          <PrivateRoutes>
            <MainLayout>
              <Templates />
            </MainLayout>
          </PrivateRoutes>
        }
      />

      <Route
        path="/services/marketing-campaigns"
        element={
          <PrivateRoutes>
            <MainLayout>
              <MarketingCampaigns />
            </MainLayout>
          </PrivateRoutes>
        }
      />

      <Route
        path="/services/clients"
        element={
          <PrivateRoutes>
            <MainLayout>
              <ClientsHub />
            </MainLayout>
          </PrivateRoutes>
        }
      />

      <Route
        path="/settings"
        element={
          <PrivateRoutes>
            <MainLayout>
              <ClientSettings />
            </MainLayout>
          </PrivateRoutes>
        }
      />

      {/* Catch all */}
      <Route path="*" element={<NotFound />} />
    </Routes>
  );
}
