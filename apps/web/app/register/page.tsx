"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { AuthHeader } from "@/components/AuthHeader";
import { AuthIntroPanel } from "@/components/AuthIntroPanel";
import { api, ApiError } from "@/lib/api";

export default function RegisterPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await api.register(email, password);
      router.push("/dashboard");
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
            <h1 className="font-serif text-2xl font-semibold text-ink">Create your account</h1>
            <p className="mt-1 text-sm text-ink/60">Start a project and upload requirements or code.</p>
          </div>
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
              Password
              <input
                id="password"
                type="password"
                required
                minLength={8}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="rounded-md border border-ink/15 bg-surface px-3 py-2 outline-none focus:border-trace"
              />
              <span className="text-xs text-ink/50">At least 8 characters.</span>
            </label>
            {error && <p className="text-sm text-red-700">{error}</p>}
            <button
              type="submit"
              disabled={submitting}
              className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
            >
              {submitting ? "Creating account…" : "Create account"}
            </button>
          </form>
          <p className="text-sm text-ink/60">
            Already have an account?{" "}
            <Link href="/sign-in" className="font-medium text-trace">
              Sign in
            </Link>
          </p>
        </div>
      </div>
      </div>
    </main>
  );
}
