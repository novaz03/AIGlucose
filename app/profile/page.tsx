'use client';

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useUser } from "@/context/UserContext";
import type { HeightUnit, WeightUnit } from "@/context/UserContext";
import { fetchProfile, updateProfile } from "@/lib/api";
import {
  convertHeightToCentimeters,
  convertHeightToUnit,
  convertWeightToKilograms,
  convertWeightToUnit,
  formatHeight,
  formatWeight,
  formatA1c
} from "@/lib/measurements";

const HEIGHT_UNIT_OPTIONS: Array<{ label: string; value: HeightUnit }> = [
  { label: "cm", value: "cm" },
  { label: "ft", value: "ft" }
];

const WEIGHT_UNIT_OPTIONS: Array<{ label: string; value: WeightUnit }> = [
  { label: "kg", value: "kg" },
  { label: "lb", value: "lb" }
];

const UNDERLYING_DISEASE_OPTIONS: Array<{ label: string; value: string }> = [
  { label: "Type 1 Diabetes", value: "Type 1 Diabetes" },
  { label: "Type 2 Diabetes", value: "Type 2 Diabetes" },
  { label: "Prediabetes", value: "Prediabetes" },
  { label: "Healthy Mode", value: "Healthy" }
];

const GENDER_OPTIONS: Array<{ label: string; value: string }> = [
  { label: "Female", value: "female" },
  { label: "Male", value: "male" },
  { label: "Other / Prefer not to say", value: "other" },
];

export default function ProfilePage() {
  return (
    <section className="space-y-8">
      <header className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div>
          <p className="text-sm uppercase tracking-normal text-slate-500">
            Profile
          </p>
          <h1 className="mt-2 text-4xl font-semibold text-slate-900">
            Body metrics
          </h1>
          <p className="mt-3 max-w-2xl text-base text-slate-600">
            Keep numbers current.
          </p>
        </div>
      </header>

      <div className="grid gap-6 xl:grid-cols-[1.05fr,0.55fr]">
        <ProfileForm />
        <StatusPreview />
      </div>
    </section>
  );
}

function ProfileForm() {
  const router = useRouter();
  const {
    metrics: { age, height, weight, gender, heightUnit, weightUnit, a1c, underlyingDisease },
    updateMetrics
  } = useUser();

  const [ageValue, setAgeValue] = useState("");
  const [heightValue, setHeightValue] = useState("");
  const [weightValue, setWeightValue] = useState("");
  const [a1cValue, setA1cValue] = useState("");
  const [genderValue, setGenderValue] = useState("");
  const [diseaseValue, setDiseaseValue] = useState("");
  const [heightUnitState, setHeightUnitState] = useState<HeightUnit>("cm");
  const [weightUnitState, setWeightUnitState] = useState<WeightUnit>("kg");
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    let redirectTimer: number | undefined;

    const loadProfile = async () => {
      try {
        const profile = await fetchProfile();
        if (cancelled) {
          return;
        }
        updateMetrics({
          age: typeof profile.age === "number" ? profile.age : null,
          height: typeof profile.height_cm === "number" ? profile.height_cm : null,
          weight: typeof profile.weight_kg === "number" ? profile.weight_kg : null,
          gender: typeof profile.gender === "string" ? profile.gender : null,
          underlyingDisease: profile.underlying_disease ?? null
        });
        setErrorMessage(null);
      } catch (error) {
        if (!cancelled) {
          const message = error instanceof Error ? error.message : "Failed to load profile";
          setErrorMessage(message);
          if (message.toLowerCase().includes("not logged in")) {
            redirectTimer = window.setTimeout(() => {
              router.replace("/login");
            }, 1200);
          }
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    };

    loadProfile();

    return () => {
      cancelled = true;
      if (redirectTimer) {
        window.clearTimeout(redirectTimer);
      }
    };
  }, [router, updateMetrics]);

  useEffect(() => {
    setHeightUnitState(heightUnit);
    setWeightUnitState(weightUnit);

    setAgeValue(age != null ? Math.round(age).toString() : "");

    setHeightValue(
      height != null
        ? formatInputForField(
            convertHeightToUnit(height, heightUnit),
            heightUnit === "ft" ? 2 : 1
          )
        : ""
    );
    setWeightValue(
      weight != null
        ? formatInputForField(
            convertWeightToUnit(weight, weightUnit),
            weightUnit === "lb" ? 1 : 1
          )
        : ""
    );
    setA1cValue(a1c != null ? formatInputForField(a1c, 1) : "");
    setDiseaseValue(underlyingDisease ?? "");
    setGenderValue(gender ?? "");
  }, [age, height, weight, heightUnit, weightUnit, a1c, underlyingDisease, gender]);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (isLoading || isSubmitting) {
      return;
    }

    setStatusMessage(null);
    setErrorMessage(null);

    const parsedAge = Number(ageValue);
    if (!Number.isFinite(parsedAge) || parsedAge <= 0) {
      setErrorMessage("Please enter a valid age.");
      return;
    }

    const parsedHeight = parseFloat(heightValue);
    const parsedWeight = parseFloat(weightValue);
    const parsedA1c = parseFloat(a1cValue);

    const heightInCm = Number.isFinite(parsedHeight)
      ? convertHeightToCentimeters(parsedHeight, heightUnitState)
      : null;
    const weightInKg = Number.isFinite(parsedWeight)
      ? convertWeightToKilograms(parsedWeight, weightUnitState)
      : null;

    if (heightInCm == null || heightInCm <= 0) {
      setErrorMessage("Please enter a valid height.");
      return;
    }

    if (weightInKg == null || weightInKg <= 0) {
      setErrorMessage("Please enter a valid weight.");
      return;
    }

    if (!diseaseValue) {
      setErrorMessage("Select an underlying condition.");
      return;
    }

    setIsSubmitting(true);
    try {
      const savedProfile = await updateProfile({
        age: Math.round(parsedAge),
        height_cm: heightInCm,
        weight_kg: weightInKg,
        gender: genderValue || null,
        underlying_disease: diseaseValue,
      });

      updateMetrics({
        age: typeof savedProfile.age === "number" ? savedProfile.age : Math.round(parsedAge),
        height: typeof savedProfile.height_cm === "number" ? savedProfile.height_cm : heightInCm,
        weight: typeof savedProfile.weight_kg === "number" ? savedProfile.weight_kg : weightInKg,
        gender: typeof savedProfile.gender === "string" ? savedProfile.gender : (genderValue || null),
        heightUnit: heightUnitState,
        weightUnit: weightUnitState,
        a1c: Number.isFinite(parsedA1c) ? parsedA1c : null,
        underlyingDisease: savedProfile.underlying_disease ?? diseaseValue,
      });

      setStatusMessage("Profile saved.");
      setTimeout(() => setStatusMessage(null), 2800);
    } catch (error: unknown) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to save profile.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleHeightUnitChange = (unit: HeightUnit) => {
    if (unit === heightUnitState) {
      return;
    }
    const numeric = parseFloat(heightValue);
    const baseCm = Number.isFinite(numeric)
      ? convertHeightToCentimeters(numeric, heightUnitState)
      : null;
    setHeightUnitState(unit);
    if (baseCm != null) {
      const converted = convertHeightToUnit(baseCm, unit);
      setHeightValue(
        formatInputForField(converted, unit === "ft" ? 2 : 1)
      );
    } else {
      setHeightValue("");
    }
  };

  const handleWeightUnitChange = (unit: WeightUnit) => {
    if (unit === weightUnitState) {
      return;
    }
    const numeric = parseFloat(weightValue);
    const baseKg = Number.isFinite(numeric)
      ? convertWeightToKilograms(numeric, weightUnitState)
      : null;
    setWeightUnitState(unit);
    if (baseKg != null) {
      const converted = convertWeightToUnit(baseKg, unit);
      setWeightValue(formatInputForField(converted, 1));
    } else {
      setWeightValue("");
    }
  };

  const isBusy = isSubmitting || isLoading;

  return (
    <Card className="rounded-3xl border-0 bg-white px-5 py-6 sm:px-7 sm:py-8">
      <CardHeader className="space-y-1.5 p-0">
      </CardHeader>
      <CardContent className="mt-10 p-0">
        <form className="space-y-8" onSubmit={handleSubmit} aria-busy={isBusy}>
          {isLoading ? (
            <p className="text-sm text-slate-500" aria-live="polite">
              Loading profile...
            </p>
          ) : null}
          <div className="grid gap-6 md:grid-cols-2 xl:grid-cols-3">
            <SimpleField
              id="age"
              label="Age"
              placeholder="e.g. 30"
              value={ageValue}
              onChange={setAgeValue}
              suffix="yrs"
              disabled={isBusy}
            />
            <MeasurementField
              id="height"
              label="Height"
              placeholder={heightUnitState === "ft" ? "e.g. 5.8" : "e.g. 170"}
              value={heightValue}
              onChange={setHeightValue}
              unitValue={heightUnitState}
              onUnitChange={handleHeightUnitChange}
              unitOptions={HEIGHT_UNIT_OPTIONS}
              disabled={isBusy}
            />
          <MeasurementField
            id="weight"
            label="Weight"
            placeholder={weightUnitState === "lb" ? "e.g. 132" : "e.g. 60"}
            value={weightValue}
            onChange={setWeightValue}
            unitValue={weightUnitState}
            onUnitChange={handleWeightUnitChange}
            unitOptions={WEIGHT_UNIT_OPTIONS}
            disabled={isBusy}
          />
          <SelectField
            id="gender"
            label="Gender"
            value={genderValue}
            onChange={setGenderValue}
            options={GENDER_OPTIONS}
            disabled={isBusy}
          />
          <SimpleField
            id="a1c"
            label="A1c"
            placeholder="e.g. 5.4"
            value={a1cValue}
            onChange={setA1cValue}
            suffix="%"
            disabled={isBusy}
          />
          </div>

          <SelectField
            id="underlying-disease"
            label="Underlying condition"
            value={diseaseValue}
            onChange={setDiseaseValue}
            options={UNDERLYING_DISEASE_OPTIONS}
            disabled={isBusy}
          />

          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <Button
              type="submit"
              disabled={isBusy}
              className="rounded-full bg-emerald-600 px-8 py-3 text-sm font-semibold text-white shadow-lg shadow-emerald-200/40 transition-all hover:-translate-y-0.5 hover:bg-emerald-700 focus-visible:ring-emerald-500"
            >
              {isSubmitting ? "Saving..." : "Save"}
            </Button>
            {errorMessage ? (
              <span className="text-sm text-red-500" aria-live="assertive">
                {errorMessage}
              </span>
            ) : null}
            {statusMessage ? (
              <span className="text-sm text-slate-500" aria-live="polite">
                {statusMessage}
              </span>
            ) : null}
          </div>
        </form>
      </CardContent>
    </Card>
  );
}

function MeasurementField<T extends HeightUnit | WeightUnit>({
  id,
  label,
  placeholder,
  value,
  onChange,
  unitOptions,
  unitValue,
  onUnitChange,
  disabled
}: {
  id: string;
  label: string;
  placeholder: string;
  value: string;
  onChange: (value: string) => void;
  unitOptions: Array<{ label: string; value: T }>;
  unitValue: T;
  onUnitChange: (value: T) => void;
  disabled?: boolean;
}) {
  return (
    <label className="group relative flex flex-col rounded-3xl" htmlFor={id}>
      <span className="mb-3 text-sm font-medium uppercase tracking-normal text-slate-500">
        {label}
      </span>
      <div className="flex items-center gap-4">
        <div className="relative flex-1">
        <Input
          id={id}
          name={id}
          type="number"
          inputMode="decimal"
          placeholder={placeholder}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          disabled={disabled}
          className="h-16 w-full rounded-2xl border border-white/60 bg-[#edf1f9] text-lg text-slate-800 placeholder:text-slate-400 focus-visible:ring-2 focus-visible:ring-emerald-400"
        />
        </div>
        <UnitToggle
          options={unitOptions}
          current={unitValue}
          onChange={onUnitChange}
          disabled={disabled}
        />
      </div>
    </label>
  );
}

function SimpleField({
  id,
  label,
  placeholder,
  value,
  onChange,
  suffix,
  disabled
}: {
  id: string;
  label: string;
  placeholder: string;
  value: string;
  onChange: (value: string) => void;
  suffix?: string;
  disabled?: boolean;
}) {
  return (
    <label className="group relative flex flex-col rounded-3xl" htmlFor={id}>
      <span className="mb-3 text-sm font-medium uppercase tracking-normal text-slate-500">
        {label}
      </span>
      <div className="relative flex items-center">
        <Input
          id={id}
          name={id}
          type="number"
          inputMode="decimal"
          placeholder={placeholder}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          disabled={disabled}
          className={`${id === "age" ? "h-12" : "h-14"} w-full rounded-2xl border border-white/60 bg-[#edf1f9] text-base text-slate-800 placeholder:text-slate-400 focus-visible:ring-2 focus-visible:ring-emerald-400`}
        />
        {suffix ? (
          <span className="pointer-events-none absolute right-4 text-xs font-semibold uppercase text-slate-400">
            {suffix}
          </span>
        ) : null}
      </div>
    </label>
  );
}

function UnitToggle<T extends HeightUnit | WeightUnit>({
  options,
  current,
  onChange,
  disabled
}: {
  options: Array<{ label: string; value: T }>;
  current: T;
  onChange: (value: T) => void;
  disabled?: boolean;
}) {
  return (
    <div className="inline-flex rounded-full bg-[#edf1f9] p-1 shadow-[inset_6px_6px_12px_rgba(209,217,230,0.55),inset_-6px_-6px_12px_rgba(255,255,255,0.9)]">
      {options.map((option) => {
        const active = option.value === current;
        return (
          <button
            key={option.value}
            type="button"
            onClick={() => onChange(option.value)}
            disabled={disabled}
            className={`relative min-w-[64px] rounded-full px-4 py-2 text-xs font-semibold uppercase tracking-normal transition-all ${
              active
                ? "text-emerald-600 shadow-[6px_6px_12px_rgba(209,217,230,0.4),_-6px_-6px_12px_rgba(255,255,255,0.95)] bg-white"
                : "text-slate-500"
            }`}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}

function SelectField({
  id,
  label,
  value,
  onChange,
  options,
  disabled
}: {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: Array<{ label: string; value: string }>;
  disabled?: boolean;
}) {
  return (
    <label className="group relative flex flex-col rounded-3xl" htmlFor={id}>
      <span className="mb-3 text-sm font-medium uppercase tracking-normal text-slate-500">
        {label}
      </span>
      <select
        id={id}
        name={id}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        disabled={disabled}
        required
        className="h-14 w-full rounded-2xl border border-white/60 bg-[#edf1f9] px-4 text-base text-slate-800 focus-visible:ring-2 focus-visible:ring-emerald-400"
      >
        <option value="" disabled={Boolean(value)}>
          Select an option
        </option>
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  );
}

function StatusPreview() {
  const {
    metrics: { age, height, weight, gender, heightUnit, weightUnit, a1c, underlyingDisease }
  } = useUser();

  return (
    <div className="flex h-full flex-col gap-6">
      <Card className="neu-surface rounded-3xl border-0 px-5 py-6 sm:px-6 sm:py-8">
        <CardHeader className="space-y-2 p-0">
          <CardTitle className="text-lg font-semibold text-slate-900">
            Latest record
          </CardTitle>
          <CardDescription className="text-sm text-slate-500">
            Used across tools.
          </CardDescription>
        </CardHeader>
        <CardContent className="mt-8 grid gap-6 p-0">
          <MetricBadge label="Age" value={formatAge(age)} />
          <MetricBadge label="Gender" value={formatGender(gender)} />
          <MetricBadge
            label="Height"
            value={formatHeight(height, heightUnit)}
          />
          <MetricBadge
            label="Weight"
            value={formatWeight(weight, weightUnit)}
          />
          <MetricBadge label="Condition" value={formatUnderlyingDisease(underlyingDisease)} />
          <MetricBadge label="A1c" value={formatA1c(a1c)} />
        </CardContent>
      </Card>
    </div>
  );
}

function MetricBadge({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-2 rounded-2xl bg-[#edf1f9] px-5 py-4 shadow-[8px_8px_16px_rgba(209,217,230,0.6),_-8px_-8px_16px_rgba(255,255,255,0.9)]">
      <span className="text-xs uppercase tracking-normal text-slate-500">
        {label}
      </span>
      <span className="text-lg font-semibold text-slate-900">{value}</span>
    </div>
  );
}

function formatInputForField(value: number, digits: number) {
  const rounded = Number(value.toFixed(digits));
  return Number.isFinite(rounded) ? rounded.toString() : "";
}

function formatAge(age: number | null) {
  if (age == null || Number.isNaN(age)) {
    return "-";
  }
  return `${Math.round(age)} yrs`;
}

function formatGender(value: string | null) {
  if (!value) {
    return "-";
  }
  const s = value.trim();
  if (!s) {
    return "-";
  }
  return s.charAt(0).toUpperCase() + s.slice(1);
}

function formatUnderlyingDisease(value: string | null) {
  return value && value.trim().length > 0 ? value : "-";
}
