"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { TopNav } from "@/components/TopNav";
import { api, ApiError, User } from "@/lib/api";

const ROLE_LABEL: Record<User["role"], string> = {
  contributor: "Contributor",
  reviewer: "Reviewer",
  administrator: "Administrator",
};

export default function ProfilePage() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  useEffect(() => {
    api
      .getCurrentUser()
      .then(setUser)
      .catch((err) => {
        if (err instanceof ApiError && err.status === 401) {
          router.replace("/sign-in");
        } else {
          setLoadError("Could not load your profile.");
        }
      });
  }, [router]);

  async function handleChangePassword(e: React.FormEvent) {
    e.preventDefault();
    setFormError(null);
    setSuccess(false);
    if (newPassword !== confirmPassword) {
      setFormError("New password and confirmation don't match.");
      return;
    }
    setSubmitting(true);
    try {
      await api.changePassword(currentPassword, newPassword);
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      setSuccess(true);
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : "Could not change your password.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="mx-auto max-w-5xl px-4 py-12">
      <TopNav />
      <div className="mx-auto max-w-2xl">
        <h1 className="mb-8 font-serif text-2xl font-semibold text-ink">My Profile</h1>

        {loadError && <p className="text-sm text-red-700">{loadError}</p>}

        {user && (
          <section className="mb-10 rounded-lg border border-ink/10 bg-surface p-5 shadow-sm">
            <div className="mb-3 h-1.5 w-8 rounded-full bg-trace" />
            <dl className="flex flex-col gap-3 text-sm">
              <div>
                <dt className="text-xs font-medium uppercase tracking-wide text-ink/50">Email</dt>
                <dd className="text-ink">{user.email}</dd>
              </div>
              <div>
                <dt className="text-xs font-medium uppercase tracking-wide text-ink/50">Role</dt>
                <dd className="text-ink">{ROLE_LABEL[user.role]}</dd>
              </div>
              <div>
                <dt className="text-xs font-medium uppercase tracking-wide text-ink/50">Member since</dt>
                <dd className="text-ink">{new Date(user.created_at).toLocaleDateString()}</dd>
              </div>
            </dl>
          </section>
        )}

        <section>
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-ink/50">
            Change password
          </h2>
          <form onSubmit={handleChangePassword} className="flex flex-col gap-3 rounded-lg border border-ink/10 bg-surface p-5 shadow-sm">
            <div className="-mt-1 mb-1 h-1.5 w-8 rounded-full bg-trace" />
            <label className="flex flex-col gap-1 text-sm">
              Current password
              <input
                type="password"
                required
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                className="rounded-md border border-ink/15 px-3 py-2 outline-none focus:border-trace"
              />
            </label>
            <label className="flex flex-col gap-1 text-sm">
              New password
              <input
                type="password"
                required
                minLength={8}
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                className="rounded-md border border-ink/15 px-3 py-2 outline-none focus:border-trace"
              />
            </label>
            <label className="flex flex-col gap-1 text-sm">
              Confirm new password
              <input
                type="password"
                required
                minLength={8}
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                className="rounded-md border border-ink/15 px-3 py-2 outline-none focus:border-trace"
              />
            </label>
            {formError && <p className="text-sm text-red-700">{formError}</p>}
            {success && <p className="text-sm text-emerald-700">Password changed.</p>}
            <button
              type="submit"
              disabled={submitting}
              className="self-start rounded-md bg-accent px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
            >
              {submitting ? "Saving…" : "Change password"}
            </button>
          </form>
        </section>
      </div>
    </main>
  );
}
