// src/features/calendar/ShowAppointments.jsx
// Evolvian Light — Appointment List + Calendar Views

import { useEffect, useState, useMemo } from "react";
import { useClientId } from "../../hooks/useClientId";
import { useLanguage } from "../../contexts/LanguageContext";
import UpdateCancelAppointmentModal from "../services/update_cancel_appointment";
import { authFetch } from "../../lib/authFetch";

import DayView from "../services/DayView";
import WeekView from "../services/WeekView";
import MonthView from "../services/MonthView";
import "../../components/ui/internal-admin-responsive.css";

/* 🌐 API ENV */
const API_BASE_URL =
  import.meta.env.MODE === "development"
    ? "http://localhost:8001"
    : "https://evolvian-assistant.onrender.com";

export default function ShowAppointments({ refreshKey = 0 }) {
  const clientId = useClientId();
  const { t } = useLanguage();
  const [isMobile, setIsMobile] = useState(
    typeof window !== "undefined" ? window.innerWidth < 768 : false
  );

  const [appointments, setAppointments] = useState([]);
  const [googleBusyRanges, setGoogleBusyRanges] = useState([]);
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

  const toDateInputValue = (date) => {
    const y = date.getFullYear();
    const m = String(date.getMonth() + 1).padStart(2, "0");
    const d = String(date.getDate()).padStart(2, "0");
    return `${y}-${m}-${d}`;
  };

  const toValidDate = (value) => {
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? null : date;
  };

  const formatDateTime = (value) => {
    const date = toValidDate(value);
    return date ? date.toLocaleString() : "Fecha inválida";
  };

  const getVisibleRange = () => {
    if (viewMode === "day") {
      return { from: new Date(currentDate), to: new Date(currentDate) };
    }

    if (viewMode === "week") {
      const start = new Date(currentDate);
      start.setDate(start.getDate() - start.getDay());
      const end = new Date(start);
      end.setDate(start.getDate() + 6);
      return { from: start, to: end };
    }

    const monthStart = new Date(currentDate.getFullYear(), currentDate.getMonth(), 1);
    const monthEnd = new Date(currentDate.getFullYear(), currentDate.getMonth() + 1, 0);
    return { from: monthStart, to: monthEnd };
  };

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

  useEffect(() => {
    if (!clientId || viewMode === "list") {
      setGoogleBusyRanges([]);
      return;
    }

    const fetchGoogleBusyRanges = async () => {
      try {
        const visibleRange = getVisibleRange();
        const fromDate = toDateInputValue(visibleRange.from);
        const toDate = toDateInputValue(visibleRange.to);

        const res = await authFetch(
          `${API_BASE_URL}/calendar/google_busy_slots?client_id=${clientId}&from_date=${fromDate}&to_date=${toDate}`
        );
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const payload = await res.json();
        setGoogleBusyRanges(Array.isArray(payload?.busy_ranges) ? payload.busy_ranges : []);
      } catch (err) {
        console.error("Failed loading Google busy ranges", err);
        setGoogleBusyRanges([]);
      }
    };

    fetchGoogleBusyRanges();
  }, [clientId, viewMode, currentDate]);

  useEffect(() => {
    const onResize = () => setIsMobile(window.innerWidth < 768);
    onResize();
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

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
    const scheduled = toValidDate(appointment.scheduled_time);

    if (!scheduled) return appointment.status || "pending";

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
      const da = toValidDate(a.scheduled_time);
      const db = toValidDate(b.scheduled_time);
      const ta = da ? da.getTime() : 0;
      const tb = db ? db.getTime() : 0;
      return filters.order === "asc" ? ta - tb : tb - ta;
    });

    return list;
  }, [appointments, filters]);

  const appointmentCounters = useMemo(() => {
    const now = new Date();
    const startOfDay = new Date(now);
    startOfDay.setHours(0, 0, 0, 0);

    const startOfWeek = new Date(startOfDay);
    const dayIndex = startOfWeek.getDay();
    const diffToMonday = (dayIndex + 6) % 7;
    startOfWeek.setDate(startOfWeek.getDate() - diffToMonday);

    const startOfMonth = new Date(startOfDay);
    startOfMonth.setDate(1);

    let day = 0;
    let week = 0;
    let month = 0;

    for (const appointment of appointments) {
      const dt = toValidDate(appointment.scheduled_time);
      if (!dt) continue;

      if (dt >= startOfMonth) month += 1;
      if (dt >= startOfWeek) week += 1;
      if (dt >= startOfDay) day += 1;
    }

    return {
      total: appointments.length,
      month,
      week,
      day,
    };
  }, [appointments]);

  const googleBusyEvents = useMemo(() => {
    const events = [];
    const stepMs = 30 * 60 * 1000;

    (googleBusyRanges || []).forEach((range, rangeIndex) => {
      const rangeStart = new Date(range.start);
      const rangeEnd = new Date(range.end);
      if (Number.isNaN(rangeStart.getTime()) || Number.isNaN(rangeEnd.getTime()) || rangeEnd <= rangeStart) {
        return;
      }

      let cursor = new Date(rangeStart.getTime());
      let guard = 0;
      while (cursor < rangeEnd && guard < 3000) {
        events.push({
          id: `google-busy-${rangeIndex}-${cursor.toISOString()}`,
          source: "google_busy",
          user_name: "Ocupado (Google)",
          scheduled_time: cursor.toISOString(),
          status: "confirmed",
          appointment_type: "google_busy",
          channel: "google",
        });
        cursor = new Date(cursor.getTime() + stepMs);
        guard += 1;
      }

      if (guard === 0) {
        events.push({
          id: `google-busy-${rangeIndex}-${rangeStart.toISOString()}`,
          source: "google_busy",
          user_name: "Ocupado (Google)",
          scheduled_time: rangeStart.toISOString(),
          status: "confirmed",
          appointment_type: "google_busy",
          channel: "google",
        });
      }
    });

    return events;
  }, [googleBusyRanges]);

  const calendarAppointments = useMemo(
    () => [...filteredAppointments, ...googleBusyEvents],
    [filteredAppointments, googleBusyEvents]
  );

  /* =========================
     UI
     ========================= */
  return (
    <div style={container}>
      <h3 style={sectionTitle}>{t("appointments_created_title")}</h3>
      <div style={counterRow}>
        <span style={counterBadge}>{t("appointments_nav") || "Appointments"} · Total: {appointmentCounters.total}</span>
        <span style={counterBadge}>{t("appointments_nav") || "Appointments"} · {t("month") || "Month"}: {appointmentCounters.month}</span>
        <span style={counterBadge}>{t("appointments_nav") || "Appointments"} · {t("week") || "Week"}: {appointmentCounters.week}</span>
        <span style={counterBadge}>{t("appointments_nav") || "Appointments"} · {t("day") || "Day"}: {appointmentCounters.day}</span>
      </div>

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
          appointments={calendarAppointments}
          currentDate={currentDate}
        />
      )}

      {!loading && viewMode === "week" && (
        <WeekView
          appointments={calendarAppointments}
          currentDate={currentDate}
        />
      )}

      {!loading && viewMode === "month" && (
        <MonthView
          appointments={calendarAppointments}
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
                <div
                  style={{
                    ...row,
                    flexDirection: isMobile ? "column" : "row",
                    alignItems: isMobile ? "flex-start" : "center",
                  }}
                >
                  <strong>{a.user_name}</strong>

                  <div
                    style={{
                      ...rightRow,
                      width: isMobile ? "100%" : "auto",
                      justifyContent: isMobile ? "space-between" : "flex-end",
                    }}
                  >
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

                <div style={{ ...meta, marginTop: isMobile ? "0.35rem" : 0 }}>
                  <span>
                    📅 {formatDateTime(a.scheduled_time)}
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
  fontSize: "clamp(1.05rem, 0.95rem + 0.4vw, 1.2rem)",
  fontWeight: "bold",
  color: "#274472",
  marginBottom: "0.5rem",
};

const counterRow = {
  display: "flex",
  gap: "0.6rem",
  marginBottom: "1rem",
  flexWrap: "wrap",
};

const counterBadge = {
  backgroundColor: "#EAF7F0",
  color: "#1F6B4A",
  border: "1px solid #CDEBDB",
  borderRadius: "999px",
  padding: "0.35rem 0.75rem",
  fontSize: "0.85rem",
  fontWeight: 600,
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
  minWidth: 0,
  flex: "1 1 180px",
};

const filterSelect = {
  padding: "0.5rem 0.65rem",
  borderRadius: 10,
  border: "1px solid #EDEDED",
  backgroundColor: "#FFFFFF",
  minWidth: 0,
  flex: "1 1 170px",
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
  gap: "0.55rem",
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
