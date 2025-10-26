'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { login } from '@/lib/api';

export default function LoginPage() {
  const [userId, setUserId] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const router = useRouter();

  const openDialog = useCallback(() => {
    setError('');
    setIsDialogOpen(true);
  }, []);

  const closeDialog = useCallback(() => {
    setIsDialogOpen(false);
    setError('');
  }, []);

  useEffect(() => {
    if (!isDialogOpen) {
      return;
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        closeDialog();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isDialogOpen, closeDialog]);

  const initials = useMemo(() => {
    return userId ? userId.slice(0, 2).toUpperCase() : 'GS';
  }, [userId]);

  const submitLogin = async (id: string) => {
    setError('');
    setIsLoading(true);

    const trimmedId = id.trim();
    if (!trimmedId) {
      setError('User ID cannot be empty.');
      setIsLoading(false);
      return;
    }

    try {
      const response = await login(trimmedId);
      if (response.ok) {
        closeDialog();
        router.push(`/chat?userId=${trimmedId}`);
      } else {
        setError(response.error || 'An unknown error occurred.');
      }
    } catch (err: any) {
      setError(err.message || 'Failed to connect to the server.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleLogin = async (event: React.FormEvent) => {
    event.preventDefault();
    await submitLogin(userId);
  };

  return (
    <section className="relative flex min-h-[60vh] flex-col justify-center overflow-hidden rounded-[28px] bg-gradient-to-br from-[#f0f6ff] via-[#f6fbf7] to-[#fefefe] px-6 py-12 sm:px-12 sm:py-16">
      <div className="absolute right-6 top-6 flex items-center gap-3 sm:right-10 sm:top-10">
        <div className="flex h-12 w-12 items-center justify-center rounded-full border border-white/60 bg-white/80 text-sm font-semibold text-emerald-600 shadow-[6px_6px_14px_rgba(208,219,235,0.6),_-6px_-6px_14px_rgba(255,255,255,0.8)]">
          {initials}
        </div>
        <Button
          onClick={openDialog}
          className="rounded-full bg-emerald-600 px-6 py-2 text-sm font-semibold shadow-lg shadow-emerald-200/50 hover:bg-emerald-700"
        >
          Sign in
        </Button>
      </div>

      <div className="relative mx-auto max-w-2xl text-center">
        <div className="mx-auto mb-6 flex h-12 w-12 items-center justify-center rounded-full bg-white/80 text-xs uppercase tracking-wider text-emerald-500 shadow-[8px_8px_16px_rgba(209,217,230,0.55),_-8px_-8px_16px_rgba(255,255,255,0.9)]">
          Welcome
        </div>
        <h1 className="text-4xl font-semibold text-slate-900 sm:text-5xl">
          Sign in to unlock AI-powered meal planning
        </h1>
        <p className="mt-4 text-base text-slate-600 sm:text-lg">
          Enter the numeric user ID provided by the backend team to resume your personalised assistant session (for example, try 101).
        </p>
      </div>

      {isDialogOpen ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 px-4 py-6 backdrop-blur-sm"
          onClick={closeDialog}
        >
          <div
            role="dialog"
            aria-modal="true"
            className="w-full max-w-md rounded-[26px] border border-white/40 bg-white shadow-[12px_18px_40px_rgba(15,35,95,0.18)]"
            onClick={(event) => event.stopPropagation()}
          >
            <Card className="border-0 shadow-none">
              <CardHeader className="flex flex-row items-start justify-between gap-4">
                <div>
                  <CardTitle className="text-xl font-semibold text-slate-900">
                    Sign in to continue
                  </CardTitle>
                  <CardDescription className="mt-1 text-sm text-slate-500">
                    Provide the numeric user ID issued by the backend.
                  </CardDescription>
                </div>
                <button
                  type="button"
                  onClick={closeDialog}
                  className="rounded-full bg-[#f1f4fa] px-3 py-1 text-xs font-semibold uppercase tracking-wide text-slate-500 transition hover:text-slate-700"
                >
                  Close
                </button>
              </CardHeader>
              <CardContent className="space-y-6">
                <form onSubmit={handleLogin} className="space-y-4">
                  <div className="space-y-2">
                    <label htmlFor="user-id" className="text-sm font-medium text-slate-600">
                      Enter your user ID
                    </label>
                    <Input
                      id="user-id"
                      placeholder="Numeric user ID"
                      value={userId}
                      onChange={(event) => setUserId(event.target.value)}
                      disabled={isLoading}
                      className="h-12 rounded-xl border-0 bg-[#edf1f9] text-sm shadow-[inset_6px_6px_12px_rgba(209,217,230,0.6),inset_-6px_-6px_12px_rgba(255,255,255,0.9)] focus-visible:ring-2 focus-visible:ring-emerald-500"
                    />
                  </div>
                  <Button
                    type="submit"
                    disabled={isLoading}
                    className="w-full rounded-full bg-emerald-600 py-3 text-sm font-semibold shadow-lg shadow-emerald-200/50 hover:bg-emerald-700 disabled:bg-emerald-400"
                  >
                    {isLoading ? 'Signing in...' : 'Continue'}
                  </Button>
                </form>

                <p className="text-center text-xs text-slate-400">
                  Need a test account? Try logging in with 101, 102, or 103.
                </p>

                {error ? (
                  <p className="text-center text-sm text-red-500">{error}</p>
                ) : null}
              </CardContent>
            </Card>
          </div>
        </div>
      ) : null}
    </section>
  );
}
