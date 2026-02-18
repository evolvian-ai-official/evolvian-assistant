// ConfirmedAppointments.jsx — Evolvian Premium Light version (no Tailwind)
import { useEffect, useState } from "react";
import { useClientId } from "../../hooks/useClientId";
import { authFetch } from "../../lib/authFetch";
import { useLanguage } from "../../contexts/LanguageContext";
import "../../components/ui/internal-admin-responsive.css";

export default function ConfirmedAppointments() {
  const { t } = useLanguage();
  const clientId = useClientId();
  const [appointments, setAppointments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [isMobile, setIsMobile] = useState(
    typeof window !== "undefined" ? window.innerWidth < 768 : false
  );

  useEffect(() => {
    const onResize = () => setIsMobile(window.innerWidth < 768);
    onResize();
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  useEffect(() => {
    if (!clientId) return;

    const backendUrl =
      import.meta.env.VITE_API_URL ||
      (window.location.hostname === "localhost"
        ? "http://localhost:8001"
        : "https://evolvian-assistant.onrender.com");

    authFetch(`${backendUrl}/calendar/appointments?client_id=${clientId}`)
      .then(async (res) => {
        if (!res.ok) {
          throw new Error(`HTTP ${res.status}`);
        }
        return res.json();
      })
      .then((data) => {
        setAppointments(data.appointments || []);
        setLoading(false);
      })
      .catch((err) => {
        console.error("❌ Error loading appointments:", err);
        setLoading(false);
      });
  }, [clientId]);


  if (loading) {
    return (
      <div style={loaderContainer}>
        <div className="ia-spinner" style={spinner}></div>
        <p style={{ color: "#274472", marginTop: "1rem" }}>{t("appointments_loading")}</p>
      </div>
    );
  }

  if (!appointments.length) {
    return (
      <div style={emptyStateBox}>
        <img src="/logo-evolvian.svg" alt="Evolvian" style={logoStyle} />
        <h2 style={emptyTitle}>{t("no_confirmed_appointments_yet")}</h2>
        <p style={emptySubtitle}>
          {t("confirmed_appointments_will_appear_here")}
        </p>
      </div>
    );
  }

  return (
    <div className="ia-page" style={pageStyle}>
      <div className="ia-shell ia-services-shell" style={{ maxWidth: 1200 }}>
        <h2 style={titleStyle}>📅 {t("confirmed_appointments_title")}</h2>
        <p style={subtitleStyle}>
          {t("confirmed_appointments_subtitle")}
        </p>
        <AppointmentGrid appointments={appointments} isMobile={isMobile} />
      </div>
    </div>
  );
}

// ============================================================
// 🗓️ AppointmentGrid — Agrupar por día (Evolvian design)
// ============================================================
function AppointmentGrid({ appointments, isMobile }) {
  const { t, lang } = useLanguage();
  const grouped = appointments.reduce((acc, appt) => {
    const date = new Date(appt.scheduled_time);
    const key = date.toISOString().split("T")[0];
    acc[key] = acc[key] || [];
    acc[key].push(appt);
    return acc;
  }, {});

  const sortedDays = Object.keys(grouped).sort((a, b) => new Date(a) - new Date(b));

  return (
    <div style={gridContainer}>
      {sortedDays.map((day) => {
        const appts = grouped[day].sort(
          (a, b) => new Date(a.scheduled_time) - new Date(b.scheduled_time)
        );
        const locale = lang === "es" ? "es-ES" : "en-US";
        const dayLabel = new Date(day).toLocaleDateString(locale, {
          weekday: "long",
          month: "short",
          day: "numeric",
        });

        return (
            <div key={day} style={dayCard}>
              <div style={dayHeader}>
                <h3 style={dayTitle}>{dayLabel}</h3>
                <span style={dayCount}>{appts.length} {t("appointments_nav").toLowerCase()}</span>
              </div>
            <div>
              {appts.map((appt) => {
                const time = new Date(appt.scheduled_time).toLocaleTimeString([], {
                  hour: "2-digit",
                  minute: "2-digit",
                });
                return (
                  <div
                    key={appt.id}
                    style={{
                      ...appointmentBox,
                      flexDirection: isMobile ? "column" : "row",
                      alignItems: isMobile ? "flex-start" : "center",
                      gap: isMobile ? "0.55rem" : "0.35rem",
                    }}
                  >
                    <div>
                      <p style={apptName}>{appt.user_name}</p>
                      <p style={{ ...apptEmail, overflowWrap: "anywhere" }}>{appt.user_email}</p>
                    </div>
                    <div style={apptTime}>{time}</div>
                  </div>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ============================================================
// 🎨 Evolvian Premium Light Styles
// ============================================================

const pageStyle = {
  backgroundColor: "#FFFFFF",
  padding: "clamp(0.8rem, 0.6rem + 1vw, 1.4rem)",
  fontFamily: "system-ui, sans-serif",
  color: "#274472",
  minHeight: "100%",
};

const titleStyle = {
  fontSize: "clamp(1.3rem, 1.1rem + 0.9vw, 1.8rem)",
  color: "#F5A623",
  fontWeight: "bold",
  marginBottom: "0.5rem",
};

const subtitleStyle = {
  color: "#4A90E2",
  marginBottom: "1rem",
  fontSize: "1rem",
  maxWidth: "100%",
};

const gridContainer = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
  gap: "0.9rem",
};

const dayCard = {
  backgroundColor: "#FFFFFF",
  border: "1px solid #EDEDED",
  borderRadius: "14px",
  padding: "clamp(0.9rem, 0.8rem + 0.8vw, 1.3rem)",
  boxShadow: "0 2px 10px rgba(0,0,0,0.05)",
  display: "flex",
  flexDirection: "column",
  justifyContent: "space-between",
  transition: "all 0.2s ease",
};

const dayHeader = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "flex-start",
  marginBottom: "0.75rem",
  gap: "0.5rem",
  flexWrap: "wrap",
};

const dayTitle = {
  color: "#274472",
  fontSize: "1.1rem",
  fontWeight: "bold",
};

const dayCount = {
  fontSize: "0.85rem",
  color: "#F5A623",
  fontWeight: "600",
};

const appointmentBox = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  backgroundColor: "#A3D9B133",
  border: "1px solid #A3D9B180",
  borderRadius: "12px",
  padding: "0.8rem 1rem",
  marginBottom: "0.6rem",
  transition: "all 0.2s ease",
};

const apptName = {
  fontWeight: "600",
  fontSize: "0.95rem",
  color: "#274472",
  margin: 0,
};

const apptEmail = {
  fontSize: "0.8rem",
  color: "#4A90E2",
  margin: "0.2rem 0 0 0",
};

const apptTime = {
  fontWeight: "bold",
  color: "#274472",
  fontSize: "0.9rem",
  backgroundColor: "#E8F7ED",
  borderRadius: "8px",
  padding: "0.4rem 0.8rem",
};

const loaderContainer = {
  display: "flex",
  flexDirection: "column",
  alignItems: "center",
  justifyContent: "center",
  backgroundColor: "#FFFFFF",
  minHeight: "100%",
  color: "#274472",
  fontFamily: "system-ui, sans-serif",
};

const spinner = {
  width: "40px",
  height: "40px",
};

const emptyStateBox = {
  textAlign: "center",
  backgroundColor: "#FFFFFF",
  border: "1px solid #EDEDED",
  borderRadius: "14px",
  padding: "1.6rem",
  maxWidth: "min(92vw, 620px)",
  margin: "1.5rem auto",
  boxShadow: "0 3px 12px rgba(0,0,0,0.05)",
};

const logoStyle = {
  width: "56px",
  height: "56px",
  borderRadius: "50%",
  marginBottom: "1rem",
};

const emptyTitle = {
  fontSize: "1.4rem",
  color: "#F5A623",
  marginBottom: "0.5rem",
  fontWeight: "bold",
};

const emptySubtitle = {
  color: "#4A90E2",
  fontSize: "0.95rem",
};
