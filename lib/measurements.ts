import type { HeightUnit, WeightUnit } from "@/context/UserContext";

export function convertHeightToUnit(heightCm: number, unit: HeightUnit) {
  if (unit === "ft") {
    return heightCm / 30.48;
  }
  return heightCm;
}

export function convertWeightToUnit(weightKg: number, unit: WeightUnit) {
  if (unit === "lb") {
    return weightKg * 2.20462;
  }
  return weightKg;
}

export function convertHeightToCentimeters(value: number, unit: HeightUnit) {
  if (unit === "ft") {
    return value * 30.48;
  }
  return value;
}

export function convertWeightToKilograms(value: number, unit: WeightUnit) {
  if (unit === "lb") {
    return value * 0.453592;
  }
  return value;
}

export function formatHeight(heightCm: number | null, unit: HeightUnit) {
  if (heightCm == null) {
    return "Not set";
  }
  const converted = convertHeightToUnit(heightCm, unit);
  return unit === "cm"
    ? `${round(converted, 1)} cm`
    : `${round(converted, 2)} ft`;
}

export function formatWeight(weightKg: number | null, unit: WeightUnit) {
  if (weightKg == null) {
    return "Not set";
  }
  const converted = convertWeightToUnit(weightKg, unit);
  return unit === "kg"
    ? `${round(converted, 1)} kg`
    : `${round(converted, 1)} lb`;
}

export function formatA1c(value: number | null) {
  if (value == null) {
    return "Not set";
  }
  return `${round(value, 1)}%`;
}

function round(value: number, digits: number) {
  const factor = Math.pow(10, digits);
  return Math.round(value * factor) / factor;
}
