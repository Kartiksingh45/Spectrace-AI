"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { getLastProjectId } from "@/lib/lastProject";

/** BRD generation is project-scoped - resolves to whichever project the user was last working
 * in, falling back to their most recent project if nothing's tracked yet (e.g. a fresh
 * browser/session that never opened a specific project page). Falls back to /dashboard only if
 * the user has no projects at all. */
export function useBrdHref(): string {
  const [href, setHref] = useState("/dashboard");

  useEffect(() => {
    const lastProjectId = getLastProjectId();
    if (lastProjectId) {
      setHref(`/projects/${lastProjectId}/brd`);
      return;
    }
    api
      .listProjects()
      .then((projects) => {
        if (projects[0]) setHref(`/projects/${projects[0].id}/brd`);
      })
      .catch(() => {});
  }, []);

  return href;
}
