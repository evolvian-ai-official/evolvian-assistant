export default function Terms() {
  return (
    <div style={styles.container}>
      <div style={styles.card}>
        <h1 style={styles.title}>Terms and Conditions</h1>

        <p style={styles.paragraph}>
          These Terms and Conditions (“Terms”) govern your use of the Evolvian™ platform (“Service”). By accessing or using our Service, you agree to be bound by these Terms. If you do not agree, please do not use the Service.
        </p>

        <h2 style={styles.subtitle}>1. Use of Service</h2>
        <p style={styles.paragraph}>
          You must be at least 18 years old to use the Service. You agree to use the platform only for lawful purposes and in accordance with these Terms.
        </p>

        <h2 style={styles.subtitle}>2. Account Responsibility</h2>
        <p style={styles.paragraph}>
          You are responsible for maintaining the confidentiality of your credentials and for any activity conducted under your account. You agree to notify us immediately of any unauthorized use.
        </p>

        <h2 style={styles.subtitle}>3. Document Privacy</h2>
        <p style={styles.paragraph}>
          Documents uploaded to Evolvian are private and are not shared with third parties or used to train any public AI model. We do not access your data unless explicitly authorized or required by law.
        </p>

        <h2 style={styles.subtitle}>4. Intellectual Property</h2>
        <p style={styles.paragraph}>
          All intellectual property rights in the platform and its components are owned by Evolvian. You retain ownership of any documents or data you upload.
        </p>

        <h2 style={styles.subtitle}>5. Prohibited Activities</h2>
        <p style={styles.paragraph}>
          You agree not to misuse the platform, including but not limited to uploading malicious content, violating privacy rights, reverse engineering the software, or exceeding usage limits based on your plan.
        </p>

        <h2 style={styles.subtitle}>6. Service Availability</h2>
        <p style={styles.paragraph}>
          We aim to provide continuous access but do not guarantee uninterrupted availability. We may suspend access for maintenance or upgrades with prior notice when possible.
        </p>

        <h2 style={styles.subtitle}>7. Limitation of Liability</h2>
        <p style={styles.paragraph}>
          Evolvian is not liable for any indirect, incidental, or consequential damages resulting from the use or inability to use the Service, to the extent permitted by law.
        </p>

        <h2 style={styles.subtitle}>8. Changes to Terms</h2>
        <p style={styles.paragraph}>
          We may update these Terms at any time. Continued use of the Service after such changes implies acceptance. We encourage users to review the Terms periodically.
        </p>

        <h2 style={styles.subtitle}>9. Contact</h2>
        <p style={styles.paragraph}>
          For any questions regarding these Terms, please contact us at <a href="mailto:legal@evolvian.com" style={styles.link}>legal@evolvian.com</a>.
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
  link: {
    color: "#4a90e2",
    textDecoration: "underline",
  },
};
