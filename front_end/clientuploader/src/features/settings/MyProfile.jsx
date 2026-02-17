import { useEffect, useState, useMemo } from "react";
import { useClientId } from "../../hooks/useClientId";
import { useLanguage } from "../../contexts/LanguageContext";
import countries from "../../assets/countries.json";
import { authFetch, getAuthHeaders } from "../../lib/authFetch";

/* =========================
   Static Dropdown Options
========================= */

const industries = [
  "Software",
  "Education",
  "Healthcare",
  "Finance",
  "Retail",
  "Manufacturing",
  "Consulting",
  "Other",
];

const roles = [
  "Founder / CEO",
  "CMO / Marketing Manager",
  "Customer Support",
  "Operations Manager",
  "Sales Executive",
  "IT Manager",
  "Product Manager",
  "Developer / Engineer",
  "HR / People",
  "Other",
];

const companySizes = [
  "1-10 employees",
  "11-50 employees",
  "51-200 employees",
  "201-500 employees",
  "501-1000 employees",
  "More than 1000 employees",
];



const timezones = [
  // Universal
  "UTC",

  // 🇺🇸 North America
  "America/New_York",       // Eastern (US, Canada)
  "America/Chicago",        // Central
  "America/Denver",         // Mountain
  "America/Los_Angeles",    // Pacific
  "America/Phoenix",
  "America/Toronto",
  "America/Vancouver",
  "America/Mexico_City",
  "America/Bogota",
  "America/Lima",
  "America/Santiago",
  "America/Argentina/Buenos_Aires",

  // 🇪🇺 Europe
  "Europe/London",
  "Europe/Dublin",
  "Europe/Paris",
  "Europe/Madrid",
  "Europe/Berlin",
  "Europe/Rome",
  "Europe/Amsterdam",
  "Europe/Brussels",
  "Europe/Zurich",
  "Europe/Vienna",
  "Europe/Warsaw",
  "Europe/Stockholm",
  "Europe/Athens",
  "Europe/Istanbul",
  "Europe/Moscow",

  // 🌍 Middle East
  "Asia/Dubai",
  "Asia/Riyadh",
  "Asia/Qatar",
  "Asia/Kuwait",
  "Asia/Tehran",
  "Asia/Jerusalem",

  // 🌏 Asia
  "Asia/Kolkata",
  "Asia/Karachi",
  "Asia/Bangkok",
  "Asia/Singapore",
  "Asia/Kuala_Lumpur",
  "Asia/Hong_Kong",
  "Asia/Shanghai",
  "Asia/Taipei",
  "Asia/Seoul",
  "Asia/Tokyo",
  "Asia/Manila",
  "Asia/Jakarta",

  // 🇦🇺 Oceania
  "Australia/Sydney",
  "Australia/Melbourne",
  "Australia/Brisbane",
  "Australia/Perth",
  "Pacific/Auckland",

  // 🌍 Africa
  "Africa/Cairo",
  "Africa/Johannesburg",
  "Africa/Nairobi",
  "Africa/Lagos",
  "Africa/Casablanca",
];

export default function MyProfile() {
  const clientId = useClientId();
  const { t, lang, changeLanguage } = useLanguage();

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState(null);

  const [formData, setFormData] = useState({
    contact_name: "",
    company_name: "",
    phone: "",
    industry: "",
    role: "",
    country: "",
    company_size: "",
    timezone: "UTC",
    language: lang || "en",
  });

  /* =========================
     Country Handling
  ========================= */

  const countryOptions = useMemo(() => {
    if (!countries || !Array.isArray(countries)) return [];
    return countries
      .map((c) => (typeof c === "string" ? c : c.name))
      .sort((a, b) => a.localeCompare(b));
  }, []);

  /* =========================
     Fetch Profile
  ========================= */

  useEffect(() => {
    const fetchProfile = async () => {
      if (!clientId) return;

      try {
        const res = await authFetch(
          `${import.meta.env.VITE_API_URL}/profile/${clientId}`
        );

        const data = await res.json();

        if (res.ok) {
          setFormData({
            contact_name: data.profile?.contact_name || "",
            company_name: data.profile?.company_name || "",
            phone: data.profile?.phone || "",
            industry: data.profile?.industry || "",
            role: data.profile?.role || "",
            country: data.profile?.country || "",
            company_size: data.profile?.company_size || "",
            timezone: data.timezone || "UTC",
            language: lang || "en",
          });

          const settingsRes = await authFetch(
            `${import.meta.env.VITE_API_URL}/client_settings?client_id=${clientId}`
          );

          if (settingsRes.ok) {
            const settingsData = await settingsRes.json();
            setFormData((prev) => ({
              ...prev,
              language: settingsData?.language || prev.language || "en",
            }));
          }
        } else {
          console.error("❌ Failed loading profile:", data);
        }
      } catch (err) {
        console.error("❌ Error fetching profile:", err);
      }

      setLoading(false);
    };

    fetchProfile();
  }, [clientId, lang]);

  /* =========================
     Handlers
  ========================= */

  const handleChange = (e) => {
    const { name, value } = e.target;

    setFormData((prev) => ({
      ...prev,
      [name]: value,
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!formData.contact_name || formData.contact_name.length < 2) {
      setStatus({
        type: "error",
        message: t("profile_name_min_error"),
      });
      return;
    }

    setSaving(true);
    setStatus(null);

    try {
      const payload = {
        client_id: clientId,
        profile: formData,
        terms: {
          accepted: true,
          accepted_marketing: false,
        },
      };

      const res = await authFetch(
        `${import.meta.env.VITE_API_URL}/complete_onboarding`,
        {
          method: "POST",
          headers: await getAuthHeaders({ "Content-Type": "application/json" }),
          body: JSON.stringify(payload),
        }
      );

      const data = await res.json();

      if (!res.ok) {
        setStatus({
          type: "error",
          message: data.detail || t("profile_save_error"),
        });
      } else {
        const langRes = await authFetch(`${import.meta.env.VITE_API_URL}/client_settings`, {
          method: "POST",
          headers: await getAuthHeaders({ "Content-Type": "application/json" }),
          body: JSON.stringify({
            client_id: clientId,
            language: formData.language || "en",
          }),
        });

        if (!langRes.ok) {
          throw new Error("Error saving language");
        }

        await changeLanguage(formData.language || "en");
        setStatus({
          type: "success",
          message: t("profile_save_success"),
        });
      }
    } catch (err) {
      console.error("❌ Error saving profile:", err);
      setStatus({
        type: "error",
        message: t("network_error_retry"),
      });
    }

    setSaving(false);
  };

  /* =========================
     Loading
  ========================= */

  if (loading) {
    return (
      <div style={loadingStyle}>
        <div style={spinner}></div>
        <p>{t("loading_profile") || "Loading profile..."}</p>
      </div>
    );
  }

  /* =========================
     UI
  ========================= */

  return (
    <form onSubmit={handleSubmit} style={container}>
      <h3 style={sectionTitle}>{t("my_profile")}</h3>

      <div style={card}>
        <Input
          label={t("contact_name")}
          name="contact_name"
          value={formData.contact_name}
          onChange={handleChange}
          required
        />

        <Input
          label={t("company_name")}
          name="company_name"
          value={formData.company_name}
          onChange={handleChange}
        />

        <Input
          label={t("phone")}
          name="phone"
          value={formData.phone}
          onChange={handleChange}
        />

        <Select
          label={t("industry")}
          name="industry"
          value={formData.industry}
          options={industries}
          onChange={handleChange}
        />

        <Select
          label={t("role")}
          name="role"
          value={formData.role}
          options={roles}
          onChange={handleChange}
        />

        <Select
          label={t("country")}
          name="country"
          value={formData.country}
          options={countryOptions}
          onChange={handleChange}
        />

        <Select
          label={t("company_size")}
          name="company_size"
          value={formData.company_size}
          options={companySizes}
          onChange={handleChange}
        />

        <Select
          label={t("timezone")}
          name="timezone"
          value={formData.timezone}
          options={timezones}
          onChange={handleChange}
        />

        <Select
          label={t("language")}
          name="language"
          value={formData.language}
          options={[
            { value: "en", label: t("english") },
            { value: "es", label: t("spanish") },
          ]}
          onChange={handleChange}
        />

        <button type="submit" style={saveButton} disabled={saving}>
          {saving ? t("saving") : t("save")}
        </button>

        {status && (
          <p
            style={{
              marginTop: "1rem",
              fontWeight: "600",
              color: status.type === "error" ? "#e63946" : "#2eb39a",
            }}
          >
            {status.message}
          </p>
        )}
      </div>
    </form>
  );
}

/* =========================
   Reusable Components
========================= */

function Input({ label, ...props }) {
  return (
    <div style={inputGroup}>
      <label style={labelStyle}>{label}</label>
      <input {...props} style={inputStyle} />
    </div>
  );
}

function Select({ label, options, ...props }) {
  const { t } = useLanguage();
  const normalizedOptions = options.map((opt) =>
    typeof opt === "string" ? { value: opt, label: opt } : opt
  );
  return (
    <div style={inputGroup}>
      <label style={labelStyle}>{label}</label>
      <select {...props} style={inputStyle}>
        <option value="">{t("select_placeholder")}</option>
        {normalizedOptions.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
    </div>
  );
}

/* =========================
   Styles
========================= */

const container = {
  display: "flex",
  flexDirection: "column",
  gap: "1.5rem",
};

const sectionTitle = {
  fontSize: "1.2rem",
  fontWeight: "600",
  color: "#274472",
};

const card = {
  backgroundColor: "#ffffff",
  border: "1px solid #ededed",
  borderRadius: "12px",
  padding: "1.5rem",
  boxShadow: "0 4px 16px rgba(39,68,114,0.05)",
  display: "flex",
  flexDirection: "column",
  gap: "1rem",
};

const inputGroup = {
  display: "flex",
  flexDirection: "column",
  gap: "0.4rem",
};

const labelStyle = {
  fontSize: "0.85rem",
  fontWeight: "500",
  color: "#274472",
};

const inputStyle = {
  padding: "8px 10px",
  borderRadius: "6px",
  border: "1px solid #ededed",
  outline: "none",
};

const saveButton = {
  marginTop: "1rem",
  backgroundColor: "#4a90e2",
  color: "white",
  padding: "10px 16px",
  border: "none",
  borderRadius: "6px",
  cursor: "pointer",
  fontWeight: "bold",
};

const loadingStyle = {
  display: "flex",
  flexDirection: "column",
  alignItems: "center",
  gap: "1rem",
  padding: "2rem",
};

const spinner = {
  width: 36,
  height: 36,
  border: "4px solid #ededed",
  borderTop: "4px solid #4a90e2",
  borderRadius: "50%",
  animation: "spin 1s linear infinite",
};
