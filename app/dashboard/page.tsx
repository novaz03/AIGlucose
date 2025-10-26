'use client';

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

const predictionData = [
  { time: "14:00", level: 90 },
  { time: "14:30", level: 110 },
  { time: "15:00", level: 135 },
  { time: "15:30", level: 120 },
  { time: "16:00", level: 100 }
];

export default function DashboardPage() {
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
              Keep your latest readings synced for sharper predictions.
            </div>
            <div
              className="rounded-[26px] border border-white/50 bg-[#edf1f9] p-4 sm:rounded-[32px] sm:p-6"
              style={{ height: 320 }}
            >
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={predictionData}>
                  <CartesianGrid strokeDasharray="8 8" stroke="#d8e0ec" />
                  <XAxis
                    dataKey="time"
                    stroke="#94a3b8"
                    tick={{ fontSize: 12, fill: "#64748b" }}
                  />
                  <YAxis
                    stroke="#94a3b8"
                    label={{
                      value: "Glucose (mg/dL)",
                      angle: -90,
                      position: "insideLeft",
                      style: { textAnchor: "middle", fill: "#64748b" }
                    }}
                    domain={[80, 160]}
                    tick={{ fontSize: 12, fill: "#64748b" }}
                    tickCount={5}
                  />
                  <Tooltip
                    formatter={(value: number) => [`${value} mg/dL`, "Predicted"]}
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
                    dataKey="level"
                    stroke="#10b981"
                    strokeWidth={3}
                    dot={{ r: 4 }}
                    activeDot={{
                      r: 8,
                      strokeWidth: 2,
                      stroke: "#0ea5e9",
                      fill: "#ffffff"
                    }}
                  />
                </LineChart>
              </ResponsiveContainer>
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
