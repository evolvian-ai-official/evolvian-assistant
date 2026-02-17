// src/features/calendar/ShowAppointments.jsx
// Evolvian Light — Appointment List + Calendar Views

import { useEffect, useState, useMemo } from "react";
import { useClientId } from "../../hooks/useClientId";
import { useLanguage } from "../../contexts/LanguageContext";
import UpdateCancelAppointmentModal from "../services/update_cancel_appointment";

import DayView from "../services/DayView";
import WeekView from "../services/WeekView";
import MonthView from "../services/MonthView";

/* 🌐 API ENV */
const API_BASE_URL =
  import.meta.env.MODE === "development"
    ? "http://localhost:8001"
    : "https://evolvian-assistant.onrender.com";

export default function ShowAppointments({ refreshKey = 0 }) {
  const clientId = useClientId();
  const { t } = useLanguage();

  const [appointments, setAppointments] = useState([]);
  const [loading, setLoading] = useState(true);

  /* 🗓 View Mode */
  const [viewMode, setViewMode] = useState("list");
  const [currentDate, setCurrentDate] = useState(new Date());

  const MAX_FORWARD_DATE = new Date(
    new Date().setFullYear(new Date().getFullYear() + 1)
  );

  /* 🔍 Filters */
  const [filters, setFilters] = useState({
    name: "",
    phone: "",
    status: "all",
    order: "desc",
  });

  /* 🧩 Modal state */
  const [showCancelModal, setShowCancelModal] = useState(false);
  const [selectedAppointmentId, setSelectedAppointmentId] = useState(null);

  /* =========================
     Fetch appointments
     ========================= */
  const fetchAppointments = async () => {
    if (!clientId) return;

    setLoading(true);
    try {
      const res = await fetch(
        `${API_BASE_URL}/appointments/show?client_id=${clientId}`
      );

      if (!res.ok) throw new Error(t("appointments_fetch_failed"));

      const data = await res.json();
      setAppointments(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error("Failed to load appointments", err);
      setAppointments([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAppointments();
  }, [clientId, refreshKey]);

  /* =========================
     Navigation
     ========================= */
  const goPrevious = () => {
    const d = new Date(currentDate);
    if (viewMode === "day") d.setDate(d.getDate() - 1);
    if (viewMode === "week") d.setDate(d.getDate() - 7);
    if (viewMode === "month") d.setMonth(d.getMonth() - 1);
    setCurrentDate(d);
  };

  const goNext = () => {
    const d = new Date(currentDate);
    if (viewMode === "day") d.setDate(d.getDate() + 1);
    if (viewMode === "week") d.setDate(d.getDate() + 7);
    if (viewMode === "month") d.setMonth(d.getMonth() + 1);

    if (d > MAX_FORWARD_DATE) return;
    setCurrentDate(d);
  };

  const goToday = () => setCurrentDate(new Date());

  /* =========================
     Helpers
     ========================= */
  const resolveStatus = (appointment) => {
    if (appointment.status === "cancelled") return "cancelled";

    const now = new Date();
    const scheduled = new Date(appointment.scheduled_time);

    if (now > scheduled) return "closed";
    if (appointment.status === "confirmed") return "confirmed";
    return "pending";
  };

  const statusLabel = (status) => {
    const map = {
      pending: t("appointments_pending"),
      confirmed: t("appointments_confirmed"),
      closed: t("appointments_closed"),
      cancelled: t("appointments_cancelled"),
    };
    return map[status] || status;
  };

  /* =========================
     Apply filters
     ========================= */
  const filteredAppointments = useMemo(() => {
    let list = [...appointments];

    if (filters.name) {
      list = list.filter((a) =>
        a.user_name?.toLowerCase().includes(filters.name.toLowerCase())
      );
    }

    if (filters.phone) {
      list = list.filter((a) => a.user_phone?.includes(filters.phone));
    }

    if (filters.status !== "all") {
      list = list.filter((a) => resolveStatus(a) === filters.status);
    }

    list.sort((a, b) => {
      const da = new Date(a.scheduled_time);
      const db = new Date(b.scheduled_time);
      return filters.order === "asc" ? da - db : db - da;
    });

    return list;
  }, [appointments, filters]);

  /* =========================
     UI
     ========================= */
  return (
    <div style={container}>
      <h3 style={sectionTitle}>{t("appointments_created_title")}</h3>

      {/* 🔄 View Switcher */}
      <div style={viewBar}>
        <button style={viewBtn(viewMode === "list")} onClick={() => setViewMode("list")}>{t("appointments_view_list")}</button>
        <button style={viewBtn(viewMode === "day")} onClick={() => setViewMode("day")}>{t("appointments_view_day")}</button>
        <button style={viewBtn(viewMode === "week")} onClick={() => setViewMode("week")}>{t("appointments_view_week")}</button>
        <button style={viewBtn(viewMode === "month")} onClick={() => setViewMode("month")}>{t("appointments_view_month")}</button>
      </div>

      {/* 📅 Navigation (calendar only) */}
      {viewMode !== "list" && (
        <div style={navBar}>
          <button style={navBtn} onClick={goPrevious}>←</button>
          <span style={{ fontWeight: 600 }}>
            {currentDate.toLocaleDateString()}
          </span>
          <button style={navBtn} onClick={goNext}>→</button>
          <button style={todayBtn} onClick={goToday}>{t("appointments_today")}</button>
        </div>
      )}

      {/* 🔍 Filters (SIEMPRE visibles) */}
      <div style={filterRow}>
        <input
          style={filterInput}
          placeholder={t("appointments_search_name")}
          value={filters.name}
          onChange={(e) =>
            setFilters({ ...filters, name: e.target.value })
          }
        />

        <input
          style={filterInput}
          placeholder={t("appointments_search_phone")}
          value={filters.phone}
          onChange={(e) =>
            setFilters({ ...filters, phone: e.target.value })
          }
        />

        <select
          style={filterSelect}
          value={filters.status}
          onChange={(e) =>
            setFilters({ ...filters, status: e.target.value })
          }
        >
          <option value="all">{t("appointments_all_statuses")}</option>
          <option value="pending">{t("appointments_pending")}</option>
          <option value="confirmed">{t("appointments_confirmed")}</option>
          <option value="closed">{t("appointments_closed")}</option>
          <option value="cancelled">{t("appointments_cancelled")}</option>
        </select>

        <select
          style={filterSelect}
          value={filters.order}
          onChange={(e) =>
            setFilters({ ...filters, order: e.target.value })
          }
        >
          <option value="desc">{t("appointments_newest_first")}</option>
          <option value="asc">{t("appointments_oldest_first")}</option>
        </select>
      </div>

      {loading && <p style={hint}>{t("appointments_loading")}</p>}

      {/* 📅 Calendar Views */}
      {!loading && viewMode === "day" && (
        <DayView
          appointments={filteredAppointments}
          currentDate={currentDate}
        />
      )}

      {!loading && viewMode === "week" && (
        <WeekView
          appointments={filteredAppointments}
          currentDate={currentDate}
        />
      )}

      {!loading && viewMode === "month" && (
        <MonthView
          appointments={filteredAppointments}
          currentDate={currentDate}
        />
      )}

      {/* 📋 List View (original intact) */}
      {!loading && viewMode === "list" && filteredAppointments.length > 0 && (
        <div style={list}>
          {filteredAppointments.map((a) => {
            const status = resolveStatus(a);
            const canEdit = status === "confirmed" || status === "pending";

            return (
              <div key={a.id} style={card}>
                <div style={row}>
                  <strong>{a.user_name}</strong>

                  <div style={rightRow}>
                    {canEdit && (
                      <button
                        title={t("appointments_edit_cancel_title")}
                        style={editIconBtn}
                        onClick={() => {
                          setSelectedAppointmentId(a.id);
                          setShowCancelModal(true);
                        }}
                      >
                        ✏️
                      </button>
                    )}

                    <span style={statusBadge(status)}>
                      {statusLabel(status)}
                    </span>
                  </div>
                </div>

                <div style={meta}>
                  <span>
                    📅 {new Date(a.scheduled_time).toLocaleString()}
                  </span>
                  <span>📌 {a.appointment_type}</span>
                  <span>💬 {a.channel}</span>
                </div>

                <div style={contactRow}>
                  {a.user_phone && <span>📞 {a.user_phone}</span>}
                  {a.user_email && <span>✉️ {a.user_email}</span>}
                </div>
              </div>
            );
          })}
        </div>
      )}

      <UpdateCancelAppointmentModal
        open={showCancelModal}
        appointmentId={selectedAppointmentId}
        onClose={() => {
          setShowCancelModal(false);
          setSelectedAppointmentId(null);
        }}
        onSuccess={() => fetchAppointments()}
      />
    </div>
  );
}

/* 🎨 Styles */

const container = { marginTop: "2rem" };

const sectionTitle = {
  fontSize: "1.2rem",
  fontWeight: "bold",
  color: "#274472",
  marginBottom: "1rem",
};

const viewBar = {
  display: "flex",
  gap: "0.5rem",
  marginBottom: "1rem",
  flexWrap: "wrap",
};

const viewBtn = (active) => ({
  padding: "0.4rem 0.8rem",
  borderRadius: 8,
  border: "1px solid #EDEDED",
  backgroundColor: active ? "#A3D9B1" : "#FFFFFF",
  cursor: "pointer",
});

const navBar = {
  display: "flex",
  gap: "1rem",
  alignItems: "center",
  marginBottom: "1rem",
  flexWrap: "wrap",
};

const navBtn = {
  border: "none",
  background: "#EDEDED",
  padding: "0.4rem 0.7rem",
  borderRadius: 8,
  cursor: "pointer",
};

const todayBtn = {
  border: "none",
  background: "#A3D9B1",
  padding: "0.4rem 0.7rem",
  borderRadius: 8,
  cursor: "pointer",
};

const filterRow = {
  display: "flex",
  gap: "0.6rem",
  marginBottom: "1rem",
  flexWrap: "wrap",
};

const filterInput = {
  padding: "0.5rem 0.65rem",
  borderRadius: 10,
  border: "1px solid #EDEDED",
  minWidth: 160,
};

const filterSelect = {
  padding: "0.5rem 0.65rem",
  borderRadius: 10,
  border: "1px solid #EDEDED",
  backgroundColor: "#FFFFFF",
};

const hint = {
  fontSize: "0.9rem",
  color: "#7A7A7A",
};

const list = {
  display: "flex",
  flexDirection: "column",
  gap: "0.75rem",
};

const card = {
  backgroundColor: "#FFFFFF",
  border: "1px solid #EDEDED",
  borderRadius: 12,
  padding: "0.9rem 1rem",
};

const row = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  marginBottom: "0.4rem",
};

const rightRow = {
  display: "flex",
  alignItems: "center",
  gap: "0.5rem",
};

const meta = {
  display: "flex",
  flexWrap: "wrap",
  gap: "1rem",
  fontSize: "0.85rem",
  color: "#4A4A4A",
};

const contactRow = {
  marginTop: "0.5rem",
  display: "flex",
  flexWrap: "wrap",
  gap: "1.2rem",
  fontSize: "0.85rem",
  color: "#274472",
};

const editIconBtn = {
  background: "transparent",
  border: "none",
  cursor: "pointer",
  fontSize: "1rem",
};

const statusBadge = (status) => {
  const map = {
    pending: "#F5A623",
    confirmed: "#4A90E2",
    closed: "#2EB39A",
    cancelled: "#9B9B9B",
  };

  return {
    fontSize: "0.75rem",
    padding: "0.25rem 0.6rem",
    borderRadius: 999,
    backgroundColor: map[status] || "#999",
    color: "#FFFFFF",
    textTransform: "capitalize",
  };
};
