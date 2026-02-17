import { useEffect, useState } from "react";

export default function PrivacyPolicy() {
  const [animateLogo, setAnimateLogo] = useState(false);

  useEffect(() => {
    setTimeout(() => setAnimateLogo(true), 100);

    if (!document.getElementById("pulseGlow")) {
      const style = document.createElement("style");
      style.id = "pulseGlow";
      style.textContent = `
        @keyframes pulseGlow {
          0%, 100% { box-shadow: 0 0 15px rgba(74,144,226,0.4); }
          50% { box-shadow: 0 0 25px rgba(163,217,177,0.7); }
        }
      `;
      document.head.appendChild(style);
    }
  }, []);

  return (
    <div style={styles.container}>
      <div style={styles.card}>
        {/* 🔹 Logo circular degradado con animación */}
        <div style={styles.logoWrapper}>
          <div
            style={{
              ...styles.logoCircle,
              transform: animateLogo ? "rotate(360deg)" : "rotate(0deg)",
              transition: "transform 1s ease-in-out",
              animation: "pulseGlow 4s ease-in-out infinite",
            }}
          >
            <img src="/logo-evolvian.svg" alt="Evolvian Logo" style={styles.logoFull} />
          </div>
        </div>

        <h1 style={styles.title}>Privacy Policy</h1>

        <div style={styles.scrollArea}>
          <p style={styles.paragraph}>
            This Privacy Policy explains how Evolvian™ (“we,” “us,” or “our”) collects, uses, and protects information
            when you access and use our Software-as-a-Service platform (“Service” or “Platform”) available at{" "}
            <a href="https://evolvianai.net" style={styles.link}>
              https://evolvianai.net
            </a>. By using the Service, you agree to the terms of this Privacy Policy.
          </p>

          <h2 style={styles.subtitle}>1. Information We Collect</h2>
          <p style={styles.paragraph}>
            We collect information that is necessary to provide and improve our Service, including:
          </p>
          <ul style={styles.list}>
            <li><strong>Account Information:</strong> name, email address, password, and authentication details.</li>
            <li><strong>Client Data:</strong> documents and materials you upload to your account.</li>
            <li><strong>Usage Data:</strong> interactions, IP, browser, and plan usage metrics.</li>
            <li><strong>Billing Data:</strong> payment details processed securely via Stripe.</li>
            <li><strong>Support Data:</strong> communications with our support team.</li>
          </ul>

          <h2 style={styles.subtitle}>2. How We Use Your Information</h2>
          <ul style={styles.list}>
            <li>Authenticate users and manage accounts.</li>
            <li>Process payments and subscriptions.</li>
            <li>Provide personalized AI experiences.</li>
            <li>Monitor plan usage and enforce limits.</li>
            <li>Communicate service updates and support.</li>
            <li>Comply with legal obligations.</li>
          </ul>

          <h2 style={styles.subtitle}>3. Data Ownership and Security</h2>
          <p style={styles.paragraph}>
            You retain full ownership of your uploaded documents and data (“Client Data”). Evolvian does not reuse or
            train any public AI models with your data.
          </p>
          <p style={styles.paragraph}>
            Data is encrypted, access-controlled, and monitored to ensure confidentiality. Only authorized staff may
            access data when necessary for maintenance or compliance.
          </p>

          <h2 style={styles.subtitle}>4. Data Processing and Storage</h2>
          <p style={styles.paragraph}>
            Data is stored on secure U.S.-based servers, with limited mirrored processing for performance. Evolvian never
            exposes Client Data publicly or cross-trains across tenants.
          </p>

          <h2 style={styles.subtitle}>5. Payment Processing</h2>
          <p style={styles.paragraph}>
            Payments are handled by{" "}
            <a href="https://stripe.com" target="_blank" rel="noopener noreferrer" style={styles.link}>
              Stripe
            </a>
            . Evolvian does not store card numbers. Stripe’s privacy policy governs all payment data handling.
          </p>

          <h2 style={styles.subtitle}>6. Cookies and Analytics</h2>
          <p style={styles.paragraph}>
            Evolvian may use cookies to enhance user experience and analytics tools like Google Analytics for aggregated,
            anonymized insights.
          </p>

          <h2 style={styles.subtitle}>7. Data Retention and Deletion</h2>
          <p style={styles.paragraph}>
            Data is retained as needed for service or legal compliance. You may request deletion anytime via{" "}
            <a href="mailto:support@evolvian.com" style={styles.link}>
              support@evolvian.com
            </a>.
          </p>

          <h2 style={styles.subtitle}>8. Data Sharing and Third Parties</h2>
          <p style={styles.paragraph}>
            Evolvian does not sell or rent your data. Limited sharing occurs only for infrastructure, payment, or legal
            compliance.
          </p>

          <h2 style={styles.subtitle}>9. User Rights (GDPR & CCPA)</h2>
          <p style={styles.paragraph}>
            Depending on your location, you may access, correct, or delete your data by contacting{" "}
            <a href="mailto:support@evolvian.com" style={styles.link}>
              support@evolvian.com
            </a>.
          </p>

          <h2 style={styles.subtitle}>10. Children’s Privacy</h2>
          <p style={styles.paragraph}>
            The Service is not intended for users under 18. We promptly delete any minor-related data discovered.
          </p>

          <h2 style={styles.subtitle}>11. Changes to This Policy</h2>
          <p style={styles.paragraph}>
            Evolvian may update this Privacy Policy from time to time. Updates take effect upon posting on{" "}
            <a href="https://evolvianai.net/privacy" style={styles.link}>
              evolvianai.net
            </a>.
          </p>

          <h2 style={styles.subtitle}>12. Contact Us</h2>
          <p style={styles.paragraph}>
            For privacy inquiries or compliance matters, contact our Data Protection Officer at{" "}
            <a href="mailto:support@evolvian.com" style={styles.link}>
              support@evolvian.com
            </a>.
          </p>

          <p style={styles.footerText}>
            © {new Date().getFullYear()} Evolvian™. All rights reserved.
          </p>
        </div>
      </div>
    </div>
  );
}

/* 🎨 Estilos Evolvian */
const styles = {
  container: {
    minHeight: "100vh",
    backgroundColor: "#f9fafb",
    display: "flex",
    justifyContent: "center",
    alignItems: "center",
    padding: "2rem",
    fontFamily: "Inter, system-ui, sans-serif",
  },
  card: {
    backgroundColor: "#ffffff",
    borderRadius: "20px",
    padding: "2.5rem",
    maxWidth: "750px",
    width: "100%",
    color: "#1b2a41",
    boxShadow: "0 8px 40px rgba(39,68,114,0.1)",
    border: "1px solid #e5e7eb",
  },
  scrollArea: {
    maxHeight: "75vh",
    overflowY: "auto",
    paddingRight: "0.5rem",
  },
  logoWrapper: {
    display: "flex",
    justifyContent: "center",
    marginBottom: "1.5rem",
  },
  logoCircle: {
    width: "80px",
    height: "80px",
    borderRadius: "50%",
    background: "radial-gradient(circle, #a3d9b1 0%, #4a90e2 100%)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    overflow: "hidden",
  },
  logoFull: {
    width: "100%",
    height: "100%",
    objectFit: "cover",
  },
  title: {
    color: "#274472",
    fontSize: "1.8rem",
    fontWeight: "700",
    marginBottom: "1.5rem",
    textAlign: "center",
  },
  subtitle: {
    color: "#f5a623",
    fontSize: "1.2rem",
    marginTop: "1.5rem",
    marginBottom: "0.5rem",
  },
  paragraph: {
    fontSize: "1rem",
    lineHeight: "1.7",
    marginBottom: "1rem",
    color: "#1f2937",
  },
  list: {
    marginLeft: "1.5rem",
    marginBottom: "1rem",
    lineHeight: "1.7",
    color: "#1f2937",
  },
  link: {
    color: "#4a90e2",
    textDecoration: "underline",
    fontWeight: "500",
  },
  footerText: {
    textAlign: "center",
    marginTop: "2rem",
    fontSize: "0.9rem",
    color: "#6b7280",
  },
};
