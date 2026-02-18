import "./legal-layout.css";

export default function LegalLayout({ title, children }) {
  return (
    <div className="legal-page">
      <article className="legal-card">
        <div className="legal-logo-wrap">
          <img src="/logo-evolvian.svg" alt="Evolvian Logo" className="legal-logo" />
        </div>

        <h1 className="legal-title">{title}</h1>

        <div className="legal-scroll">{children}</div>
      </article>
    </div>
  );
}
