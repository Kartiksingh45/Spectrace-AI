export type ThemePreference = "light" | "dark" | "system";

const KEY = "spectrace:theme";

export function getStoredThemePreference(): ThemePreference {
  try {
    const value = localStorage.getItem(KEY);
    if (value === "light" || value === "dark" || value === "system") return value;
  } catch {
    // ignore - falls through to the default below
  }
  return "system";
}

export function setStoredThemePreference(pref: ThemePreference): void {
  try {
    localStorage.setItem(KEY, pref);
  } catch {
    // ignore
  }
}

function systemPrefersDark(): boolean {
  return typeof window !== "undefined" && window.matchMedia("(prefers-color-scheme: dark)").matches;
}

/** Applies a theme preference to the document immediately (also called by the blocking inline
 * script in layout.tsx before first paint, to avoid a flash of the wrong theme). */
export function applyTheme(pref: ThemePreference): void {
  const isDark = pref === "dark" || (pref === "system" && systemPrefersDark());
  document.documentElement.classList.toggle("dark", isDark);
}
