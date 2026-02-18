import "./auth-layout.css";

export default function AuthLayout({
  children,
  mediaSrc = null,
  mediaAlt = "Evolvian illustration",
}) {
  const hasMedia = Boolean(mediaSrc);

  return (
    <div className="auth-page">
      <div className={hasMedia ? "auth-frame" : "auth-frame auth-frame--single"}>
        {hasMedia && (
          <div className="auth-frame-media">
            <img src={mediaSrc} alt={mediaAlt} />
          </div>
        )}
        <div className="auth-frame-panel">{children}</div>
      </div>
    </div>
  );
}
