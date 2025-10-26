'use client';

import { FormEvent, useState, type ReactNode, useEffect, Suspense } from "react";
import { useSearchParams } from 'next/navigation';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { greet, sendMessage } from "@/lib/api";

type Message =
  | {
      id: string;
      role: "user";
      text: string;
    }
  | {
      id: string;
      role: "assistant";
      text: string;
    };

function ChatPageContent() {
  const searchParams = useSearchParams();
  const userId = searchParams.get('userId');
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isSessionActive, setIsSessionActive] = useState(false);

  useEffect(() => {
    if (!userId) return;

    const initializeChat = async () => {
      setIsLoading(true);
      try {
        const greetingData = await greet();
        if (greetingData.messages) {
          const assistantMessages = greetingData.messages.map((msg: any) => ({
            id: createMessageId(),
            role: "assistant",
            text: msg.text,
          }));
          setMessages(assistantMessages);
        }
        setIsSessionActive(true);
      } catch (error) {
        console.error("Initialization failed:", error);
        // Handle error appropriately
      } finally {
        setIsLoading(false);
      }
    };

    initializeChat();
  }, [userId]);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmed = inputValue.trim();
    if (!trimmed || !isSessionActive) {
      return;
    }

    const userMessageId = createMessageId();
    setMessages((prev) => [
      ...prev,
      { id: userMessageId, role: "user", text: trimmed },
    ]);
    setInputValue("");
    setIsLoading(true);

    try {
      const response = await sendMessage(trimmed);
      if (response.messages) {
        const assistantMessages = response.messages.map((msg: any) => ({
          id: createMessageId(),
          role: "assistant",
          text: msg.text,
        }));
        setMessages((prev) => [...prev, ...assistantMessages]);
      }
      if (response.finished) {
        setIsSessionActive(false);
      }
    } catch (error) {
      console.error("Sending message failed:", error);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <section className="space-y-8">
      <header className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div>
          <p className="text-sm uppercase tracking-normal text-slate-500">
            Recipes
          </p>
          <h1 className="mt-2 text-4xl font-semibold text-slate-900">
            AI Recipes for User: {userId}
          </h1>
          <p className="mt-3 max-w-2xl text-base text-slate-600">
            Tell us what ingredients you have.
          </p>
        </div>
      </header>

      <div className="grid gap-6 xl:grid-cols-[2fr,1fr]">
        <div className="flex min-h-[520px] flex-col rounded-3xl px-2 py-4 sm:px-4 sm:py-6">
          <div className="h-full flex-1 overflow-y-auto rounded-2xl px-2 py-4 sm:px-3">
            {messages.length === 0 && !isLoading ? (
              <div className="flex h-full flex-col items-center justify-center gap-3 text-center">
                <div className="rounded-full bg-white/80 px-4 py-2 text-xs uppercase tracking-normal text-slate-400 shadow-[8px_8px_16px_rgba(209,217,230,0.5),_-8px_-8px_16px_rgba(255,255,255,0.9)]">
                  start session
                </div>
                <p className="max-w-xs text-sm text-slate-500">
                  Try “chicken, rice”.
                </p>
              </div>
            ) : (
              <div className="flex flex-col gap-4">
                {messages.map((message) =>
                  message.role === "user" ? (
                    <UserBubble key={message.id} text={message.text} />
                  ) : (
                    <AssistantBubble key={message.id} message={message} />
                  )
                )}
              </div>
            )}
            {isLoading ? (
              <div className="mt-4 flex items-center gap-2 text-sm text-slate-500">
                <span className="h-2 w-2 animate-ping rounded-full bg-emerald-400" />
                Crafting your recipe...
              </div>
            ) : null}
          </div>
          <div className="mt-6 border-t border-white/40 pt-6">
            <form
              className="flex w-full flex-col gap-3 sm:flex-row sm:items-center sm:gap-4"
              onSubmit={handleSubmit}
            >
              <Input
                placeholder="Type ingredients"
                value={inputValue}
                onChange={(event) => setInputValue(event.target.value)}
                aria-label="Ingredients prompt"
                disabled={isLoading || !isSessionActive}
                className="h-14 w-full flex-1 rounded-2xl border-0 bg-[#edf1f9] text-sm shadow-[inset_6px_6px_12px_rgba(209,217,230,0.6),inset_-6px_-6px_12px_rgba(255,255,255,0.9)] placeholder:text-slate-400 focus-visible:ring-2 focus-visible:ring-emerald-400"
              />
              <Button
                type="submit"
                disabled={isLoading || !isSessionActive}
                className="w-full rounded-full bg-emerald-600 px-8 py-3 text-sm font-semibold text-white shadow-lg shadow-emerald-200/40 transition-all hover:bg-emerald-700 focus-visible:ring-emerald-500 disabled:bg-emerald-300 sm:w-auto"
              >
                Send
              </Button>
            </form>
          </div>
        </div>

        <InsightsPanel />
      </div>
    </section>
  );
}

export default function ChatPage() {
  return (
    <Suspense fallback={<div>Loading...</div>}>
      <ChatPageContent />
    </Suspense>
  );
}

function UserBubble({ text }: { text: string }) {
  return (
    <div className="flex justify-end">
      <div className="w-full max-w-[820px] rounded-3xl bg-[#f2f5fb] px-6 py-4 text-sm text-slate-700 sm:mr-4">
        {text}
      </div>
    </div>
  );
}

function AssistantBubble({ message }: { message: Extract<Message, { role: "assistant" }> }) {
  return (
    <div className="flex justify-start">
      <Card className="w-full max-w-[820px] rounded-3xl border border-white/40 bg-white px-6 py-6 sm:ml-4">
        <div className="flex flex-col gap-5">
          <div>
            <span className="text-xs uppercase tracking-normal text-emerald-500">
              Suggestion
            </span>
            <p className="mt-2 text-sm text-slate-600">{message.text}</p>
          </div>
        </div>
      </Card>
    </div>
  );
}

function InsightsPanel() {
  return (
    <div className="flex h-full flex-col gap-6">
      <Card className="neu-surface rounded-3xl border-0 px-6 py-8">
        <CardHeader className="space-y-2 p-0">
          <CardTitle className="text-lg font-semibold text-slate-900">
            Prompts
          </CardTitle>
          <CardDescription className="text-sm text-slate-500">
            Mix ingredient notes.
          </CardDescription>
        </CardHeader>
        <CardContent className="mt-6 space-y-4 p-0 text-sm text-slate-600">
          <TipPill>High-fiber breakfast</TipPill>
          <TipPill>20-minute lunch</TipPill>
          <TipPill>Low-glycemic dinner</TipPill>
        </CardContent>
      </Card>
      <Card className="neu-surface rounded-3xl border-0 px-6 py-8">
        <CardHeader className="space-y-2 p-0">
          <CardTitle className="text-lg font-semibold text-slate-900">
            Nutrient snapshot
          </CardTitle>
          <CardDescription className="text-sm text-slate-500">
            We balance macros automatically for stable glucose responses.
          </CardDescription>
        </CardHeader>
        <CardContent className="mt-8 grid gap-4 p-0 text-sm text-slate-600">
          <MetricRow label="Target carbs" value="45 g" accent="from-emerald-200 to-emerald-50" />
          <MetricRow label="Lean proteins" value="30 g" accent="from-sky-200 to-sky-50" />
          <MetricRow label="Healthy fats" value="15 g" accent="from-amber-200 to-amber-50" />
        </CardContent>
      </Card>
    </div>
  );
}

function TipPill({ children }: { children: ReactNode }) {
  return (
    <span className="inline-flex items-center justify-between rounded-full bg-[#f3f6fb] px-5 py-3 text-sm font-medium text-slate-700 shadow-[6px_6px_12px_rgba(209,217,230,0.5),_-6px_-6px_12px_rgba(255,255,255,0.9)]">
      {children}
      <span className="ml-3 text-xs font-semibold uppercase tracking-normal text-emerald-500">
        try
      </span>
    </span>
  );
}

function MetricRow({
  label,
  value,
  accent
}: {
  label: string;
  value: string;
  accent: string;
}) {
  return (
    <div
      className={`flex items-center justify-between rounded-2xl bg-gradient-to-br ${accent} px-5 py-4 shadow-[8px_8px_16px_rgba(209,217,230,0.45),_-8px_-8px_16px_rgba(255,255,255,0.9)]`}
    >
      <span className="text-sm uppercase tracking-normal text-slate-500">
        {label}
      </span>
      <span className="text-lg font-semibold text-slate-800">{value}</span>
    </div>
  );
}

function createMessageId() {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}
