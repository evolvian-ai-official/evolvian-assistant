export const PLAN_ORDER = { free: 0, starter: 1, premium: 2, white_label: 3 };

export const normalizeFeature = (value) =>
  String(value || "")
    .trim()
    .toLowerCase()
    .replace(/\s+/g, "_");

export const normalizePlanId = (value) => {
  const normalized = String(value || "free").trim().toLowerCase();
  if (normalized === "enterprise") return "white_label";
  return normalized || "free";
};

export const extractActivePlanFeatures = (rawFeatures) =>
  (Array.isArray(rawFeatures) ? rawFeatures : [])
    .map((feature) => {
      if (typeof feature === "string") return normalizeFeature(feature);
      if (feature && typeof feature === "object" && feature.is_active !== false) {
        return normalizeFeature(feature.feature);
      }
      return null;
    })
    .filter(Boolean);

export const planHasAllFeatures = (planRow, featureKeys) => {
  const required = (Array.isArray(featureKeys) ? featureKeys : [featureKeys])
    .map((featureKey) => normalizeFeature(featureKey))
    .filter(Boolean);

  if (!required.length) return true;

  const activeFeatures = new Set(extractActivePlanFeatures(planRow?.plan_features));
  return required.every((featureKey) => activeFeatures.has(featureKey));
};

export const minPlanForFeatures = (availablePlans, featureKeys) => {
  const required = (Array.isArray(featureKeys) ? featureKeys : [featureKeys])
    .map((featureKey) => normalizeFeature(featureKey))
    .filter(Boolean);

  if (!required.length) return null;

  let winner = null;
  for (const planRow of Array.isArray(availablePlans) ? availablePlans : []) {
    const planId = normalizePlanId(planRow?.id);
    if (!planHasAllFeatures(planRow, required)) continue;
    if (!winner || (PLAN_ORDER[planId] ?? 99) < (PLAN_ORDER[winner] ?? 99)) {
      winner = planId;
    }
  }

  return winner;
};
