import { useEffect, useState } from "react";
import { useClientId } from "../../hooks/useClientId";
import { ButtonPrimary } from "../../components/ui/ButtonPrimary";
import { Card } from "../../components/ui/Card";
import { toast } from "../../components/ui/use-toast";
import { useLocation, useNavigate } from "react-router-dom";
import { useLanguage } from "../../contexts/LanguageContext";

export default function GoogleCalendar() {
  const { t } = useLanguage();
  const clientId = useClientId();
  const [connected, setConnected] = useState(false);
  const [availableSlots, setAvailableSlots] = useState([]);
  const location = useLocation();
  const navigate = useNavigate();

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    if (params.get("connected_calendar") === "true") {
      toast({
        title: t("calendar_connected_title"),
        description: t("calendar_connected_description"),
      });

      params.delete("connected_calendar");
      navigate({ pathname: location.pathname, search: params.toString() }, { replace: true });
    }
  }, [location, navigate]);

  useEffect(() => {
    if (!clientId) return;

    fetch(`/api/calendar/status?client_id=${clientId}`)
      .then((res) => res.json())
      .then((data) => {
        if (data.connected) {
          setConnected(true);
          const safeSlots = (data.available_slots || []).filter(
            (slot) => typeof slot === "string" || typeof slot === "number"
          );
          setAvailableSlots(safeSlots);
        }
      })
      .catch(() => {
        toast({
          title: t("calendar_error_title"),
          description: t("calendar_error_description"),
          variant: "destructive",
        });
      });
  }, [clientId]);

  const handleConnect = () => {
    const backendUrl = import.meta.env.VITE_API_URL || "http://localhost:8001";
    const redirectUrl = `${backendUrl}/api/auth/google_calendar/init?client_id=${clientId}`;
    console.log("🔗 Redirigiendo a:", redirectUrl);
    window.location.href = redirectUrl;
  };

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <h1 className="text-2xl font-bold mb-4">{t("calendar_title")}</h1>

      <Card>
        <p className="mb-4">{t("calendar_description")}</p>

        <div className="flex items-center gap-4 flex-wrap">
          <ButtonPrimary onClick={handleConnect} disabled={!clientId || connected}>
            {connected ? t("calendar_account_connected") : t("calendar_connect_button")}
          </ButtonPrimary>

          {connected && (
            <span className="text-sm text-green-600 font-medium">
              {t("calendar_active_connection")}
            </span>
          )}
        </div>
      </Card>

      {connected && (
        <div className="mt-8">
          <Card>
            <h2 className="text-xl font-semibold mb-2">{t("calendar_next_slots_title")}</h2>
            {availableSlots.length === 0 ? (
              <p className="text-sm text-gray-500">{t("calendar_no_slots")}</p>
            ) : (
              <ul className="list-disc ml-5">
                {availableSlots.map((slot, index) => {
                  const safeDate = new Date(slot);
                  const isValid = !isNaN(safeDate.getTime());
                  return (
                    <li key={index} className="text-sm">
                      {isValid ? safeDate.toLocaleString() : "⛔ Fecha inválida"}
                    </li>
                  );
                })}
              </ul>
            )}
          </Card>
        </div>
      )}
    </div>
  );
}
