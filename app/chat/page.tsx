"use client";
import { FormEvent, useState, type ReactNode, useEffect, Suspense } from "react";
import { useRouter } from 'next/navigation';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { greet, sendMessage, getSession } from "@/lib/api";

type RecipeIngredient = {
  name: string;
  amount: string;
  notes?: string | null;
};

type RecipePayload = {
  title: string;
  ingredients: RecipeIngredient[];
  steps: string[];
};

type AssistantMessage = {
  id: string;
  role: "assistant";
  text?: string;
  recipe?: RecipePayload;
};

type UserMessage = {
  id: string;
  role: "user";
  text: string;
};

type Message = AssistantMessage | UserMessage;

type AssistantMessageInput = {
  text?: string;
  recipe?: RecipePayload;
};

function isPopulatedAssistantEntry(entry: AssistantMessageInput): entry is AssistantMessageInput & { text?: string; recipe: RecipePayload } | AssistantMessageInput & { text: string } {
  const normalizedText = typeof entry.text === "string" ? entry.text.trim() : "";
  return normalizedText.length > 0 || Boolean(entry.recipe);
}

function normalizeAssistantEntry(entry: AssistantMessageInput): AssistantMessage {
  const normalizedText = typeof entry.text === "string" ? entry.text.trim() : "";
  return {
    id: createMessageId(),
    role: "assistant",
    ...(normalizedText.length > 0 ? { text: normalizedText } : {}),
    ...(entry.recipe ? { recipe: entry.recipe } : {}),
  };
}

function ChatPageContent() {
  const router = useRouter();
  const [userId, setUserId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isSessionActive, setIsSessionActive] = useState(false);
  const [sessionError, setSessionError] = useState<string | null>(null);
  const [recipe, setRecipe] = useState<RecipePayload | null>(null);

  const appendAssistantMessages = (entries: AssistantMessageInput[]) => {
    if (entries.length === 0) {
      return;
    }

    const normalized = entries
      .filter(isPopulatedAssistantEntry)
      .map(normalizeAssistantEntry);

    if (normalized.length === 0) {
      return;
    }

    setMessages((prev) => [
      ...prev,
      ...normalized,
    ]);
  };

  const reinitializeSession = async () => {
    setIsLoading(true);
    setIsSessionActive(false);
    setRecipe(null);
    try {
      const greetingData = await greet();
      const greetingMessages = Array.isArray(greetingData.messages)
        ? greetingData.messages
          .map((msg: any) => String(msg?.text ?? ""))
          .filter((txt: string) => txt.trim().length > 0)
        : [];
      setSessionError(null);
      appendAssistantMessages(greetingMessages.map((text) => ({ text })));
      setIsSessionActive(true);
    } catch (error) {
      console.error("Failed to reinitialise session:", error);
      setSessionError("Unable to restart the session. Please try again later.");
      setIsSessionActive(false);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    let redirectTimer: number | undefined;
    let cancelled = false;

    const initializeChat = async () => {
      setIsLoading(true);

      try {
        const currentUserId = await getSession();
        if (cancelled) {
          return;
        }
        setUserId(String(currentUserId));
        setSessionError(null);
        setMessages([]);
      } catch (error) {
        console.error("Session lookup failed:", error);
        const message = error instanceof Error ? error.message : "Not authenticated";
        if (!cancelled) {
          setSessionError("Session expired. Please sign in again.");
          setIsSessionActive(false);
          setUserId(null);
          setRecipe(null);
          const normalized = message.toLowerCase();
          if (normalized.includes("not authenticated") || normalized.includes("not logged")) {
            redirectTimer = window.setTimeout(() => {
              router.replace("/login");
            }, 1200);
          }
          setIsLoading(false);
        }
        return;
      }

      try {
        const greetingData = await greet();
        if (cancelled) {
          return;
        }
        if (greetingData.messages) {
          const assistantMessages: AssistantMessage[] = [];
          greetingData.messages
            .map((msg: any) => String(msg.text ?? ""))
            .forEach((rawText: string) => {
              const text = rawText.trim();
              if (!text) {
                return;
              }
              const recipeFromText = parseRecipeText(text);
              if (recipeFromText) {
                assistantMessages.push({
                  id: createMessageId(),
                  role: "assistant",
                  recipe: recipeFromText,
                });
              } else {
                assistantMessages.push({
                  id: createMessageId(),
                  role: "assistant",
                  text,
                });
              }
            });
          setMessages(assistantMessages);
        }
        setIsSessionActive(true);
      } catch (error) {
        console.error("Greeting failed:", error);
        if (!cancelled) {
          setSessionError("Failed to load the conversation. Please try again later.");
          setIsSessionActive(false);
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    };

    initializeChat();

    return () => {
      cancelled = true;
      if (redirectTimer) {
        window.clearTimeout(redirectTimer);
      }
    };
  }, [router]);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault(); // Prevent the form from reloading the page
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
    setRecipe(null); // Clear the previous recipe from the UI
    setIsLoading(true);

    try {
      const response = await sendMessage(trimmed);
      const assistantEntries: AssistantMessageInput[] = [];

      // Step 1: collect assistant messages and attempt to parse any embedded recipes
      if (Array.isArray(response.messages)) {
        response.messages.forEach((msg: any) => {
          const text = String(msg?.text ?? "").trim();
          if (text) {
            const recipeFromText = parseRecipeText(text);
            if (recipeFromText) {
              assistantEntries.push({ recipe: recipeFromText });
            } else {
              assistantEntries.push({ text });
            }
          }
        });
      }

      // Step 2: pull the structured recipe for card rendering
      const recipePayload = extractRecipeFromResponse(response);
      if (recipePayload) {
        setRecipe(recipePayload); // update the recipe panel on the right
        const alreadyHasRecipeCard = assistantEntries.some((entry) => Boolean(entry.recipe));
        if (!alreadyHasRecipeCard) {
          assistantEntries.push({ recipe: recipePayload });
        }
      }

      // Step 3: fall back to the raw result message when nothing else is available
      if (assistantEntries.length === 0) {
        const fallbackText = String(response?.result?.message ?? "").trim();
        if (fallbackText) {
          assistantEntries.push({ text: fallbackText });
        }
      }

      // Step 4: append everything to the chat log
      appendAssistantMessages(assistantEntries);

      if (response.finished) {
        // Await reinitialization to prevent race conditions with loading state
        await reinitializeSession(); 
        return; // Exit early as reinitializeSession handles the final state
      }
    } catch (error) {
      console.error("Sending message failed:", error);
      setMessages((prev) => [
        ...prev,
        {
          id: createMessageId(),
          role: "assistant",
          text: "Sorry, I ran into a problem sending your message. Please try again later.",
        },
      ]);
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
            AI Recipes for User: {userId ?? "-"}
          </h1>
          <p className="mt-3 max-w-2xl text-base text-slate-600">
            Tell me the ingredients you have.
          </p>
          {sessionError ? (
            <p className="mt-2 text-sm text-red-500" aria-live="assertive">
              {sessionError}
            </p>
          ) : null}
        </div>
      </header>

      <div className="grid gap-6 xl:grid-cols-[2fr,1fr]">
        <div className="flex h-[520px] flex-col rounded-3xl px-2 py-4 sm:h-[540px] sm:px-4 sm:py-6">
          <div className="flex-1 overflow-y-auto rounded-2xl px-2 py-4 scrollbar-hide sm:px-3">
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
                    <UserBubble key={message.id} message={message} />
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
                placeholder="Type the dish you are craving"
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

        <div className="flex h-full flex-col gap-6">
          <RecipeChecklist recipe={recipe} isLoading={isLoading} />
          <InsightsPanel />
        </div>
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

function UserBubble({ message }: { message: Extract<Message, { role: "user" }> }) {
  return (
    <div className="flex justify-end">
      <div className="w-full max-w-[820px] rounded-3xl bg-[#f2f5fb] px-6 py-4 text-sm text-slate-700 sm:mr-4">
        {message.text}
      </div>
    </div>
  );
}

function AssistantBubble({ message }: { message: Extract<Message, { role: "assistant" }> }) {
  const recipe = message.recipe ?? parseRecipeText(message.text ?? "");
  const hasRecipe = Boolean(recipe);
  const sanitizedText = (message.text ?? "").trim();
  const isLikelyJson = sanitizedText.startsWith("{") || sanitizedText.startsWith("[");
  const displayText = sanitizedText.length > 0 && (!hasRecipe || !isLikelyJson);

  return (
    <div className="flex justify-start">
      <div className="w-full max-w-[820px] rounded-3xl border border-white/60 bg-white px-6 py-6 shadow-[8px_8px_18px_rgba(209,217,230,0.35),_-8px_-8px_18px_rgba(255,255,255,0.9)] sm:ml-4">
        <span className="text-xs uppercase tracking-normal text-emerald-500">
          Suggestion
        </span>
        {displayText ? (
          <p className="mt-3 whitespace-pre-wrap text-sm leading-6 text-slate-600">
            {sanitizedText}
          </p>
        ) : null}
        {hasRecipe && recipe ? (
          <RecipeResponseCards recipe={recipe} />
        ) : null}
      </div>
    </div>
  );
}

function RecipeResponseCards({ recipe }: { recipe: RecipePayload }) {
  const { title, ingredients, steps } = recipe;
  const showTitle = Boolean(title && title.trim().length > 0);
  const hasIngredients = ingredients.length > 0;
  const hasSteps = steps.length > 0;

  return (
    <div className="mt-5 space-y-4">
      {showTitle ? (
        <h3 className="text-lg font-semibold text-slate-900">{title}</h3>
      ) : null}
      <div className="grid gap-4 md:grid-cols-2">
        <Card className="h-full rounded-2xl border border-slate-100 bg-[#f7f9fd] px-5 py-5 shadow-[6px_6px_12px_rgba(209,217,230,0.35),_-6px_-6px_12px_rgba(255,255,255,0.9)]">
          <CardHeader className="p-0">
            <CardTitle className="text-sm font-semibold uppercase tracking-normal text-slate-600">
              Ingredients
            </CardTitle>
          </CardHeader>
          <CardContent className="mt-4 space-y-3 p-0">
            {hasIngredients ? (
              <ul className="space-y-2 text-sm text-slate-600">
                {ingredients.map((ingredient, index) => (
                  <li key={`${ingredient.name}-${index}`} className="flex items-start gap-2">
                    <span className="mt-2 h-2 w-2 rounded-full bg-emerald-400" />
                    <span className="flex-1 leading-6">
                      <span className="font-medium text-slate-700">{ingredient.name}</span>
                      {ingredient.amount ? <span> — {ingredient.amount}</span> : null}
                      {ingredient.notes ? (
                        <span className="text-slate-500"> ({ingredient.notes})</span>
                      ) : null}
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-slate-500">No ingredients provided.</p>
            )}
          </CardContent>
        </Card>
        <Card className="h-full rounded-2xl border border-slate-100 bg-[#f7f9fd] px-5 py-5 shadow-[6px_6px_12px_rgba(209,217,230,0.35),_-6px_-6px_12px_rgba(255,255,255,0.9)]">
          <CardHeader className="p-0">
            <CardTitle className="text-sm font-semibold uppercase tracking-normal text-slate-600">
              Steps
            </CardTitle>
          </CardHeader>
          <CardContent className="mt-4 space-y-3 p-0">
            {hasSteps ? (
              <ol className="space-y-3 text-sm text-slate-600">
                {steps.map((step, index) => (
                  <li key={`step-${index}`} className="flex gap-3 leading-6">
                    <span className="mt-1 inline-flex h-6 w-6 flex-none items-center justify-center rounded-full bg-emerald-500/10 text-xs font-semibold text-emerald-600">
                      {index + 1}
                    </span>
                    <span className="flex-1">{step}</span>
                  </li>
                ))}
              </ol>
            ) : (
              <p className="text-sm text-slate-500">No steps provided.</p>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function RecipeChecklist({
  recipe,
  isLoading
}: {
  recipe: RecipePayload | null;
  isLoading: boolean;
}) {
  const [ingredientChecks, setIngredientChecks] = useState<Record<number, boolean>>({});
  const [stepChecks, setStepChecks] = useState<Record<number, boolean>>({});

  // This effect now only resets the checklist when a new recipe is provided,
  // ignoring the intermediate null state. This preserves the user's checked items
  // until a new recipe is actually generated.
  useEffect(() => {
    if (recipe) {
      setIngredientChecks({});
      setStepChecks({});
    }
  }, [recipe]);
  
  const handleIngredientChange = (index: number, checked: boolean) => {
    setIngredientChecks((prev) => ({
      ...prev,
      [index]: checked,
    }));
  };

  const handleStepChange = (index: number, checked: boolean) => {
    setStepChecks((prev) => ({
      ...prev,
      [index]: checked,
    }));
  };

  if (!recipe) {
    return (
      <Card className="neu-surface rounded-3xl border-0 px-6 py-8">
        <CardHeader className="space-y-2 p-0">
          <CardTitle className="text-lg font-semibold text-slate-900">
            AI Recipes
          </CardTitle>
          <CardDescription className="text-sm text-slate-500">
            {isLoading
              ? "Generating a recipe..."
              : "Share ingredients and I will build a low-GI recipe for you."}
          </CardDescription>
        </CardHeader>
      </Card>
    );
  }

  const renderIngredients = () => {
    if (recipe.ingredients.length === 0) {
      return <p className="text-sm text-slate-500">No ingredients provided.</p>;
    }

    return recipe.ingredients.map((ingredient, index) => {
      const id = `ingredient-${index}`;
      const checked = Boolean(ingredientChecks[index]);
      const amountText = ingredient.amount ? ` — ${ingredient.amount}` : "";
      const notesText = ingredient.notes ? ` (${ingredient.notes})` : "";

      return (
        <div key={id} className="flex items-start gap-3">
          <input
            type="checkbox"
            id={id}
            checked={checked}
            onChange={(event) => handleIngredientChange(index, event.target.checked)}
            className="mt-0.5 h-5 w-5 rounded-md border-gray-300 text-emerald-600 focus:ring-emerald-500"
          />
          <label
            htmlFor={id}
            className={`cursor-pointer text-sm leading-6 text-slate-700 transition-colors ${checked ? "line-through text-slate-400" : ""
              }`}
          >
            <span className="font-medium">{ingredient.name}</span>
            {amountText}
            {notesText}
          </label>
        </div>
      );
    });
  };

  const renderSteps = () => {
    if (recipe.steps.length === 0) {
      return <p className="text-sm text-slate-500">No cooking steps provided.</p>;
    }

    return recipe.steps.map((step, index) => {
      const id = `step-${index}`;
      const checked = Boolean(stepChecks[index]);
      return (
        <div key={id} className="flex items-start gap-3">
          <input
            type="checkbox"
            id={id}
            checked={checked}
            onChange={(event) => handleStepChange(index, event.target.checked)}
            className="mt-0.5 h-5 w-5 rounded-md border-gray-300 text-emerald-600 focus:ring-emerald-500"
          />
          <label
            htmlFor={id}
            className={`cursor-pointer text-sm leading-6 text-slate-700 transition-colors ${checked ? "line-through text-slate-400" : ""
              }`}
          >
            {`${index + 1}. ${step}`}
          </label>
        </div>
      );
    });
  };

  return (
    <Card className="neu-surface rounded-3xl border-0 px-6 py-8">
      <CardHeader className="space-y-2 p-0">
        <CardTitle className="text-lg font-semibold text-slate-900">
          {recipe.title}
        </CardTitle>
        <CardDescription className="text-sm text-slate-500">
          Use the checklist to track prepared ingredients and steps.
        </CardDescription>
      </CardHeader>
      <CardContent className="mt-6 space-y-6 p-0">
        <div className="space-y-3">
          <h3 className="text-xs font-semibold uppercase tracking-normal text-slate-500">
            Ingredients
          </h3>
          <div className="space-y-3">{renderIngredients()}</div>
        </div>
        <div className="space-y-3">
          <h3 className="text-xs font-semibold uppercase tracking-normal text-slate-500">
            Steps
          </h3>
          <div className="space-y-3">{renderSteps()}</div>
        </div>
      </CardContent>
    </Card>
  );
}

function InsightsPanel() {
  return (
    <>
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
    </>
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

function extractRecipeFromResponse(response: any): RecipePayload | null {
  // Priority 1: Attempt to normalize the direct `recipe` object from the response.
  // This handles cases where the backend provides a clean, structured object.
  const directRecipe = normalizeRecipePayload(response?.result?.recipe);
  if (directRecipe) {
    return directRecipe;
  }

  // Priority 2: If the direct object is missing or malformed, try parsing from text.
  // This handles fallbacks where the recipe is embedded in a string.
  const text = response?.result?.recipe?.steps?.[0] ?? response?.result?.message;
  const parsedFromText = parseRecipeText(text);
  if (parsedFromText) {
    return parsedFromText;
  }
  return null;
}

function normalizeRecipePayload(raw: any): RecipePayload | null {
  if (!raw || typeof raw !== "object") {
    return null;
  }

  const titleSource =
    (typeof raw.title === "string" && raw.title.trim()) ||
    (typeof raw.food_name === "string" && raw.food_name.trim()) ||
    (typeof raw.name === "string" && raw.name.trim()) ||
    null;

  const ingredientsRaw = Array.isArray(raw.ingredients) ? raw.ingredients : [];
  const ingredients: RecipeIngredient[] = ingredientsRaw
    .map((item: any) => {
      if (item && typeof item === "object") {
        const name = typeof item.name === "string" ? item.name.trim() : "";
        if (!name) {
          return null;
        }
        const amount =
          item.amount != null
            ? String(item.amount).trim()
            : "";
        const notes =
          item.notes != null && item.notes !== ""
            ? String(item.notes).trim()
            : null;
        return {
          name,
          amount,
          notes,
        };
      }
      if (typeof item === "string") {
        const value = item.trim();
        if (!value) {
          return null;
        }
        return {
          name: value,
          amount: "",
          notes: null,
        };
      }
      return null;
    })
    .filter((item): item is RecipeIngredient => Boolean(item));

  const stepsSource = Array.isArray(raw.steps)
    ? raw.steps
    : Array.isArray(raw.instructions)
      ? raw.instructions
      : [];
  const steps: string[] = stepsSource
    .map((entry: any) => {
      if (typeof entry === "string") {
        return entry.trim();
      }
      if (entry && typeof entry === "object") {
        const candidate =
          entry.instruction ??
          entry.text ??
          entry.step ??
          entry.description ??
          entry.title;
        if (typeof candidate === "string") {
          return candidate.trim();
        }
      }
      return "";
    })
    .filter((value: string) => value.length > 0);

  if (!titleSource && ingredients.length === 0 && steps.length === 0) {
    return null;
  }

  return {
    title: titleSource ?? "Recipe",
    ingredients,
    steps,
  };
}

function parseRecipeText(rawText: unknown): RecipePayload | null {
  if (typeof rawText !== "string") {
    return null;
  }

  // Find the start of a JSON object, robustly handling surrounding text.
  const firstBraceIndex = rawText.indexOf("{");
  if (firstBraceIndex === -1) {
    return null;
  }

  // Find the matching closing brace to isolate the JSON object.
  let depth = 0;
  let endIndex = -1;
  for (let i = firstBraceIndex; i < rawText.length; i++) {
    const char = rawText[i];
    if (char === "{") {
      depth += 1;
    } else if (char === "}") {
      depth -= 1;
      if (depth === 0) {
        endIndex = i;
        break;
      }
    }
  }

  if (endIndex === -1) {
    return null;
  }

  // Extract and clean the object literal to make it valid JSON.
  const objectLiteral = rawText.slice(firstBraceIndex, endIndex + 1);
  let normalized = objectLiteral.replace(
    /([{\s,])([A-Za-z_][\w]*)\s*:/g,
    '$1"$2":'
  );
  normalized = normalized.replace(/'([^']*)'/g, (_match, value) =>
    `"${String(value).replace(/"/g, '\\"')}"`
  );
  normalized = normalized.replace(/,\s*([}\]])/g, "$1");

  try {
    const parsed = JSON.parse(normalized);
    // The backend schema wraps the recipe in a "recipe" key.
    // We need to unwrap it before passing to normalizeRecipePayload.
    const unwrapped = parsed.recipe ? parsed.recipe : parsed;
    return normalizeRecipePayload(unwrapped);
  } catch {
    return null;
  }
}

function createMessageId() {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}
