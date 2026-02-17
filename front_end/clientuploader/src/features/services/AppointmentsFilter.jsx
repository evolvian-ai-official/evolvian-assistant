// src/features/services/AppointmentsFilter.jsx
// AppointmentsFilter — Evolvian Light

import { useState } from "react";
import { useLanguage } from "../../contexts/LanguageContext";

export default function AppointmentsFilter({ onChange }) {
  const { t } = useLanguage();
  const [filters, setFilters] = useState({
    name: "",
    phone: "",
    status: "all",
    order: "desc", // asc | desc
  });

  const update = (key, value) => {
    const next = { ...filters, [key]: value };
    setFilters(next);
    onChange?.(next);
  };

  return (
    <div style={container}>
      <input
        style={input}
        placeholder={t("appointments_search_name")}
        value={filters.name}
        onChange={(e) => update("name", e.target.value)}
      />

      <input
        style={input}
        placeholder={t("appointments_search_phone")}
        value={filters.phone}
        onChange={(e) => update("phone", e.target.value)}
      />

      <select
        style={select}
        value={filters.status}
        onChange={(e) => update("status", e.target.value)}
      >
        <option value="all">{t("appointments_all_statuses")}</option>
        <option value="scheduled">{t("appointments_scheduled")}</option>
        <option value="completed">{t("appointments_completed")}</option>
        <option value="cancelled">{t("appointments_cancelled")}</option>
      </select>

      <select
        style={select}
        value={filters.order}
        onChange={(e) => update("order", e.target.value)}
      >
        <option value="desc">{t("appointments_newest_first")}</option>
        <option value="asc">{t("appointments_oldest_first")}</option>
      </select>
    </div>
  );
}

/* 🎨 Styles */
const container = {
  display: "flex",
  gap: "0.75rem",
  marginBottom: "1.25rem",
  flexWrap: "wrap",
};

const input = {
  padding: "0.55rem 0.7rem",
  borderRadius: 10,
  border: "1px solid #EDEDED",
  minWidth: 180,
};

const select = {
  padding: "0.55rem 0.7rem",
  borderRadius: 10,
  border: "1px solid #EDEDED",
  backgroundColor: "#FFFFFF",
};
