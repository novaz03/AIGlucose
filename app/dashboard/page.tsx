'use client';

import { useEffect, useMemo, useState } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle
} from "@/components/ui/card";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";
import { useUser } from "@/context/UserContext";
import { fetchForecast, fetchProfile } from "@/lib/api";

type ChartPoint = {
  minute: number;
  glucose: number;
};

function toNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === "string") {
    const parsed = Number.parseFloat(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

export default function DashboardPage() {
  const {
    metrics: { age, height, weight, gender, underlyingDisease },
    updateMetrics
  } = useUser();

  const [chartPoints, setChartPoints] = useState<ChartPoint[]>([]);
  const [loadingForecast, setLoadingForecast] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [profileStatus, setProfileStatus] = useState<
    "idle" | "loading" | "loaded" | "error"
  >("idle");
  const [baselineGlucose, setBaselineGlucose] = useState<number | null>(null);

  useEffect(() => {
    if (profileStatus !== "idle") {
      return;
    }
    if (height != null && weight != null && age != null) {
      setProfileStatus("loaded");
      return;
    }

    let cancelled = false;

    const loadProfile = async () => {
      setProfileStatus("loading");
      try {
        const profile = await fetchProfile();
        if (cancelled) {
          return;
        }
        updateMetrics({
          age: typeof profile.age === "number" ? profile.age : null,
          height:
            typeof profile.height_cm === "number" ? profile.height_cm : null,
          weight:
            typeof profile.weight_kg === "number" ? profile.weight_kg : null,
          underlyingDisease: profile.underlying_disease ?? null
        });
        setErrorMessage(null);
        setProfileStatus("loaded");
      } catch (error) {
        if (cancelled) {
          return;
        }
        const message =
          error instanceof Error ? error.message : "Unable to load profile.";
        setErrorMessage(message);
        setProfileStatus("error");
      }
    };

    loadProfile();

    return () => {
      cancelled = true;
    };
  }, [age, height, weight, profileStatus, updateMetrics]);

  useEffect(() => {
    if (height == null || weight == null) {
      // Try to load a cached forecast from chat if available
      try {
        const raw = sessionStorage.getItem('last_forecast');
        if (raw) {
          const data = JSON.parse(raw);
          const mins = Array.isArray(data?.minutes) ? data.minutes : [];
          const abs = Array.isArray(data?.absolute_glucose) ? data.absolute_glucose : [];
          const points = mins.reduce<ChartPoint[]>((acc, minute, i) => {
            const glucose = typeof abs[i] === 'number' ? abs[i] : null;
            if (glucose != null) acc.push({ minute, glucose });
            return acc;
          }, []);
          setChartPoints(points);
        } else {
          setChartPoints([]);
        }
      } catch {
        setChartPoints([]);
      }
      setBaselineGlucose(null);
      setLoadingForecast(false);
      return;
    }

    let cancelled = false;
    setLoadingForecast(true);
    setErrorMessage(null);

    const loadForecast = async () => {
      try {
        const forecast = await fetchForecast({
          height_cm: height,
          weight_kg: weight,
          age: age ?? undefined,
          gender: gender ?? undefined,
        });
        if (cancelled) {
          return;
        }

        const baseline = toNumber(
          forecast.inputs_used?.baseline_avg_glucose
        );
        setBaselineGlucose(baseline);

        const series = forecast.minutes.reduce<ChartPoint[]>(
          (acc, minute, index) => {
            const glucose = toNumber(
              forecast.absolute_glucose?.[index]
            );
            if (typeof minute === "number" && glucose != null) {
              acc.push({ minute, glucose });
            }
            return acc;
          },
          []
        );

        if (baseline != null) {
          series.unshift({ minute: 0, glucose: baseline });
        }

        if (!series.length) {
          setErrorMessage("Forecast returned no data.");
        }

        setChartPoints(series);
      } catch (error) {
        if (cancelled) {
          return;
        }
        const message = error instanceof Error ? error.message : "Prediction failed.";
        setErrorMessage(message);
        setChartPoints([]);
      } finally {
        if (!cancelled) {
          setLoadingForecast(false);
        }
      }
    };

    loadForecast();

    return () => {
      cancelled = true;
    };
  }, [age, height, weight, gender]);

  const yDomain = useMemo<[number, number]>(() => {
    if (!chartPoints.length) {
      return [80, 160];
    }
    const values = chartPoints.map((point) => point.glucose);
    const min = Math.min(...values);
    const max = Math.max(...values);
    if (!Number.isFinite(min) || !Number.isFinite(max)) {
      return [80, 160];
    }
    const padding = Math.max(5, Math.round((max - min) * 0.08));
    const lower = Math.floor((min - padding) / 5) * 5;
    const upper = Math.ceil((max + padding) / 5) * 5;
    return [Math.max(60, lower), Math.min(250, upper)];
  }, [chartPoints]);

  const statusMessage = useMemo(() => {
    if (loadingForecast) {
      return "Generating forecast, please wait...";
    }
    if (errorMessage) {
      return errorMessage;
    }
    if (!chartPoints.length) {
      return "Add height and weight in the Profile page to generate a forecast.";
    }
    const heightText =
      height != null ? `${Math.round(height)} cm` : "height unknown";
    const weightText =
      weight != null ? `${Math.round(weight)} kg` : "weight unknown";
    const baselineText =
      baselineGlucose != null
        ? `Baseline glucose ${baselineGlucose.toFixed(0)} mg/dL`
        : "Baseline glucose assumed at 100 mg/dL";
    const messageParts = [
      `Forecast generated with height ${heightText} and weight ${weightText}.`,
      `${baselineText}.`
    ];
    if (underlyingDisease) {
      messageParts.push(`Condition: ${underlyingDisease}.`);
    }
    return messageParts.join(" ");
  }, [
    baselineGlucose,
    chartPoints.length,
    errorMessage,
    height,
    loadingForecast,
    underlyingDisease,
    weight
  ]);

  return (
    <section className="space-y-8">
      <header className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div>
          <p className="text-sm uppercase tracking-normal text-slate-500">
            Forecast
          </p>
          <h1 className="mt-2 text-4xl font-semibold text-slate-900">
            Glucose outlook
          </h1>
          <p className="mt-3 max-w-3xl text-base text-slate-600">
            Watch the next curve.
          </p>
        </div>
      </header>

      <div className="grid gap-6 xl:grid-cols-[1.1fr,0.9fr]">
        <Card className="rounded-3xl border-0 bg-white px-5 py-6 sm:px-7 sm:py-8">
          <CardHeader className="space-y-3 p-0">
            <CardTitle className="text-lg font-semibold text-slate-900">
              Forecast window
            </CardTitle>
            <CardDescription className="text-sm text-slate-600">
              Projected glucose for the next two hours.
            </CardDescription>
          </CardHeader>
          <CardContent className="mt-6 space-y-6 p-0">
            <div className="rounded-3xl bg-gradient-to-br from-emerald-100 via-white to-sky-100 px-5 py-4 text-sm text-emerald-700">
              {statusMessage}
            </div>
            <div
              className="rounded-[26px] border border-white/50 bg-[#edf1f9] p-4 sm:rounded-[32px] sm:p-6"
              style={{ height: 320 }}
            >
              {chartPoints.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartPoints}>
                    <CartesianGrid strokeDasharray="8 8" stroke="#d8e0ec" />
                    <XAxis
                      dataKey="minute"
                      type="number"
                      stroke="#94a3b8"
                      domain={[0, 120]}
                      ticks={[0, 30, 60, 90, 120]}
                      tickFormatter={(value) => `${value} min`}
                      tick={{ fontSize: 12, fill: "#64748b" }}
                    />
                    <YAxis
                      stroke="#94a3b8"
                      domain={yDomain}
                      label={{
                        value: "Glucose (mg/dL)",
                        angle: -90,
                        position: "insideLeft",
                        style: { textAnchor: "middle", fill: "#64748b" }
                      }}
                      tick={{ fontSize: 12, fill: "#64748b" }}
                      tickCount={6}
                    />
                    <Tooltip
                      formatter={(value: number | string) => {
                        const numeric = Number(value);
                        const pretty = Number.isFinite(numeric)
                          ? `${numeric.toFixed(0)} mg/dL`
                          : `${value}`;
                        return [pretty, "Predicted"];
                      }}
                      labelFormatter={(value) => `${value} min`}
                      labelStyle={{ color: "#0f172a" }}
                      contentStyle={{
                        borderRadius: 20,
                        border: "1px solid rgba(148,163,184,0.2)",
                        boxShadow:
                          "12px 12px 24px rgba(209,217,230,0.4), -12px -12px 24px rgba(255,255,255,0.8)"
                      }}
                    />
                    <Line
                      type="monotone"
                      dataKey="glucose"
                      stroke="#10b981"
                      strokeWidth={3}
                      dot={false}
                      activeDot={{
                        r: 6,
                        strokeWidth: 2,
                        stroke: "#0ea5e9",
                        fill: "#ffffff"
                      }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <div className="flex h-full items-center justify-center text-sm text-slate-500">
                  {loadingForecast
                    ? "Generating forecast..."
                    : errorMessage ?? "No forecast available"}
                </div>
              )}
            </div>
          </CardContent>
        </Card>
        <Card className="neu-surface rounded-3xl border-0 px-5 py-6 sm:px-7 sm:py-8">
          <CardHeader className="space-y-3 p-0">
            <CardTitle className="text-lg font-semibold text-slate-900">
              Stability notes
            </CardTitle>
            <CardDescription className="text-sm text-slate-600">
              Blend with meals.
            </CardDescription>
          </CardHeader>
          <CardContent className="mt-8 space-y-5 p-0">
            <InsightPill
              title="Post-meal walk"
              detail="10–15 min"
              description="Light steps smooth peaks."
            />
            <InsightPill
              title="Hydration"
              detail="2.5 L"
              description="Steady fluids aid balance."
            />
            <InsightPill
              title="Fiber boost"
              detail="+5 g"
              description="Greens help flatten spikes."
            />
          </CardContent>
        </Card>
      </div>
    </section>
  );
}

function InsightPill({
  title,
  detail,
  description
}: {
  title: string;
  detail: string;
  description: string;
}) {
  return (
    <div className="space-y-3 rounded-3xl bg-[#f2f5fb] px-6 py-5 shadow-[12px_12px_24px_rgba(209,217,230,0.4),_-12px_-12px_24px_rgba(255,255,255,0.9)]">
      <div className="flex items-center justify-between">
        <span className="text-sm font-semibold text-slate-800">{title}</span>
        <span className="rounded-full bg-white px-4 py-1 text-xs font-semibold uppercase tracking-normal text-emerald-500 shadow-[6px_6px_12px_rgba(209,217,230,0.35),_-6px_-6px_12px_rgba(255,255,255,0.8)]">
          {detail}
        </span>
      </div>
      <p className="text-sm text-slate-600">{description}</p>
    </div>
  );
}
