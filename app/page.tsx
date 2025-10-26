import Link from "next/link";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";

export default function HomePage() {
  return (
    <section className="space-y-10">
      <header className="flex flex-col gap-6 text-slate-900 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-sm uppercase tracking-normal text-slate-500">
            Wellness suite
          </p>
          <h1 className="mt-2 text-5xl font-semibold">Stay balanced</h1>
          <p className="mt-4 max-w-2xl text-base text-slate-600">
            Sync profile, meals, trends.
          </p>
        </div>
      </header>

      <div className="grid gap-6 md:grid-cols-3">
        <FeatureCard
          title="Profile metrics"
          description="Track height and weight."
          href="/profile"
          cta="Open"
        />
        <FeatureCard
          title="AI recipes"
          description="Ask fast meal ideas."
          href="/login"
          cta="Open"
        />
        <FeatureCard
          title="Forecast"
          description="See upcoming curve."
          href="/dashboard"
          cta="Open"
        />
      </div>
    </section>
  );
}

function FeatureCard({
  title,
  description,
  href,
  cta
}: {
  title: string;
  description: string;
  href: string;
  cta: string;
}) {
  return (
    <Card className="neu-surface flex h-full flex-col rounded-3xl border-0 px-5 py-6 sm:px-6 sm:py-8">
      <CardHeader className="space-y-3 p-0">
        <CardTitle className="text-xl font-semibold text-slate-900">
          {title}
        </CardTitle>
        <CardDescription className="text-sm text-slate-600">
          {description}
        </CardDescription>
      </CardHeader>
      <CardContent className="mt-auto flex justify-end p-0">
        <Button
          asChild
          className="rounded-full bg-emerald-600 px-6 py-3 text-sm font-semibold text-white shadow-lg shadow-emerald-200/40 transition-all hover:bg-emerald-700 focus-visible:ring-emerald-500"
        >
          <Link href={href}>{cta}</Link>
        </Button>
      </CardContent>
    </Card>
  );
}
