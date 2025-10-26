'use client';

import { FormEvent, useEffect, useState } from "react";
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
  const {
    metrics: { height, weight, heightUnit, weightUnit, a1c },
    updateMetrics
  } = useUser();

  const [heightValue, setHeightValue] = useState("");
  const [weightValue, setWeightValue] = useState("");
  const [a1cValue, setA1cValue] = useState("");
  const [heightUnitState, setHeightUnitState] = useState<HeightUnit>("cm");
  const [weightUnitState, setWeightUnitState] = useState<WeightUnit>("kg");
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  useEffect(() => {
    setHeightUnitState(heightUnit);
    setWeightUnitState(weightUnit);

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
  }, [height, weight, heightUnit, weightUnit, a1c]);

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    const parsedHeight = parseFloat(heightValue);
    const parsedWeight = parseFloat(weightValue);
    const parsedA1c = parseFloat(a1cValue);

    const heightInCm = Number.isFinite(parsedHeight)
      ? convertHeightToCentimeters(parsedHeight, heightUnitState)
      : null;
    const weightInKg = Number.isFinite(parsedWeight)
      ? convertWeightToKilograms(parsedWeight, weightUnitState)
      : null;

    updateMetrics({
      height: heightInCm,
      weight: weightInKg,
      heightUnit: heightUnitState,
      weightUnit: weightUnitState,
      a1c: Number.isFinite(parsedA1c) ? parsedA1c : null
    });

    setStatusMessage("Metrics saved successfully.");
    setTimeout(() => setStatusMessage(null), 2800);
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

  return (
    <Card className="rounded-3xl border-0 bg-white px-5 py-6 sm:px-7 sm:py-8">
      <CardHeader className="space-y-1.5 p-0">
      </CardHeader>
      <CardContent className="mt-10 p-0">
        <form className="space-y-8" onSubmit={handleSubmit}>
          <div className="grid gap-6 md:grid-cols-2 xl:grid-cols-3">
            <MeasurementField
              id="height"
              label="Height"
              placeholder={heightUnitState === "ft" ? "e.g. 5.8" : "e.g. 170"}
              value={heightValue}
              onChange={setHeightValue}
              unitValue={heightUnitState}
              onUnitChange={handleHeightUnitChange}
              unitOptions={HEIGHT_UNIT_OPTIONS}
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
            />
            <SimpleField
              id="a1c"
              label="A1c"
              placeholder="e.g. 5.4"
              value={a1cValue}
              onChange={setA1cValue}
              suffix="%"
            />
          </div>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <Button
              type="submit"
              className="rounded-full bg-emerald-600 px-8 py-3 text-sm font-semibold text-white shadow-lg shadow-emerald-200/40 transition-all hover:-translate-y-0.5 hover:bg-emerald-700 focus-visible:ring-emerald-500"
            >
              Save
            </Button>
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
  onUnitChange
}: {
  id: string;
  label: string;
  placeholder: string;
  value: string;
  onChange: (value: string) => void;
  unitOptions: Array<{ label: string; value: T }>;
  unitValue: T;
  onUnitChange: (value: T) => void;
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
          className="h-14 w-full rounded-2xl border border-white/60 bg-[#edf1f9] text-base text-slate-800 placeholder:text-slate-400 focus-visible:ring-2 focus-visible:ring-emerald-400"
        />
        </div>
        <UnitToggle
          options={unitOptions}
          current={unitValue}
          onChange={onUnitChange}
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
  suffix
}: {
  id: string;
  label: string;
  placeholder: string;
  value: string;
  onChange: (value: string) => void;
  suffix?: string;
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
          className="h-14 w-full rounded-2xl border border-white/60 bg-[#edf1f9] text-base text-slate-800 placeholder:text-slate-400 focus-visible:ring-2 focus-visible:ring-emerald-400"
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
  onChange
}: {
  options: Array<{ label: string; value: T }>;
  current: T;
  onChange: (value: T) => void;
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

function StatusPreview() {
  const {
    metrics: { height, weight, heightUnit, weightUnit, a1c }
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
          <MetricBadge
            label="Height"
            value={formatHeight(height, heightUnit)}
          />
          <MetricBadge
            label="Weight"
            value={formatWeight(weight, weightUnit)}
          />
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
