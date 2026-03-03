import { useEffect, useState, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { useClientId } from "../../hooks/useClientId";
import { useLanguage } from "../../contexts/LanguageContext";
import countries from "../../assets/countries.json";
import { authFetch, getAuthHeaders } from "../../lib/authFetch";
import { supabase } from "../../lib/supabaseClient";
import "../../components/ui/internal-admin-responsive.css";

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
  const navigate = useNavigate();
  const { t, lang, changeLanguage } = useLanguage();

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState(null);
  const [accountEmail, setAccountEmail] = useState("");
  const [canChangePassword, setCanChangePassword] = useState(true);
  const [isPasswordModalOpen, setIsPasswordModalOpen] = useState(false);
  const [passwordSaving, setPasswordSaving] = useState(false);
  const [passwordStatus, setPasswordStatus] = useState(null);
  const [passwordForm, setPasswordForm] = useState({
    newPassword: "",
    confirmPassword: "",
  });

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

  useEffect(() => {
    const fetchAuthProfile = async () => {
      try {
        const { data, error } = await supabase.auth.getUser();
        if (error) throw error;

        const user = data?.user;
        setAccountEmail(user?.email || "");

        const provider = String(user?.app_metadata?.provider || "").toLowerCase();
        const providers = Array.isArray(user?.app_metadata?.providers)
          ? user.app_metadata.providers.map((item) => String(item).toLowerCase())
          : [];

        const hasEmailProvider =
          provider === "email" || providers.includes("email");

        setCanChangePassword(
          hasEmailProvider || (!provider && providers.length === 0)
        );
      } catch (err) {
        console.error("❌ Error fetching auth profile:", err);
      }
    };

    fetchAuthProfile();
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
            timezone: formData.timezone || "UTC",
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

  const openPasswordModal = () => {
    setPasswordForm({ newPassword: "", confirmPassword: "" });
    setPasswordStatus(null);
    setIsPasswordModalOpen(true);
  };

  const closePasswordModal = () => {
    setIsPasswordModalOpen(false);
    setPasswordForm({ newPassword: "", confirmPassword: "" });
    setPasswordStatus(null);
  };

  const handlePasswordChange = (e) => {
    const { name, value } = e.target;
    setPasswordForm((prev) => ({ ...prev, [name]: value }));
  };

  const handlePasswordSubmit = async (e) => {
    e.preventDefault();
    setPasswordStatus(null);

    if (!canChangePassword) {
      setPasswordStatus({
        type: "error",
        message: t("password_not_available_for_google_sso"),
      });
      return;
    }

    if (passwordForm.newPassword !== passwordForm.confirmPassword) {
      setPasswordStatus({
        type: "error",
        message: t("passwords_do_not_match"),
      });
      return;
    }

    const passwordRegex = /^[A-Za-z0-9]{8,}$/;
    if (!passwordRegex.test(passwordForm.newPassword)) {
      setPasswordStatus({
        type: "error",
        message: `${t("invalid_password_format")} ${t("password_hint")}`,
      });
      return;
    }

    try {
      setPasswordSaving(true);
      const { error } = await supabase.auth.updateUser({
        password: passwordForm.newPassword,
      });

      if (error) {
        setPasswordStatus({
          type: "error",
          message: `${t("error_updating_password")}: ${error.message}`,
        });
        return;
      }

      const persistedLang = localStorage.getItem("lang");
      await supabase.auth.signOut();
      localStorage.removeItem("client_id");
      localStorage.removeItem("public_client_id");
      localStorage.removeItem("user_id");
      localStorage.removeItem("alreadyRedirected");
      if (persistedLang) localStorage.setItem("lang", persistedLang);
      navigate("/login?password_updated=1", { replace: true });
      window.location.reload();
    } catch (err) {
      console.error("❌ Error updating password:", err);
      setPasswordStatus({
        type: "error",
        message: t("error_updating_password"),
      });
    } finally {
      setPasswordSaving(false);
    }
  };

  /* =========================
     Loading
  ========================= */

  if (loading) {
    return (
      <div className="ia-loader" style={loadingStyle}>
        <div className="ia-spinner" style={spinner}></div>
        <p>{t("loading_profile") || "Loading profile..."}</p>
      </div>
    );
  }

  /* =========================
     UI
  ========================= */

  return (
    <form onSubmit={handleSubmit} style={container} className="ia-stack-md">
      <h3 style={sectionTitle}>{t("my_profile")}</h3>

      <div style={card}>
        <Input
          label={t("account_email")}
          name="email"
          value={accountEmail}
          disabled
          readOnly
        />

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

        <div style={secondaryActions}>
          <button
            type="button"
            style={secondaryButton}
            onClick={openPasswordModal}
          >
            {t("change_password")}
          </button>
        </div>
      </div>

      {isPasswordModalOpen && (
        <div className="ia-modal-overlay" role="dialog" aria-modal="true" aria-labelledby="change-password-title">
          <div className="ia-modal" style={passwordModalCard}>
            <div className="ia-modal-main">
              <h3 id="change-password-title" className="ia-modal-title" style={passwordModalTitle}>
                {t("change_password_modal_title")}
              </h3>
              <p className="ia-modal-muted" style={{ marginBottom: "1rem" }}>
                {t("change_password_modal_subtitle")}
              </p>

              {canChangePassword ? (
                <form onSubmit={handlePasswordSubmit} style={passwordFormStyle}>
                  <Input
                    label={t("new_password")}
                    name="newPassword"
                    type="password"
                    value={passwordForm.newPassword}
                    onChange={handlePasswordChange}
                    required
                  />

                  <Input
                    label={t("confirm_password")}
                    name="confirmPassword"
                    type="password"
                    value={passwordForm.confirmPassword}
                    onChange={handlePasswordChange}
                    required
                  />

                  <div className="ia-modal-actions" style={passwordModalActions}>
                    <button
                      type="button"
                      className="ia-button ia-button-ghost"
                      onClick={closePasswordModal}
                    >
                      {t("cancel")}
                    </button>
                    <button
                      type="submit"
                      className="ia-button ia-button-primary"
                      disabled={passwordSaving}
                    >
                      {passwordSaving ? t("updating") : t("update_password")}
                    </button>
                  </div>
                </form>
              ) : (
                <div>
                  <p style={passwordSsoMessage}>{t("password_not_available_for_google_sso")}</p>
                  <div className="ia-modal-actions" style={passwordModalActions}>
                    <button
                      type="button"
                      className="ia-button ia-button-ghost"
                      onClick={closePasswordModal}
                    >
                      {t("cancel")}
                    </button>
                  </div>
                </div>
              )}

              {passwordStatus && (
                <p
                  style={{
                    marginTop: "0.6rem",
                    fontWeight: "600",
                    color: passwordStatus.type === "error" ? "#e63946" : "#2eb39a",
                  }}
                >
                  {passwordStatus.message}
                </p>
              )}
            </div>
          </div>
        </div>
      )}
    </form>
  );
}

/* =========================
   Reusable Components
========================= */

function Input({ label, style, ...props }) {
  return (
    <div style={inputGroup}>
      <label style={labelStyle}>{label}</label>
      <input
        {...props}
        style={{
          ...inputStyle,
          ...(props.disabled ? disabledInputStyle : {}),
          ...style,
        }}
      />
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
  gap: "1rem",
};

const sectionTitle = {
  fontSize: "clamp(1rem, 0.95rem + 0.3vw, 1.2rem)",
  fontWeight: "600",
  color: "#274472",
  margin: 0,
};

const card = {
  backgroundColor: "#ffffff",
  border: "1px solid #ededed",
  borderRadius: "12px",
  padding: "clamp(0.9rem, 0.8rem + 0.7vw, 1.5rem)",
  boxShadow: "0 4px 16px rgba(39,68,114,0.05)",
  display: "flex",
  flexDirection: "column",
  gap: "0.8rem",
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
  padding: "10px 12px",
  borderRadius: "10px",
  border: "1px solid #ededed",
  outline: "none",
  fontSize: "0.94rem",
  color: "#274472",
  backgroundColor: "#FFFFFF",
};

const disabledInputStyle = {
  backgroundColor: "#f7f8fb",
  color: "#6b7280",
  cursor: "not-allowed",
};

const saveButton = {
  marginTop: "1rem",
  backgroundColor: "#4a90e2",
  color: "white",
  padding: "10px 16px",
  border: "none",
  borderRadius: "10px",
  cursor: "pointer",
  fontWeight: "bold",
  width: "100%",
  maxWidth: 260,
};

const secondaryActions = {
  marginTop: "0.4rem",
  display: "flex",
};

const secondaryButton = {
  border: "1px solid #d9dce5",
  backgroundColor: "#f8f9fc",
  color: "#274472",
  padding: "10px 16px",
  borderRadius: "10px",
  cursor: "pointer",
  fontWeight: "600",
  width: "100%",
  maxWidth: 260,
};

const passwordModalCard = {
  width: "min(95vw, 520px)",
};

const passwordModalTitle = {
  color: "#274472",
};

const passwordFormStyle = {
  display: "flex",
  flexDirection: "column",
  gap: "0.8rem",
};

const passwordModalActions = {
  marginTop: "0.4rem",
};

const passwordSsoMessage = {
  color: "#4b5563",
  fontSize: "0.93rem",
  lineHeight: 1.45,
};

const loadingStyle = {
  display: "flex",
  flexDirection: "column",
  alignItems: "center",
  gap: "1rem",
  padding: "1rem",
};

const spinner = {
  width: 36,
  height: 36,
};
