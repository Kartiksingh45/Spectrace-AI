"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { AuthHeader } from "@/components/AuthHeader";
import { AuthIntroPanel } from "@/components/AuthIntroPanel";
import { api, ApiError } from "@/lib/api";
import { getLastProjectId } from "@/lib/lastProject";

function destinationAfterSignIn(): string {
  const lastProjectId = getLastProjectId();
  return lastProjectId ? `/projects/${lastProjectId}` : "/dashboard";
}

export default function SignInPage() {
  return (
    <Suspense fallback={null}>
      <SignInContent />
    </Suspense>
  );
}

function SignInContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const justReset = searchParams.get("reset") === "1";
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    // Already signed in (e.g. opened the app fresh with a live session)? Skip the form and go
    // straight back to whatever project was last open, rather than making them log in again.
    api.getCurrentUser().then(() => router.replace(destinationAfterSignIn())).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await api.login(email, password);
      router.push(destinationAfterSignIn());
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="min-h-screen bg-background">
      <AuthHeader />
      <div className="auth-background flex flex-col lg:flex-row">
      <AuthIntroPanel />
      <div className="flex flex-1 items-center justify-center px-4 py-16">
        <div className="w-full max-w-sm flex flex-col gap-6 rounded-xl border border-ink/10 bg-background p-8 shadow-lg">
          <div>
            <h1 className="font-serif text-2xl font-semibold text-ink">Sign in</h1>
            <p className="mt-1 text-sm text-ink/60">Access your Spectrace AI projects.</p>
          </div>
          {justReset && (
            <p className="rounded-md bg-emerald-50 px-3 py-2 text-sm text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-300">
              Password reset - sign in with your new password.
            </p>
          )}
          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <label className="flex flex-col gap-1 text-sm">
              Email
              <input
                id="email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="rounded-md border border-ink/15 bg-surface px-3 py-2 outline-none focus:border-trace"
              />
            </label>
            <label className="flex flex-col gap-1 text-sm">
              <div className="flex items-center justify-between">
                Password
                <Link href="/forgot-password" className="text-xs font-medium text-trace">
                  Forgot password?
                </Link>
              </div>
              <input
                id="password"
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="rounded-md border border-ink/15 bg-surface px-3 py-2 outline-none focus:border-trace"
              />
            </label>
            {error && <p className="text-sm text-red-700">{error}</p>}
            <button
              type="submit"
              disabled={submitting}
              className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
            >
              {submitting ? "Signing in…" : "Sign in"}
            </button>
          </form>
          <p className="text-sm text-ink/60">
            No account yet?{" "}
            <Link href="/register" className="font-medium text-trace">
              Register
            </Link>
          </p>
        </div>
      </div>
      </div>
    </main>
  );
}
