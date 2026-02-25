export const PHONE_COUNTRY_OPTIONS = [
  { code: "+1", label: "US / CA (+1)", countries: ["united states", "canada"] },
  { code: "+52", label: "Mexico (+52)", countries: ["mexico"] },
  { code: "+34", label: "Spain (+34)", countries: ["spain"] },
  { code: "+54", label: "Argentina (+54)", countries: ["argentina"] },
  { code: "+55", label: "Brazil (+55)", countries: ["brazil"] },
  { code: "+56", label: "Chile (+56)", countries: ["chile"] },
  { code: "+57", label: "Colombia (+57)", countries: ["colombia"] },
  { code: "+58", label: "Venezuela (+58)", countries: ["venezuela"] },
  { code: "+51", label: "Peru (+51)", countries: ["peru"] },
  { code: "+593", label: "Ecuador (+593)", countries: ["ecuador"] },
  { code: "+507", label: "Panama (+507)", countries: ["panama"] },
  { code: "+506", label: "Costa Rica (+506)", countries: ["costa rica"] },
  { code: "+503", label: "El Salvador (+503)", countries: ["el salvador"] },
  { code: "+502", label: "Guatemala (+502)", countries: ["guatemala"] },
  { code: "+504", label: "Honduras (+504)", countries: ["honduras"] },
  { code: "+505", label: "Nicaragua (+505)", countries: ["nicaragua"] },
  { code: "+44", label: "UK (+44)", countries: ["united kingdom"] },
  { code: "+33", label: "France (+33)", countries: ["france"] },
  { code: "+49", label: "Germany (+49)", countries: ["germany"] },
  { code: "+39", label: "Italy (+39)", countries: ["italy"] },
  { code: "+351", label: "Portugal (+351)", countries: ["portugal"] },
  { code: "+31", label: "Netherlands (+31)", countries: ["netherlands"] },
  { code: "+32", label: "Belgium (+32)", countries: ["belgium"] },
  { code: "+41", label: "Switzerland (+41)", countries: ["switzerland"] },
  { code: "+353", label: "Ireland (+353)", countries: ["ireland"] },
  { code: "+61", label: "Australia (+61)", countries: ["australia"] },
  { code: "+64", label: "New Zealand (+64)", countries: ["new zealand"] },
  { code: "+91", label: "India (+91)", countries: ["india"] },
  { code: "+81", label: "Japan (+81)", countries: ["japan"] },
  { code: "+82", label: "South Korea (+82)", countries: ["south korea"] },
  { code: "+86", label: "China (+86)", countries: ["china"] },
  { code: "+65", label: "Singapore (+65)", countries: ["singapore"] },
  { code: "+971", label: "UAE (+971)", countries: ["united arab emirates"] },
  { code: "+966", label: "Saudi Arabia (+966)", countries: ["saudi arabia"] },
  { code: "+27", label: "South Africa (+27)", countries: ["south africa"] },
];

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;
const E164_PHONE_RE = /^\+[1-9]\d{7,14}$/;

const COUNTRY_TZ_PREFIX_MAP = [
  ["America/Mexico_City", "+52"],
  ["America/New_York", "+1"],
  ["America/Chicago", "+1"],
  ["America/Denver", "+1"],
  ["America/Los_Angeles", "+1"],
  ["Europe/Madrid", "+34"],
  ["Europe/London", "+44"],
  ["Europe/Paris", "+33"],
  ["Europe/Berlin", "+49"],
  ["America/Bogota", "+57"],
  ["America/Lima", "+51"],
  ["America/Santiago", "+56"],
  ["America/Argentina", "+54"],
  ["America/Sao_Paulo", "+55"],
];

export const DEFAULT_PHONE_COUNTRY_CODE = "+1";

export function isValidAppointmentEmail(email) {
  const value = String(email || "").trim();
  return !value || EMAIL_RE.test(value);
}

export function normalizeAppointmentEmail(email) {
  const value = String(email || "").trim().toLowerCase();
  return value || "";
}

export function isValidAppointmentPhone(phone) {
  const value = String(phone || "").trim();
  return !value || E164_PHONE_RE.test(value);
}

export function normalizeAppointmentName(name) {
  return String(name || "").trim().replace(/\s+/g, " ");
}

export function sanitizePhoneLocalInput(value) {
  return String(value || "").replace(/\D/g, "");
}

export function composeE164Phone(countryCode, localDigits) {
  const code = String(countryCode || "").trim();
  const local = sanitizePhoneLocalInput(localDigits);
  if (!local) return "";
  const normalizedCode = code.startsWith("+") ? code : `+${code.replace(/\D/g, "")}`;
  return `${normalizedCode}${local}`;
}

export function splitE164Phone(phone) {
  const raw = String(phone || "").trim();
  if (!raw.startsWith("+")) {
    return { countryCode: DEFAULT_PHONE_COUNTRY_CODE, localNumber: sanitizePhoneLocalInput(raw) };
  }
  const codes = [...PHONE_COUNTRY_OPTIONS]
    .map((c) => c.code)
    .sort((a, b) => b.length - a.length);
  const matched = codes.find((code) => raw.startsWith(code));
  if (!matched) {
    return { countryCode: DEFAULT_PHONE_COUNTRY_CODE, localNumber: sanitizePhoneLocalInput(raw) };
  }
  return {
    countryCode: matched,
    localNumber: sanitizePhoneLocalInput(raw.slice(matched.length)),
  };
}

export function inferPhoneCountryCode({ country = "", timezone = "" } = {}) {
  const normalizedCountry = String(country || "").trim().toLowerCase();
  if (normalizedCountry) {
    const found = PHONE_COUNTRY_OPTIONS.find((option) =>
      (option.countries || []).some((name) => name === normalizedCountry)
    );
    if (found) return found.code;
  }

  const tz = String(timezone || "").trim();
  if (tz) {
    const found = COUNTRY_TZ_PREFIX_MAP.find(([prefix]) => tz.startsWith(prefix));
    if (found) return found[1];
  }

  return DEFAULT_PHONE_COUNTRY_CODE;
}

export function buildContactMatchKey({ user_email, user_phone, user_name }) {
  const email = normalizeAppointmentEmail(user_email);
  const phone = String(user_phone || "").trim();
  const name = normalizeAppointmentName(user_name).toLowerCase();
  if (email) return `email:${email}`;
  if (phone) return `phone:${phone}`;
  if (name) return `name:${name}`;
  return "";
}
