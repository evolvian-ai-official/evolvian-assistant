// MonthView.jsx — Real calendar grid (7 columns)

export default function MonthView({ appointments, currentDate }) {
  const year = currentDate.getFullYear();
  const month = currentDate.getMonth();

  const firstDay = new Date(year, month, 1);
  const startDay = firstDay.getDay();

  const daysInMonth = new Date(year, month + 1, 0).getDate();

  const cells = [];

  // empty cells before first day
  for (let i = 0; i < startDay; i++) {
    cells.push(null);
  }

  for (let d = 1; d <= daysInMonth; d++) {
    cells.push(new Date(year, month, d));
  }

  return (
    <div style={wrapper}>
      <div style={innerGrid}>
        {/* Week headers */}
        <div style={headerRow}>
          {["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].map((day) => (
            <div key={day} style={dayHeader}>{day}</div>
          ))}
        </div>

        <div style={grid}>
          {cells.map((date, index) => {
            if (!date) {
              return <div key={index} style={emptyCell}></div>;
            }

            const dayEvents = appointments.filter((a) => {
              const d = new Date(a.scheduled_time);
              return (
                d.getDate() === date.getDate() &&
                d.getMonth() === date.getMonth() &&
                d.getFullYear() === date.getFullYear()
              );
            });

            return (
              <div key={index} style={cell}>
                <div style={dateLabel}>{date.getDate()}</div>

                {dayEvents.map((e) => (
                  <div
                    key={e.id}
                    style={e.source === "google_busy" ? googleBusyBadge : eventBadge}
                  >
                    {new Date(e.scheduled_time).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}{" "}
                    {e.source === "google_busy" ? "Ocupado (Google)" : e.user_name}
                  </div>
                ))}
              </div>
            );
          })}
        </div>
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
  minWidth: 760,
};

const headerRow = {
  display: "grid",
  gridTemplateColumns: "repeat(7, 1fr)",
  backgroundColor: "#F9F9F9",
  borderBottom: "1px solid #EDEDED",
};

const dayHeader = {
  padding: "0.5rem",
  textAlign: "center",
  fontWeight: "600",
  fontSize: "0.85rem",
};

const grid = {
  display: "grid",
  gridTemplateColumns: "repeat(7, 1fr)",
};

const cell = {
  minHeight: 108,
  borderRight: "1px solid #F0F0F0",
  borderBottom: "1px solid #F0F0F0",
  padding: "0.4rem",
  position: "relative",
};

const emptyCell = {
  minHeight: 108,
  borderRight: "1px solid #F0F0F0",
  borderBottom: "1px solid #F0F0F0",
};

const dateLabel = {
  fontSize: "0.8rem",
  fontWeight: "600",
  marginBottom: "0.3rem",
};

const eventBadge = {
  fontSize: "0.7rem",
  backgroundColor: "#A3D9B133",
  border: "1px solid #A3D9B180",
  borderRadius: 6,
  padding: "0.2rem 0.3rem",
  marginBottom: 2,
  overflowWrap: "anywhere",
};

const googleBusyBadge = {
  fontSize: "0.7rem",
  backgroundColor: "#FFE9E5",
  border: "1px solid #E85D4A",
  borderRadius: 6,
  padding: "0.2rem 0.3rem",
  marginBottom: 2,
  overflowWrap: "anywhere",
  color: "#8A2E23",
};
