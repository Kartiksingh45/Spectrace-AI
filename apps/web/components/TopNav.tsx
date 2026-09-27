"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { clearLastProjectId, getLastProjectId } from "@/lib/lastProject";
import { applyTheme, getStoredThemePreference, setStoredThemePreference, type ThemePreference } from "@/lib/theme";
import { Logo } from "@/components/Logo";

const THEME_CYCLE: ThemePreference[] = ["system", "light", "dark"];
const THEME_LABEL: Record<ThemePreference, string> = {
  system: "Theme: Auto",
  light: "Theme: Light",
  dark: "Theme: Dark",
};

function ThemeToggle() {
  const [pref, setPref] = useState<ThemePreference>("system");

  useEffect(() => {
    setPref(getStoredThemePreference());
  }, []);

  function cycleTheme() {
    const next = THEME_CYCLE[(THEME_CYCLE.indexOf(pref) + 1) % THEME_CYCLE.length];
    setPref(next);
    setStoredThemePreference(next);
    applyTheme(next);
  }

  return (
    <button onClick={cycleTheme} className="text-ink/60 hover:text-ink">
      {THEME_LABEL[pref]}
    </button>
  );
}

export function TopNav() {
  const router = useRouter();
  // BRD generation is project-scoped - send the user back into whichever project they were last
  // working in rather than requiring the link to already be inside a /projects/[id] route.
  const [brdHref, setBrdHref] = useState("/dashboard");

  useEffect(() => {
    const lastProjectId = getLastProjectId();
    if (lastProjectId) {
      setBrdHref(`/projects/${lastProjectId}/brd`);
      return;
    }
    // Nothing in storage yet (e.g. a fresh browser/session that hasn't opened a specific
    // project) - fall back to the user's most recent project instead of a dead link to
    // /dashboard, which does nothing when clicked from the dashboard itself.
    api
      .listProjects()
      .then((projects) => {
        if (projects[0]) setBrdHref(`/projects/${projects[0].id}/brd`);
      })
      .catch(() => {});
  }, []);

  async function handleSignOut() {
    clearLastProjectId();
    await api.logout();
    router.push("/sign-in");
  }

  return (
    <nav className="mb-8 flex items-center justify-between border-b border-ink/10 pb-4 text-sm">
      <div className="flex items-center gap-5">
        <Link href="/dashboard">
          <Logo />
        </Link>
        <Link href="/dashboard" className="text-ink/60 hover:text-ink">
          Projects
        </Link>
        <Link href="/guide" className="text-ink/60 hover:text-ink">
          Guide
        </Link>
        <Link href={brdHref} className="text-ink/60 hover:text-ink">
          BRD generator
        </Link>
        <Link href="/profile" className="text-ink/60 hover:text-ink">
          My Profile
        </Link>
      </div>
      <div className="flex items-center gap-5">
        <ThemeToggle />
        <button onClick={handleSignOut} className="text-ink/60 hover:text-ink">
          Sign out
        </button>
      </div>
    </nav>
  );
}
