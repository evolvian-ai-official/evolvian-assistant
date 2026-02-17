// DayView.jsx — 24h grid (Google-style light)

export default function DayView({ appointments }) {
  const hours = Array.from({ length: 24 }, (_, i) => i);

  const appointmentsByHour = appointments.reduce((acc, appt) => {
    const date = new Date(appt.scheduled_time);
    const hour = date.getHours();
    acc[hour] = acc[hour] || [];
    acc[hour].push(appt);
    return acc;
  }, {});

  return (
    <div style={container}>
      {hours.map((hour) => (
        <div key={hour} style={row}>
          <div style={hourColumn}>
            {hour.toString().padStart(2, "0")}:00
          </div>

          <div style={eventColumn}>
            {appointmentsByHour[hour]?.map((a) => (
              <div key={a.id} style={eventCard}>
                <strong>{a.user_name}</strong>
                <div style={{ fontSize: "0.75rem" }}>
                  {new Date(a.scheduled_time).toLocaleTimeString()}
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

const container = {
  border: "1px solid #EDEDED",
  borderRadius: 12,
  overflow: "hidden",
};

const row = {
  display: "flex",
  borderBottom: "1px solid #F0F0F0",
  minHeight: 60,
};

const hourColumn = {
  width: 80,
  padding: "0.5rem",
  fontSize: "0.8rem",
  color: "#999",
  borderRight: "1px solid #F0F0F0",
};

const eventColumn = {
  flex: 1,
  padding: "0.4rem",
};

const eventCard = {
  backgroundColor: "#A3D9B133",
  border: "1px solid #A3D9B180",
  borderRadius: 8,
  padding: "0.3rem 0.5rem",
  marginBottom: 4,
};
