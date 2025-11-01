import { useEffect, useState } from "react";

export default function Terms() {
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
        {/* 🔹 Logo circular degradado */}
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

        <h1 style={styles.title}>Terms and Conditions</h1>

        <div style={styles.scrollArea}>
          <p style={styles.paragraph}>
            These Terms and Conditions (“Terms”) govern your access to and use of the Evolvian™ Software-as-a-Service platform (“Service” or “Platform”). 
            By creating an account, subscribing to a plan, or using the Service, you agree to be legally bound by these Terms. 
            If you do not agree, please discontinue use immediately.
          </p>

          <h2 style={styles.subtitle}>1. Eligibility and Use of Service</h2>
          <p style={styles.paragraph}>
            You must be at least 18 years old to use the Service. You represent and warrant that you have the authority to enter into these Terms 
            on behalf of yourself or your organization. You agree to use the Platform only for lawful purposes and in compliance with all applicable laws and regulations.
          </p>

          <h2 style={styles.subtitle}>2. Account Registration and Security</h2>
          <p style={styles.paragraph}>
            You are responsible for maintaining the confidentiality of your login credentials and for all activity that occurs under your account. 
            You must immediately notify Evolvian of any unauthorized use or security breach. Evolvian is not liable for any losses caused by unauthorized access to your account.
          </p>

          <h2 style={styles.subtitle}>3. Data Ownership and Confidentiality</h2>
          <p style={styles.paragraph}>
            You retain full ownership and rights to all documents, data, and materials you upload (“Client Data”). 
            Evolvian does not claim ownership over your content. Client Data is stored securely and used solely to provide the Service. 
            Evolvian does not use or share Client Data to train any public AI models. 
            Access to Client Data is strictly limited to authorized personnel only when necessary for support, maintenance, or legal compliance.
          </p>

          <h2 style={styles.subtitle}>4. Data Protection and Compliance</h2>
          <p style={styles.paragraph}>
            Evolvian applies industry-standard security measures and aligns with major international data protection frameworks, 
            including the General Data Protection Regulation (GDPR) and the California Consumer Privacy Act (CCPA), to the extent applicable. 
            You are responsible for ensuring your own compliance with privacy regulations that apply to your users or customers.
          </p>

          <h2 style={styles.subtitle}>5. Intellectual Property</h2>
          <p style={styles.paragraph}>
            Evolvian and its licensors retain all rights, title, and interest in the Service, including software, algorithms, interfaces, designs, trademarks, and documentation. 
            No rights are granted to you except as expressly stated herein. 
            You may not copy, modify, reverse engineer, decompile, or distribute any part of the Service.
          </p>

          <h2 style={styles.subtitle}>6. Acceptable Use and Restrictions</h2>
          <p style={styles.paragraph}>
            You agree not to misuse the Service. Prohibited activities include but are not limited to: uploading harmful or illegal content, 
            attempting to disrupt or hack the platform, violating intellectual property rights, exceeding plan limits, 
            using automated systems or bots to access the Service, or using the Service to generate or disseminate harmful, misleading, or discriminatory content. 
            Excessive or automated API usage beyond your plan limits may result in throttling, suspension, or additional fees. 
            Evolvian reserves the right to suspend or terminate any account violating these provisions.
          </p>

          <h2 style={styles.subtitle}>7. Service Plans, Billing, and Termination</h2>
          <p style={styles.paragraph}>
            Subscription fees are charged according to your selected plan. Evolvian may modify pricing or plan limits with reasonable notice. 
            You may cancel your subscription at any time; however, fees paid are non-refundable except as required by law. 
            Evolvian reserves the right to suspend or terminate access for non-payment or breach of these Terms.
          </p>

          <h2 style={styles.subtitle}>8. Service Availability, Backups, and Updates</h2>
          <p style={styles.paragraph}>
            While Evolvian strives for continuous Service availability, temporary interruptions may occur for maintenance, upgrades, or unforeseen circumstances. 
            Evolvian performs regular system backups but is not responsible for data loss caused by client-side actions, third-party integrations, or force majeure events. 
            The Service may be updated, enhanced, or modified at Evolvian’s discretion without prior notice.
          </p>

          <h2 style={styles.subtitle}>9. AI-Generated Content Disclaimer</h2>
          <p style={styles.paragraph}>
            Evolvian provides AI-powered functionalities that may generate automated outputs (“AI Outputs”). 
            You acknowledge that such outputs are generated algorithmically and may not always be accurate, complete, or appropriate. 
            Evolvian makes no representations or warranties regarding the accuracy, legality, or fitness for any particular purpose of AI Outputs. 
            You are solely responsible for reviewing, validating, and using any AI-generated content. 
            Evolvian is not liable for any damages or consequences arising from reliance on AI Outputs.
          </p>

          <h2 style={styles.subtitle}>10. White Label and Branding</h2>
          <p style={styles.paragraph}>
            White-label clients may use their own branding when authorized under their subscription plan. 
            However, Evolvian retains full ownership of the underlying software, infrastructure, and technology. 
            Any use of the Evolvian brand, trademarks, or related assets must comply with Evolvian’s written brand guidelines or prior approval.
          </p>

          <h2 style={styles.subtitle}>11. Disclaimer of Warranties</h2>
          <p style={styles.paragraph}>
            The Service is provided “as is” and “as available.” Evolvian makes no warranties, express or implied, 
            regarding accuracy, reliability, uptime, merchantability, or fitness for any particular purpose. 
            You assume all responsibility for your use of the Service and any outputs generated by AI systems.
          </p>

          <h2 style={styles.subtitle}>12. Limitation of Liability</h2>
          <p style={styles.paragraph}>
            To the maximum extent permitted by law, Evolvian and its affiliates shall not be liable for any indirect, incidental, special, consequential, or punitive damages, 
            including lost profits, business interruption, or data loss, arising out of or related to your use of the Service, 
            even if advised of the possibility of such damages. 
            In all cases, Evolvian’s total aggregate liability shall not exceed the amount you paid in the 12 months preceding the event giving rise to the claim.
          </p>

          <h2 style={styles.subtitle}>13. Indemnification</h2>
          <p style={styles.paragraph}>
            You agree to defend, indemnify, and hold harmless Evolvian, its affiliates, officers, and employees from any claims, damages, losses, or expenses 
            arising from your use of the Service, violation of these Terms, or infringement of any third-party rights.
          </p>

          <h2 style={styles.subtitle}>14. Export Compliance and Legal Use</h2>
          <p style={styles.paragraph}>
            You represent that you are not located in, under the control of, or a resident of any country or entity subject to international sanctions or export restrictions. 
            You agree not to use the Service in violation of any applicable export or trade control laws.
          </p>

          <h2 style={styles.subtitle}>15. Modifications to Terms</h2>
          <p style={styles.paragraph}>
            Evolvian may revise these Terms at any time. Updates take effect upon posting on our website or within the application. 
            Continued use of the Service after modifications constitutes acceptance of the updated Terms.
          </p>

          <h2 style={styles.subtitle}>16. Governing Law and International Jurisdiction</h2>
          <p style={styles.paragraph}>
            These Terms are governed by and construed in accordance with the laws of the State of Montana, United States, 
            without regard to conflict-of-law principles. 
            International users agree that any disputes shall be resolved exclusively in the courts of Montana, U.S.A.
          </p>

          <h2 style={styles.subtitle}>17. Contact Information</h2>
          <p style={styles.paragraph}>
            For legal inquiries, please contact us at{" "}
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
