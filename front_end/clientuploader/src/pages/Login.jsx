import { useEffect, useState } from "react";
import { useNavigate, Link, useLocation } from "react-router-dom";
import { FaGoogle, FaEye, FaEyeSlash } from "react-icons/fa";
import AuthLayout from "../components/ui/AuthLayout";
import { supabase } from "../lib/supabaseClient";
import { useLanguage } from "../contexts/LanguageContext";

export default function Login() {
  const { t } = useLanguage();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");
  const [successMsg, setSuccessMsg] = useState("");
  const [checkingSession, setCheckingSession] = useState(true);

  useEffect(() => {
    const checkSession = async () => {
      const { data } = await supabase.auth.getSession();
      if (data?.session) navigate("/dashboard");
      setCheckingSession(false);
    };
    checkSession();
  }, [navigate]);

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    if (params.get("password_updated") === "1") {
      setSuccessMsg(t("password_changed_login_again"));
    } else {
      setSuccessMsg("");
    }
  }, [location.search, t]);

  const initializeUser = async (user, accessToken) => {
    try {
      const res = await fetch(`${import.meta.env.VITE_API_URL}/initialize_user`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${accessToken}`,
        },
        body: JSON.stringify({
          auth_user_id: user.id,
          email: user.email,
        }),
      });
      if (!res.ok) throw new Error(t("login_initialize_failed"));

      const initData = await res.json();
      localStorage.setItem("client_id", initData.client_id);
      localStorage.setItem("public_client_id", initData.public_client_id);
      localStorage.setItem("user_id", user.id);
      navigate("/dashboard");
    } catch (err) {
      console.error(err);
      setErrorMsg(t("login_initialize_error"));
    }
  };

  const handleEmailLogin = async (e) => {
    e.preventDefault();
    setErrorMsg("");

    const { data, error } = await supabase.auth.signInWithPassword({ email, password });
    if (error) {
      setErrorMsg(t("wrong_credentials"));
      return;
    }
    if (!data.session) {
      setErrorMsg(t("email_not_confirmed"));
      return;
    }

    await initializeUser(data.session.user, data.session.access_token);
  };

  const handleGoogleLogin = async () => {
    const redirectTo = `${window.location.origin}/dashboard`;
    const { error } = await supabase.auth.signInWithOAuth({
      provider: "google",
      options: { redirectTo },
    });
    if (error) setErrorMsg(t("login_google_connect_error"));
  };

  if (checkingSession) {
    return (
      <AuthLayout>
        <p className="auth-loading">{t("loading_session")}</p>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout mediaSrc="/evost1.gif" mediaAlt="Evolvian illustration">
      <div className="auth-card">
        <div className="auth-logo-wrap">
          <img src="/logo-evolvian.svg" alt="Evolvian Logo" className="auth-logo" />
        </div>

        <h1 className="auth-title">Evolvian</h1>

        <form onSubmit={handleEmailLogin} className="auth-form">
          <div className="auth-field">
            <input
              type="email"
              placeholder={t("email")}
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="email"
              className="auth-input"
            />
          </div>

          <div className="auth-field">
            <input
              type={showPassword ? "text" : "password"}
              placeholder={t("password")}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoComplete="current-password"
              className="auth-input"
            />
            <button
              type="button"
              className="auth-icon-btn"
              aria-label={showPassword ? "Hide password" : "Show password"}
              onClick={() => setShowPassword((prev) => !prev)}
            >
              {showPassword ? <FaEyeSlash /> : <FaEye />}
            </button>
          </div>

          {successMsg && <p className="auth-status-success">{successMsg}</p>}
          {errorMsg && <p className="auth-status-error">{errorMsg}</p>}

          <button type="submit" className="auth-btn auth-btn-primary">
            {t("login")}
          </button>

          <div className="auth-row">
            <label style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
              <input type="checkbox" />
              {t("remember_me")}
            </label>
            <Link to="/forgot-password">{t("forgot_password")}</Link>
          </div>
        </form>

        <p className="auth-note">
          {t("no_account")}{" "}
          <Link to="/register" className="auth-note-inline">
            {t("register_here")}
          </Link>
        </p>

        <div className="auth-divider">
          <div className="auth-divider-line" />
          <span style={{ color: "#6b7280", fontSize: "0.9rem" }}>{t("or")}</span>
          <div className="auth-divider-line" />
        </div>

        <button
          type="button"
          onClick={handleGoogleLogin}
          className="auth-btn auth-btn-outline"
          style={{
            width: "100%",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: "0.5rem",
          }}
        >
          <FaGoogle />
          {t("login_with_google")}
        </button>
      </div>
    </AuthLayout>
  );
}
