"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { AuthIntroPanel } from "@/components/AuthIntroPanel";
import { api, ApiError } from "@/lib/api";

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={null}>
      <ResetPasswordContent />
    </Suspense>
  );
}

function ResetPasswordContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = searchParams.get("token") ?? "";

  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (password !== confirmPassword) {
      setError("Those passwords don't match.");
      return;
    }
    setSubmitting(true);
    try {
      await api.resetPassword(token, password);
      router.push("/sign-in?reset=1");
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Could not reset your password. Try again."
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="auth-background flex min-h-screen flex-col lg:flex-row">
      <AuthIntroPanel />
      <div className="flex flex-1 items-center justify-center px-4 py-16">
        <div className="w-full max-w-sm flex flex-col gap-6 rounded-xl border border-ink/10 bg-background p-8 shadow-lg">
          <div>
            <h1 className="font-serif text-2xl font-semibold text-ink">Reset password</h1>
            <p className="mt-1 text-sm text-ink/60">Choose a new password for your account.</p>
          </div>

          {!token ? (
            <p className="text-sm text-red-700">
              This reset link is missing its token. Request a new one from the{" "}
              <Link href="/forgot-password" className="font-medium text-trace">
                forgot password
              </Link>{" "}
              page.
            </p>
          ) : (
            <form onSubmit={handleSubmit} className="flex flex-col gap-4">
              <label className="flex flex-col gap-1 text-sm">
                New password
                <input
                  id="password"
                  type="password"
                  required
                  minLength={8}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="rounded-md border border-ink/15 bg-surface px-3 py-2 outline-none focus:border-trace"
                />
              </label>
              <label className="flex flex-col gap-1 text-sm">
                Confirm new password
                <input
                  id="confirm-password"
                  type="password"
                  required
                  minLength={8}
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  className="rounded-md border border-ink/15 bg-surface px-3 py-2 outline-none focus:border-trace"
                />
              </label>
              {error && <p className="text-sm text-red-700">{error}</p>}
              <button
                type="submit"
                disabled={submitting}
                className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
              >
                {submitting ? "Resetting…" : "Reset password"}
              </button>
            </form>
          )}

          <p className="text-sm text-ink/60">
            <Link href="/sign-in" className="font-medium text-trace">
              Back to sign in
            </Link>
          </p>
        </div>
      </div>
    </main>
  );
}
