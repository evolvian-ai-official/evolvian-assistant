// WeekView.jsx — 7 days × 24 hours

export default function WeekView({ appointments, currentDate }) {
  const startOfWeek = new Date(currentDate);
  startOfWeek.setDate(startOfWeek.getDate() - startOfWeek.getDay());

  const toValidDate = (value) => {
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? null : date;
  };

  const days = Array.from({ length: 7 }, (_, i) => {
    const d = new Date(startOfWeek);
    d.setDate(startOfWeek.getDate() + i);
    return d;
  });

  const hours = Array.from({ length: 24 }, (_, i) => i);

  return (
    <div style={wrapper}>
      <div style={innerGrid}>
        {/* Header */}
        <div style={headerRow}>
          <div style={{ width: "clamp(58px, 16vw, 80px)" }}></div>
          {days.map((d, i) => (
            <div key={i} style={dayHeader}>
              {d.toLocaleDateString("en-US", {
                weekday: "short",
                day: "numeric",
              })}
            </div>
          ))}
        </div>

        {/* Grid */}
        {hours.map((hour) => (
          <div key={hour} style={hourRow}>
            <div style={hourLabel}>
              {hour.toString().padStart(2, "0")}:00
            </div>

            {days.map((day, i) => {
              const events = appointments.filter((a) => {
                const d = toValidDate(a.scheduled_time);
                if (!d) return false;
                return (
                  d.getDate() === day.getDate() &&
                  d.getMonth() === day.getMonth() &&
                  d.getFullYear() === day.getFullYear() &&
                  d.getHours() === hour
                );
              });

              return (
                <div key={i} style={cell}>
                  {events.map((e) => (
                    <div
                      key={e.id}
                      style={e.source === "google_busy" ? googleBusyCard : eventCard}
                    >
                      {e.source === "google_busy" ? "Ocupado (Google)" : e.user_name}
                    </div>
                  ))}
                </div>
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
}

const wrapper = {
  border: "1px solid #EDEDED",
  borderRadius: 12,
  overflowX: "auto",
  backgroundColor: "#FFFFFF",
};

const innerGrid = {
  minWidth: 840,
};

const headerRow = {
  display: "flex",
  borderBottom: "1px solid #EDEDED",
};

const dayHeader = {
  flex: "1 0 108px",
  minWidth: 108,
  padding: "0.5rem",
  textAlign: "center",
  fontWeight: "600",
  borderLeft: "1px solid #F0F0F0",
};

const hourRow = {
  display: "flex",
  borderBottom: "1px solid #F5F5F5",
  minHeight: 60,
};

const hourLabel = {
  width: "clamp(58px, 16vw, 80px)",
  padding: "0.4rem",
  fontSize: "0.75rem",
  color: "#999",
  borderRight: "1px solid #F0F0F0",
  flex: "0 0 auto",
};

const cell = {
  flex: "1 0 108px",
  minWidth: 108,
  borderLeft: "1px solid #F5F5F5",
  padding: "0.3rem",
};

const eventCard = {
  backgroundColor: "#4A90E233",
  border: "1px solid #4A90E2",
  borderRadius: 6,
  padding: "0.2rem 0.4rem",
  fontSize: "0.75rem",
  overflowWrap: "anywhere",
};

const googleBusyCard = {
  backgroundColor: "#FFE9E5",
  border: "1px solid #E85D4A",
  borderRadius: 6,
  padding: "0.2rem 0.4rem",
  fontSize: "0.75rem",
  overflowWrap: "anywhere",
  color: "#8A2E23",
};
