"use client";

import Link from "next/link";
import { useState } from "react";
import { AuthIntroPanel } from "@/components/AuthIntroPanel";
import { api } from "@/lib/api";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [sent, setSent] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    try {
      await api.forgotPassword(email);
    } catch {
      // Deliberately ignored: the backend always responds the same way whether or not the email
      // is registered, so there is nothing different to show on failure here either - a
      // network/server error still gets the same generic message, never a signal either way.
    } finally {
      setSubmitting(false);
      setSent(true);
    }
  }

  return (
    <main className="auth-background flex min-h-screen flex-col lg:flex-row">
      <AuthIntroPanel />
      <div className="flex flex-1 items-center justify-center px-4 py-16">
        <div className="w-full max-w-sm flex flex-col gap-6 rounded-xl border border-ink/10 bg-background p-8 shadow-lg">
          <div>
            <h1 className="font-serif text-2xl font-semibold text-ink">Forgot password</h1>
            <p className="mt-1 text-sm text-ink/60">
              Enter your account email and we&apos;ll send you a link to reset your password.
            </p>
          </div>

          {sent ? (
            <p className="text-sm text-ink/80">
              If an account exists for that email, a reset link is on its way. Check your inbox
              (and spam folder) - the link expires in 30 minutes.
            </p>
          ) : (
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
              <button
                type="submit"
                disabled={submitting}
                className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
              >
                {submitting ? "Sending…" : "Send reset link"}
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
