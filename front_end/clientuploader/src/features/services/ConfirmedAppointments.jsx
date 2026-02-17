// ConfirmedAppointments.jsx — Evolvian Premium Light version (no Tailwind)
import { useEffect, useState } from "react";
import { useClientId } from "../../hooks/useClientId";
import { authFetch } from "../../lib/authFetch";
import { useLanguage } from "../../contexts/LanguageContext";

export default function ConfirmedAppointments() {
  const { t } = useLanguage();
  const clientId = useClientId();
  const [appointments, setAppointments] = useState([]);
  const [loading, setLoading] = useState(true);

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
        <div style={spinner}></div>
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
    <div style={pageStyle}>
      <div style={{ maxWidth: "1200px", margin: "0 auto" }}>
        <h2 style={titleStyle}>📅 {t("confirmed_appointments_title")}</h2>
        <p style={subtitleStyle}>
          {t("confirmed_appointments_subtitle")}
        </p>
        <AppointmentGrid appointments={appointments} />
      </div>
    </div>
  );
}

// ============================================================
// 🗓️ AppointmentGrid — Agrupar por día (Evolvian design)
// ============================================================
function AppointmentGrid({ appointments }) {
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
                  <div key={appt.id} style={appointmentBox}>
                    <div>
                      <p style={apptName}>{appt.user_name}</p>
                      <p style={apptEmail}>{appt.user_email}</p>
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
  padding: "2rem 3rem",
  fontFamily: "system-ui, sans-serif",
  color: "#274472",
  minHeight: "100vh",
};

const titleStyle = {
  fontSize: "1.8rem",
  color: "#F5A623",
  fontWeight: "bold",
  marginBottom: "0.5rem",
};

const subtitleStyle = {
  color: "#4A90E2",
  marginBottom: "2rem",
  fontSize: "1rem",
  maxWidth: "900px",
};

const gridContainer = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(360px, 1fr))",
  gap: "1.5rem",
};

const dayCard = {
  backgroundColor: "#FFFFFF",
  border: "1px solid #EDEDED",
  borderRadius: "14px",
  padding: "1.5rem",
  boxShadow: "0 2px 10px rgba(0,0,0,0.05)",
  display: "flex",
  flexDirection: "column",
  justifyContent: "space-between",
  transition: "all 0.2s ease",
};

const dayHeader = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  marginBottom: "1rem",
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
  minHeight: "100vh",
  color: "#274472",
  fontFamily: "system-ui, sans-serif",
};

const spinner = {
  width: "40px",
  height: "40px",
  border: "4px solid #EDEDED",
  borderTop: "4px solid #4A90E2",
  borderRadius: "50%",
  animation: "spin 1s linear infinite",
};

const emptyStateBox = {
  textAlign: "center",
  backgroundColor: "#FFFFFF",
  border: "1px solid #EDEDED",
  borderRadius: "14px",
  padding: "3rem",
  maxWidth: "600px",
  margin: "4rem auto",
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
