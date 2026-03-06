import React from "react";

export default class AppErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error, info) {
    console.error("Unhandled UI error:", sanitizeErrorLog(error?.message), info?.componentStack);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={containerStyle}>
          <div style={cardStyle}>
            <h1 style={titleStyle}>We hit a loading error</h1>
            <p style={textStyle}>
              Please refresh this page. If it persists, sign in again.
            </p>
            <p style={detailStyle}>Technical details are hidden for security reasons.</p>
            <button
              type="button"
              style={buttonStyle}
              onClick={() => window.location.reload()}
            >
              Reload
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

const containerStyle = {
  minHeight: "100dvh",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  backgroundColor: "#f8fafc",
  padding: "1rem",
};

const cardStyle = {
  width: "min(100%, 460px)",
  border: "1px solid #e5e7eb",
  borderRadius: 16,
  backgroundColor: "#ffffff",
  boxShadow: "0 8px 24px rgba(0,0,0,0.08)",
  padding: "1.25rem",
};

const titleStyle = {
  margin: 0,
  color: "#274472",
  fontSize: "1.25rem",
};

const textStyle = {
  marginTop: "0.65rem",
  marginBottom: "1rem",
  color: "#4b5563",
};

const detailStyle = {
  marginTop: 0,
  marginBottom: "1rem",
  color: "#7a4d00",
  backgroundColor: "#fff7ea",
  border: "1px solid #f5ddb1",
  borderRadius: 8,
  padding: "0.55rem 0.65rem",
  fontSize: "0.86rem",
  overflowWrap: "anywhere",
};

const JWT_PATTERN = /\b[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\b/g;
const BEARER_PATTERN = /\bBearer\s+[A-Za-z0-9._-]+\b/gi;
const META_TOKEN_PATTERN = /\bEA[A-Za-z0-9._-]{16,}\b/g;

function sanitizeErrorLog(message) {
  const raw = String(message || "Unknown UI error");
  return raw
    .replace(BEARER_PATTERN, "Bearer ***redacted***")
    .replace(META_TOKEN_PATTERN, "***redacted***")
    .replace(JWT_PATTERN, "***redacted***");
}

const buttonStyle = {
  border: "none",
  borderRadius: 10,
  backgroundColor: "#4a90e2",
  color: "#ffffff",
  padding: "0.6rem 1rem",
  fontWeight: 600,
  cursor: "pointer",
};
