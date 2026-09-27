"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { TopNav } from "@/components/TopNav";
import { api, ApiError, Project } from "@/lib/api";

export default function DashboardPage() {
  const router = useRouter();
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [currentUserId, setCurrentUserId] = useState<string | null>(null);
  const [newName, setNewName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [confirmingId, setConfirmingId] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.listProjects(), api.getCurrentUser()])
      .then(([projectList, user]) => {
        setProjects(projectList);
        setCurrentUserId(user.id);
      })
      .catch((err) => {
        if (err instanceof ApiError && err.status === 401) {
          router.push("/sign-in");
        } else {
          setError("Could not load projects.");
        }
      });
  }, [router]);

  async function handleDelete(projectId: string) {
    setDeletingId(projectId);
    setError(null);
    try {
      await api.deleteProject(projectId);
      setProjects((prev) => prev?.filter((p) => p.id !== projectId) ?? prev);
    } catch {
      setError("Could not delete that project.");
    } finally {
      setDeletingId(null);
      setConfirmingId(null);
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
    } catch {
      setError("Could not create the project.");
    } finally {
      setCreating(false);
    }
  }

  return (
    <main className="mx-auto max-w-2xl px-4 py-12">
      <TopNav />
      <h1 className="mb-8 font-serif text-2xl font-semibold text-ink">Projects</h1>

      <form onSubmit={handleCreate} className="mb-8 flex gap-2">
        <input
          id="project-name"
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
          Create
        </button>
      </form>

      {error && <p className="mb-4 text-sm text-red-700">{error}</p>}

      {projects === null ? (
        <p className="text-sm text-ink/60">Loading…</p>
      ) : projects.length === 0 ? (
        <p className="text-sm text-ink/60">No projects yet. Create your first one above.</p>
      ) : (
        <ul className="flex flex-col gap-2">
          {projects.map((project) => (
            <li
              key={project.id}
              className="flex items-center gap-3 rounded-md border border-ink/10 bg-surface px-4 py-3 text-sm hover:border-trace"
            >
              <Link href={`/projects/${project.id}`} className="flex-1 text-ink">
                {project.name}
              </Link>
              {project.owner_id === currentUserId &&
                (confirmingId === project.id ? (
                  <span className="flex shrink-0 items-center gap-2 text-xs">
                    <span className="text-ink/60">Delete this project and everything in it?</span>
                    <button
                      onClick={() => handleDelete(project.id)}
                      disabled={deletingId === project.id}
                      className="font-medium text-red-700 hover:underline disabled:opacity-60 dark:text-red-400"
                    >
                      {deletingId === project.id ? "Deleting…" : "Confirm"}
                    </button>
                    <button
                      onClick={() => setConfirmingId(null)}
                      disabled={deletingId === project.id}
                      className="text-ink/50 hover:text-ink"
                    >
                      Cancel
                    </button>
                  </span>
                ) : (
                  <button
                    onClick={() => setConfirmingId(project.id)}
                    className="shrink-0 text-xs text-ink/50 hover:text-red-700"
                  >
                    Delete
                  </button>
                ))}
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
