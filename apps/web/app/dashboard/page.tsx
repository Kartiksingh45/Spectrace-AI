"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";
import { TopNav } from "@/components/TopNav";
import { api, ApiError, Project, ProjectStatus } from "@/lib/api";

const STATUS_LABEL: Record<ProjectStatus, string> = {
  draft: "Draft",
  in_progress: "In Progress",
  complete: "Complete",
};

const STATUS_STYLE: Record<ProjectStatus, string> = {
  draft: "bg-ink/10 text-ink/70",
  in_progress: "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300",
  complete: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300",
};

// A handful of distinct, deterministic avatar colors - same project always gets the same one.
const AVATAR_COLORS = ["#7c5cff", "#22c55e", "#ec4899", "#3b82f6", "#14b8a6", "#f59e0b"];

function avatarColor(id: string): string {
  let hash = 0;
  for (let i = 0; i < id.length; i++) hash = (hash * 31 + id.charCodeAt(i)) >>> 0;
  return AVATAR_COLORS[hash % AVATAR_COLORS.length];
}

function timeAgo(iso: string): string {
  const seconds = Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / 1000));
  if (seconds < 60) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes} minute${minutes === 1 ? "" : "s"} ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} hour${hours === 1 ? "" : "s"} ago`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days} day${days === 1 ? "" : "s"} ago`;
  const months = Math.floor(days / 30);
  if (months < 12) return `${months} month${months === 1 ? "" : "s"} ago`;
  const years = Math.floor(months / 12);
  return `${years} year${years === 1 ? "" : "s"} ago`;
}

function ProjectMenu({
  project,
  isOwner,
  onDelete,
}: {
  project: Project;
  isOwner: boolean;
  onDelete: (id: string) => Promise<void>;
}) {
  const [open, setOpen] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onClickOutside(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setOpen(false);
        setConfirming(false);
      }
    }
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, []);

  if (!isOwner) return null;

  return (
    <div ref={menuRef} className="relative">
      <button
        onClick={(e) => {
          e.preventDefault();
          setOpen((v) => !v);
        }}
        className="rounded-md px-1.5 py-1 text-ink/40 hover:bg-ink/5 hover:text-ink"
        aria-label="Project actions"
      >
        •••
      </button>
      {open && (
        <div className="absolute right-0 top-7 z-10 w-44 rounded-md border border-ink/10 bg-background p-1 text-xs shadow-lg">
          {confirming ? (
            <div className="flex flex-col gap-1 p-1">
              <p className="px-1 text-ink/60">Delete this project and everything in it?</p>
              <button
                onClick={async (e) => {
                  e.preventDefault();
                  setDeleting(true);
                  await onDelete(project.id);
                  setDeleting(false);
                }}
                disabled={deleting}
                className="rounded px-2 py-1 text-left font-medium text-red-700 hover:bg-red-50 disabled:opacity-60 dark:text-red-400 dark:hover:bg-red-900/20"
              >
                {deleting ? "Deleting…" : "Confirm delete"}
              </button>
              <button
                onClick={(e) => {
                  e.preventDefault();
                  setConfirming(false);
                }}
                className="rounded px-2 py-1 text-left text-ink/60 hover:bg-ink/5"
              >
                Cancel
              </button>
            </div>
          ) : (
            <button
              onClick={(e) => {
                e.preventDefault();
                setConfirming(true);
              }}
              className="w-full rounded px-2 py-1.5 text-left text-red-700 hover:bg-red-50 dark:text-red-400 dark:hover:bg-red-900/20"
            >
              Delete
            </button>
          )}
        </div>
      )}
    </div>
  );
}

export default function DashboardPage() {
  return (
    <Suspense fallback={null}>
      <DashboardContent />
    </Suspense>
  );
}

function DashboardContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [currentUserId, setCurrentUserId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [signedOut, setSignedOut] = useState(false);

  // The home page's "+ Create a project" quick action links here with ?create=1 so the form is
  // already open instead of landing on a plain list with no obvious next step.
  const [showCreateForm, setShowCreateForm] = useState(() => searchParams.get("create") === "1");
  const [newName, setNewName] = useState("");
  const [creating, setCreating] = useState(false);

  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<"all" | ProjectStatus>("all");

  useEffect(() => {
    api
      .listProjects()
      .then(setProjects)
      .catch((err) => {
        if (err instanceof ApiError && err.status === 401) {
          // Browsable without an account - only actually creating a project (below) requires
          // signing in, so this just shows an empty, signed-out-aware state instead of bouncing
          // the visitor away before they've tried to do anything.
          setSignedOut(true);
          setProjects([]);
        } else {
          setError("Could not load projects.");
        }
      });
    // Only gates the per-project delete action (owner-only) - if this fails, the project list
    // above should still render rather than being blocked by an unrelated call.
    api.getCurrentUser().then((user) => setCurrentUserId(user.id)).catch(() => {});
  }, [router]);

  async function handleDelete(projectId: string) {
    setError(null);
    try {
      await api.deleteProject(projectId);
      setProjects((prev) => prev?.filter((p) => p.id !== projectId) ?? prev);
    } catch {
      setError("Could not delete that project.");
    }
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!newName.trim()) return;
    setCreating(true);
    setError(null);
    try {
      const project = await api.createProject(newName.trim());
      setProjects((prev) => [project, ...(prev ?? [])]);
      setNewName("");
      setShowCreateForm(false);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        // The real gate: trying to actually create is what requires an account. replace(), not
        // push(), so the back button from sign-in returns straight here instead of to a redirect
        // that would otherwise just bounce forward again.
        router.replace("/sign-in");
        return;
      }
      setError("Could not create the project.");
    } finally {
      setCreating(false);
    }
  }

  const filtered = (projects ?? []).filter((p) => {
    if (statusFilter !== "all" && p.status !== statusFilter) return false;
    if (query.trim() && !p.name.toLowerCase().includes(query.trim().toLowerCase())) return false;
    return true;
  });

  return (
    <main className="mx-auto max-w-5xl px-4 py-12">
      <TopNav />

      <div className="mb-6 flex items-center justify-between gap-3">
        <h1 className="flex items-center gap-2 font-serif text-2xl font-semibold text-ink">
          Projects
          {projects && <span className="text-base font-normal text-ink/40">({projects.length})</span>}
        </h1>
        <button
          onClick={() => setShowCreateForm((v) => !v)}
          className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-white hover:opacity-90"
        >
          + New Project
        </button>
      </div>

      {showCreateForm && (
        <form onSubmit={handleCreate} className="mb-6 flex gap-2">
          <input
            id="project-name"
            autoFocus
            placeholder="New project name"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            className="flex-1 rounded-md border border-ink/15 bg-surface px-3 py-2 text-sm outline-none focus:border-trace"
          />
          <button
            type="submit"
            disabled={creating}
            className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
          >
            {creating ? "Creating…" : "Create"}
          </button>
        </form>
      )}

      <div className="mb-6 flex flex-col gap-2 sm:flex-row">
        <input
          placeholder="Search projects…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="flex-1 rounded-md border border-ink/15 bg-surface px-3 py-2 text-sm outline-none focus:border-trace"
        />
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value as "all" | ProjectStatus)}
          className="rounded-md border border-ink/15 bg-surface px-3 py-2 text-sm text-ink"
        >
          <option value="all">All statuses</option>
          <option value="draft">Draft</option>
          <option value="in_progress">In Progress</option>
          <option value="complete">Complete</option>
        </select>
      </div>

      {error && <p className="mb-4 text-sm text-red-700">{error}</p>}

      {projects === null ? (
        <p className="text-sm text-ink/60">Loading…</p>
      ) : signedOut ? (
        <p className="text-sm text-ink/60">
          <Link href="/sign-in" className="text-trace hover:underline">
            Sign in
          </Link>{" "}
          to see or create your projects.
        </p>
      ) : projects.length === 0 ? (
        <p className="text-sm text-ink/60">No projects yet. Create your first one above.</p>
      ) : filtered.length === 0 ? (
        <p className="text-sm text-ink/60">No projects match your search.</p>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {filtered.map((project) => (
            <div
              key={project.id}
              className="relative flex flex-col gap-3 rounded-lg border border-ink/10 bg-surface p-4 hover:border-trace"
            >
              <div className="flex items-start justify-between gap-2">
                <Link href={`/projects/${project.id}`} className="flex min-w-0 items-center gap-3">
                  <span
                    className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-sm font-semibold text-white"
                    style={{ backgroundColor: avatarColor(project.id) }}
                  >
                    {project.name.trim().charAt(0).toUpperCase() || "?"}
                  </span>
                  <span className="min-w-0 truncate text-sm font-medium text-ink">{project.name}</span>
                </Link>
                <ProjectMenu project={project} isOwner={project.owner_id === currentUserId} onDelete={handleDelete} />
              </div>

              <Link href={`/projects/${project.id}`} className="flex flex-col gap-1 text-xs text-ink/50">
                <span>Last edited: {timeAgo(project.updated_at)}</span>
                {project.requirement_count !== null && <span>BRD · {project.requirement_count} reqs</span>}
              </Link>

              <span className={`w-fit rounded-full px-2 py-1 text-xs font-medium ${STATUS_STYLE[project.status]}`}>
                {STATUS_LABEL[project.status]}
              </span>
            </div>
          ))}
        </div>
      )}
    </main>
  );
}
