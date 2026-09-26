"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { TopNav } from "@/components/TopNav";
import { api, ApiError, Project } from "@/lib/api";

export default function DashboardPage() {
  const router = useRouter();
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [newName, setNewName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    api
      .listProjects()
      .then(setProjects)
      .catch((err) => {
        if (err instanceof ApiError && err.status === 401) {
          router.push("/sign-in");
        } else {
          setError("Could not load projects.");
        }
      });
  }, [router]);

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
            <li key={project.id}>
              <Link
                href={`/projects/${project.id}`}
                className="block rounded-md border border-ink/10 bg-surface px-4 py-3 text-sm text-ink hover:border-trace"
              >
                {project.name}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
