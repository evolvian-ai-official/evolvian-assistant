import { useState } from "react";
import { useLanguage } from "../../contexts/LanguageContext";
import "../../components/ui/internal-admin-responsive.css";

export default function AppointmentsFilter({ onChange }) {
  const { t } = useLanguage();
  const [filters, setFilters] = useState({
    name: "",
    phone: "",
    status: "all",
    order: "desc",
  });

  const update = (key, value) => {
    const next = { ...filters, [key]: value };
    setFilters(next);
    onChange?.(next);
  };

  return (
    <div
      style={{
        display: "flex",
        gap: "0.7rem",
        marginBottom: "1.1rem",
        flexWrap: "wrap",
      }}
    >
      <input
        className="ia-form-input"
        style={{ flex: "1 1 180px", minWidth: 0 }}
        placeholder={t("appointments_search_name")}
        value={filters.name}
        onChange={(e) => update("name", e.target.value)}
      />

      <input
        className="ia-form-input"
        style={{ flex: "1 1 180px", minWidth: 0 }}
        placeholder={t("appointments_search_phone")}
        value={filters.phone}
        onChange={(e) => update("phone", e.target.value)}
      />

      <select
        className="ia-form-input"
        style={{ flex: "1 1 170px", minWidth: 0 }}
        value={filters.status}
        onChange={(e) => update("status", e.target.value)}
      >
        <option value="all">{t("appointments_all_statuses")}</option>
        <option value="scheduled">{t("appointments_scheduled")}</option>
        <option value="completed">{t("appointments_completed")}</option>
        <option value="cancelled">{t("appointments_cancelled")}</option>
      </select>

      <select
        className="ia-form-input"
        style={{ flex: "1 1 170px", minWidth: 0 }}
        value={filters.order}
        onChange={(e) => update("order", e.target.value)}
      >
        <option value="desc">{t("appointments_newest_first")}</option>
        <option value="asc">{t("appointments_oldest_first")}</option>
      </select>
    </div>
  );
}
