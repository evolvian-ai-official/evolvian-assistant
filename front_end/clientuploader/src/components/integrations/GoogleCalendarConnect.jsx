import { useEffect, useState } from "react";
import { useClientId } from "@/hooks/useClientId";
import { Button } from "@/components/ui/button";
import { Loader2, CalendarCheck, LinkIcon } from "lucide-react";
import { toast } from "@/components/ui/use-toast";

export default function GoogleCalendarConnect() {
  const clientId = useClientId();
  const [isConnected, setIsConnected] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!clientId) return;

    const checkIntegration = async () => {
      try {
        const res = await fetch(`/api/calendar/status?client_id=${clientId}`);
        const data = await res.json();
        if (data?.connected) {
          setIsConnected(true);
        }
      } catch (err) {
        console.error("❌ Error al verificar integración:", err);
      } finally {
        setLoading(false);
      }
    };

    checkIntegration();
  }, [clientId]);

  const handleConnect = () => {
    const redirectURL = `/api/google-calendar/authorize?client_id=${clientId}`;
    window.location.href = redirectURL;
  };

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-muted-foreground">
        <Loader2 className="animate-spin w-4 h-4" />
        Cargando conexión con Google Calendar...
      </div>
    );
  }

  return (
    <div className="border p-4 rounded-xl bg-muted">
      <h3 className="font-bold mb-2">Integración con Google Calendar</h3>
      <p className="text-sm mb-4">
        Conecta tu cuenta de Google para permitir que tus clientes agenden citas directamente desde tu asistente AI.
      </p>

      {isConnected ? (
        <div className="flex items-center gap-2 text-green-600 font-medium">
          <CalendarCheck className="w-4 h-4" />
          Cuenta de Google conectada
        </div>
      ) : (
        <Button variant="outline" onClick={handleConnect}>
          <LinkIcon className="w-4 h-4 mr-2" />
          Conectar cuenta de Google
        </Button>
      )}
    </div>
  );
}
