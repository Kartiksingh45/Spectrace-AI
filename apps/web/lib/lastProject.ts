const KEY = "spectrace:lastProjectId";

/** Remembers which project a user was last working in (per browser) so opening the app can
 * drop them straight back into it instead of a bare project list. Wrapped in try/catch since
 * localStorage can throw (private browsing, disabled storage, etc.) and this is a convenience,
 * not something correctness depends on. */
export function getLastProjectId(): string | null {
  try {
    return localStorage.getItem(KEY);
  } catch {
    return null;
  }
}

export function setLastProjectId(projectId: string): void {
  try {
    localStorage.setItem(KEY, projectId);
  } catch {
    // ignore
  }
}

export function clearLastProjectId(): void {
  try {
    localStorage.removeItem(KEY);
  } catch {
    // ignore
  }
}
