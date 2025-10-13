export default function PrivacyPolicy() {
  return (
    <div style={styles.container}>
      <div style={styles.card}>
        <h1 style={styles.title}>Privacy Policy</h1>

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
          <li>
            <strong>Account Information:</strong> name, email address, password, and authentication details when you
            register or sign in (via Google or email).
          </li>
          <li>
            <strong>Client Data:</strong> documents, text files, and other materials you upload to your account. These
            are stored securely and used only to power your private AI assistant.
          </li>
          <li>
            <strong>Usage Data:</strong> interactions with the app, plan usage (messages, uploads), browser type, IP
            address, and time zone.
          </li>
          <li>
            <strong>Billing Data:</strong> payment information processed securely through our provider Stripe. We do not
            store credit card numbers.
          </li>
          <li>
            <strong>Support Data:</strong> messages or inquiries you send to our support team.
          </li>
        </ul>

        <h2 style={styles.subtitle}>2. How We Use Your Information</h2>
        <p style={styles.paragraph}>
          Evolvian uses collected data solely to operate and improve the Service. Specifically, we use it to:
        </p>
        <ul style={styles.list}>
          <li>Authenticate users and manage accounts.</li>
          <li>Process payments and subscriptions.</li>
          <li>Provide personalized AI assistant experiences using your uploaded data.</li>
          <li>Monitor usage and enforce plan limits.</li>
          <li>Communicate with you regarding updates, support, or important notices.</li>
          <li>Comply with legal obligations or requests from authorities.</li>
        </ul>

        <h2 style={styles.subtitle}>3. Data Ownership and Security</h2>
        <p style={styles.paragraph}>
          You retain full ownership of all content and documents you upload (“Client Data”). Evolvian does not claim
          ownership or rights to reuse your data for model training or external purposes.
        </p>
        <p style={styles.paragraph}>
          We employ industry-standard security measures including encryption, access control, and network monitoring to
          protect data integrity and confidentiality. Only authorized personnel can access your data when strictly
          necessary for support or legal compliance.
        </p>

        <h2 style={styles.subtitle}>4. Data Processing and Storage</h2>
        <p style={styles.paragraph}>
          Client Data is stored securely on servers within the United States. We may process limited technical data in
          other regions for performance and redundancy purposes, always under the same protection standards.
        </p>
        <p style={styles.paragraph}>
          Evolvian does not train or fine-tune any public AI models with Client Data. Data used to generate embeddings or
          context retrieval remains isolated within your private tenant environment.
        </p>

        <h2 style={styles.subtitle}>5. Payment Processing</h2>
        <p style={styles.paragraph}>
          Payments and billing information are handled exclusively by{" "}
          <a href="https://stripe.com" target="_blank" rel="noopener noreferrer" style={styles.link}>
            Stripe
          </a>
          . Evolvian does not store or access your full payment card details. Stripe’s own privacy policy governs how
          your billing information is processed.
        </p>

        <h2 style={styles.subtitle}>6. Cookies and Analytics</h2>
        <p style={styles.paragraph}>
          Evolvian may use cookies and similar technologies to maintain sessions, remember preferences, and measure
          performance. We also use third-party analytics tools such as Google Analytics to understand aggregate usage
          patterns. These tools collect anonymized data and do not access your private documents or assistant content.
        </p>

        <h2 style={styles.subtitle}>7. Data Retention and Deletion</h2>
        <p style={styles.paragraph}>
          We retain Client Data only for as long as necessary to provide the Service or comply with legal obligations.
          You may request deletion of your account and associated data at any time by contacting{" "}
          <a href="mailto:support@evolvian.com" style={styles.link}>
            support@evolvian.com
          </a>
          . Upon account deletion, all stored Client Data will be permanently removed from active systems and scheduled
          for deletion from backups within a reasonable timeframe.
        </p>

        <h2 style={styles.subtitle}>8. Data Sharing and Third Parties</h2>
        <p style={styles.paragraph}>
          We do not sell or rent your personal or client data. We may share limited data with third-party providers only
          when necessary to:
        </p>
        <ul style={styles.list}>
          <li>Operate infrastructure (cloud storage, hosting, analytics).</li>
          <li>Process payments and subscriptions via Stripe.</li>
          <li>Comply with law enforcement or regulatory requests.</li>
        </ul>

        <h2 style={styles.subtitle}>9. User Rights (GDPR & CCPA)</h2>
        <p style={styles.paragraph}>
          Depending on your location, you may have rights to access, correct, delete, or restrict processing of your
          personal data. To exercise these rights, contact{" "}
          <a href="mailto:support@evolvian.com" style={styles.link}>
            support@evolvian.com
          </a>
          . We will respond within applicable legal timeframes.
        </p>

        <h2 style={styles.subtitle}>10. Children’s Privacy</h2>
        <p style={styles.paragraph}>
          The Service is intended for users aged 18 and older. We do not knowingly collect personal information from
          minors. If we discover such data, we will delete it promptly.
        </p>

        <h2 style={styles.subtitle}>11. Changes to This Policy</h2>
        <p style={styles.paragraph}>
          Evolvian may update this Privacy Policy from time to time. Updates take effect upon posting within the
          Platform or at{" "}
          <a href="https://evolvianai.net/privacy" style={styles.link}>
            https://evolvianai.net/privacy
          </a>
          . Continued use of the Service after updates constitutes acceptance of the revised Policy.
        </p>

        <h2 style={styles.subtitle}>12. Contact Us</h2>
        <p style={styles.paragraph}>
          For privacy-related inquiries, data deletion requests, or compliance matters, please contact our Data
          Protection Officer at{" "}
          <a href="mailto:support@evolvian.com" style={styles.link}>
            support@evolvian.com
          </a>
          .
        </p>

        <p
          style={{
            ...styles.paragraph,
            marginTop: "2rem",
            fontSize: "0.9rem",
            color: "#ccc",
          }}
        >
          © {new Date().getFullYear()} Evolvian™. All rights reserved.
        </p>
      </div>
    </div>
  );
}

const styles = {
  container: {
    minHeight: "100vh",
    backgroundColor: "#0f1c2e",
    display: "flex",
    justifyContent: "center",
    alignItems: "center",
    padding: "2rem",
  },
  card: {
    backgroundColor: "#1b2a41",
    borderRadius: "1rem",
    padding: "2.5rem",
    maxWidth: "750px",
    width: "100%",
    border: "1px solid #274472",
    color: "#ededed",
  },
  title: {
    color: "#a3d9b1",
    fontSize: "2rem",
    marginBottom: "1.5rem",
  },
  subtitle: {
    color: "#f5a623",
    fontSize: "1.2rem",
    marginTop: "1.5rem",
    marginBottom: "0.5rem",
  },
  paragraph: {
    fontSize: "1rem",
    lineHeight: "1.6",
    marginBottom: "1rem",
  },
  list: {
    marginLeft: "1.5rem",
    marginBottom: "1rem",
    lineHeight: "1.6",
  },
  link: {
    color: "#4a90e2",
    textDecoration: "underline",
  },
};
