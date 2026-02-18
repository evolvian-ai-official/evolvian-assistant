import LegalLayout from "../components/ui/LegalLayout";

export default function PrivacyPolicy() {
  return (
    <LegalLayout title="Privacy Policy">
      <p className="legal-paragraph">
        This Privacy Policy explains how Evolvian™ ("we," "us," or "our") collects, uses, and
        protects information when you access and use our Software-as-a-Service platform ("Service"
        or "Platform") available at{" "}
        <a href="https://evolvianai.net" className="legal-link">
          https://evolvianai.net
        </a>
        . By using the Service, you agree to the terms of this Privacy Policy.
      </p>

      <h2 className="legal-subtitle">1. Information We Collect</h2>
      <p className="legal-paragraph">
        We collect information that is necessary to provide and improve our Service, including:
      </p>
      <ul className="legal-list">
        <li>
          <strong>Account Information:</strong> name, email address, password, and authentication
          details.
        </li>
        <li>
          <strong>Client Data:</strong> documents and materials you upload to your account.
        </li>
        <li>
          <strong>Usage Data:</strong> interactions, IP, browser, and plan usage metrics.
        </li>
        <li>
          <strong>Billing Data:</strong> payment details processed securely via Stripe.
        </li>
        <li>
          <strong>Support Data:</strong> communications with our support team.
        </li>
      </ul>

      <h2 className="legal-subtitle">2. How We Use Your Information</h2>
      <ul className="legal-list">
        <li>Authenticate users and manage accounts.</li>
        <li>Process payments and subscriptions.</li>
        <li>Provide personalized AI experiences.</li>
        <li>Monitor plan usage and enforce limits.</li>
        <li>Communicate service updates and support.</li>
        <li>Comply with legal obligations.</li>
      </ul>

      <h2 className="legal-subtitle">3. Data Ownership and Security</h2>
      <p className="legal-paragraph">
        You retain full ownership of your uploaded documents and data ("Client Data"). Evolvian
        does not reuse or train any public AI models with your data.
      </p>
      <p className="legal-paragraph">
        Data is encrypted, access-controlled, and monitored to ensure confidentiality. Only
        authorized staff may access data when necessary for maintenance or compliance.
      </p>

      <h2 className="legal-subtitle">4. Data Processing and Storage</h2>
      <p className="legal-paragraph">
        Data is stored on secure U.S.-based servers, with limited mirrored processing for
        performance. Evolvian never exposes Client Data publicly or cross-trains across tenants.
      </p>

      <h2 className="legal-subtitle">5. Payment Processing</h2>
      <p className="legal-paragraph">
        Payments are handled by{" "}
        <a href="https://stripe.com" target="_blank" rel="noopener noreferrer" className="legal-link">
          Stripe
        </a>
        . Evolvian does not store card numbers. Stripe's privacy policy governs all payment data
        handling.
      </p>

      <h2 className="legal-subtitle">6. Cookies and Analytics</h2>
      <p className="legal-paragraph">
        Evolvian may use cookies to enhance user experience and analytics tools like Google
        Analytics for aggregated, anonymized insights.
      </p>

      <h2 className="legal-subtitle">7. Data Retention and Deletion</h2>
      <p className="legal-paragraph">
        Data is retained as needed for service or legal compliance. You may request deletion
        anytime via{" "}
        <a href="mailto:support@evolvian.com" className="legal-link">
          support@evolvian.com
        </a>
        .
      </p>

      <h2 className="legal-subtitle">8. Data Sharing and Third Parties</h2>
      <p className="legal-paragraph">
        Evolvian does not sell or rent your data. Limited sharing occurs only for infrastructure,
        payment, or legal compliance.
      </p>

      <h2 className="legal-subtitle">9. User Rights (GDPR &amp; CCPA)</h2>
      <p className="legal-paragraph">
        Depending on your location, you may access, correct, or delete your data by contacting{" "}
        <a href="mailto:support@evolvian.com" className="legal-link">
          support@evolvian.com
        </a>
        .
      </p>

      <h2 className="legal-subtitle">10. Children's Privacy</h2>
      <p className="legal-paragraph">
        The Service is not intended for users under 18. We promptly delete any minor-related data
        discovered.
      </p>

      <h2 className="legal-subtitle">11. Changes to This Policy</h2>
      <p className="legal-paragraph">
        Evolvian may update this Privacy Policy from time to time. Updates take effect upon posting
        on{" "}
        <a href="https://evolvianai.net/privacy" className="legal-link">
          evolvianai.net
        </a>
        .
      </p>

      <h2 className="legal-subtitle">12. Contact Us</h2>
      <p className="legal-paragraph">
        For privacy inquiries or compliance matters, contact our Data Protection Officer at{" "}
        <a href="mailto:support@evolvian.com" className="legal-link">
          support@evolvian.com
        </a>
        .
      </p>

      <p className="legal-footer">© {new Date().getFullYear()} Evolvian™. All rights reserved.</p>
    </LegalLayout>
  );
}
