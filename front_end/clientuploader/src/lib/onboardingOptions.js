export const BUSINESS_SECTOR_OPTIONS = [
  { value: "Healthcare", labelEn: "Healthcare / Clinic", labelEs: "Salud / Clinica" },
  { value: "Dentistry", labelEn: "Dentistry", labelEs: "Odontologia" },
  { value: "Psychology / Therapy", labelEn: "Psychology / Therapy", labelEs: "Psicologia / Terapia" },
  { value: "Medical Practice", labelEn: "Medical Practice", labelEs: "Consulta medica" },
  { value: "Beauty / Aesthetics", labelEn: "Beauty / Aesthetics", labelEs: "Esteticas / Belleza" },
  { value: "Restaurant / Cafe", labelEn: "Restaurant / Cafe", labelEs: "Restaurantes / Cafe" },
  { value: "Retail", labelEn: "Retail", labelEs: "Retail" },
  { value: "Education", labelEn: "Education", labelEs: "Educacion" },
  { value: "Finance", labelEn: "Finance", labelEs: "Finanzas" },
  { value: "Manufacturing", labelEn: "Manufacturing", labelEs: "Manufactura" },
  { value: "Consulting", labelEn: "Consulting", labelEs: "Consultoria" },
  { value: "Professional Services", labelEn: "Professional Services", labelEs: "Servicios profesionales" },
  { value: "Real Estate", labelEn: "Real Estate", labelEs: "Bienes raices" },
  { value: "Fitness / Wellness", labelEn: "Fitness / Wellness", labelEs: "Fitness / Bienestar" },
  { value: "Software / SaaS", labelEn: "Software / SaaS", labelEs: "Software / SaaS" },
  { value: "Other", labelEn: "Other", labelEs: "Otro" },
];

export const DISCOVERY_SOURCE_OPTIONS = [
  { value: "Instagram", labelEn: "Instagram", labelEs: "Instagram" },
  { value: "LinkedIn", labelEn: "LinkedIn", labelEs: "LinkedIn" },
  { value: "Google", labelEn: "Google", labelEs: "Google" },
  { value: "Facebook", labelEn: "Facebook", labelEs: "Facebook" },
  { value: "TikTok", labelEn: "TikTok", labelEs: "TikTok" },
  { value: "Email", labelEn: "Email", labelEs: "Email" },
  { value: "Referral / Word of Mouth", labelEn: "Referral / Word of Mouth", labelEs: "Referido / Boca a boca" },
  { value: "WhatsApp", labelEn: "WhatsApp", labelEs: "WhatsApp" },
  { value: "YouTube", labelEn: "YouTube", labelEs: "YouTube" },
  { value: "Event / Conference", labelEn: "Event / Conference", labelEs: "Evento / Conferencia" },
  { value: "Other", labelEn: "Other", labelEs: "Otro" },
];

export const ROLE_OPTIONS = [
  "Founder / CEO",
  "CMO / Marketing Manager",
  "Customer Support",
  "Operations Manager",
  "Sales Executive",
  "IT Manager",
  "Product Manager",
  "Developer / Engineer",
  "HR / People",
  "Other",
];

export const CHANNEL_OPTIONS = ["Chat Widget", "WhatsApp", "Email", "Others"];

export const COMPANY_SIZE_OPTIONS = [
  "1-10 employees",
  "11-50 employees",
  "51-200 employees",
  "201-500 employees",
  "501-1000 employees",
  "More than 1000 employees",
];

export const WELCOME_INDUSTRY_TEMPLATES = [
  {
    id: "health",
    icon: "🏥",
    labelEs: "Salud / Clinica",
    labelEn: "Health / Clinic",
    descEs: "Citas, preguntas de pacientes, recordatorios",
    descEn: "Appointments, patient questions, reminders",
    industry: "Healthcare",
    channels: ["WhatsApp", "Chat Widget"],
  },
  {
    id: "beauty",
    icon: "💆",
    labelEs: "Esteticas / Belleza",
    labelEn: "Beauty / Aesthetics",
    descEs: "Reservas, servicios, disponibilidad",
    descEn: "Bookings, services, availability",
    industry: "Beauty / Aesthetics",
    channels: ["WhatsApp", "Chat Widget"],
  },
  {
    id: "restaurant",
    icon: "🍽️",
    labelEs: "Restaurantes / Cafe",
    labelEn: "Restaurant / Cafe",
    descEs: "Reservas, menu, horarios y pedidos",
    descEn: "Reservations, menu, hours, and orders",
    industry: "Restaurant / Cafe",
    channels: ["WhatsApp", "Chat Widget"],
  },
  {
    id: "professional",
    icon: "⚖️",
    labelEs: "Servicios Profesionales",
    labelEn: "Professional Services",
    descEs: "Consultas, calificacion de leads, FAQ",
    descEn: "Consultations, lead qualification, FAQ",
    industry: "Professional Services",
    channels: ["WhatsApp", "Chat Widget"],
  },
  {
    id: "other",
    icon: "🏢",
    labelEs: "Otro negocio",
    labelEn: "Other business",
    descEs: "Configura segun tus necesidades",
    descEn: "Configure according to your needs",
    industry: "Other",
    channels: ["Chat Widget"],
  },
];

export function getLocalizedOptions(options, language = "en") {
  const isSpanish = language === "es";
  return options.map((option) => ({
    value: option.value,
    label: isSpanish ? option.labelEs : option.labelEn,
  }));
}

export function findTemplateByIndustry(industry) {
  return WELCOME_INDUSTRY_TEMPLATES.find((template) => template.industry === industry) || null;
}
