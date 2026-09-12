"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { api, ApiError, Project, ProjectDocument, SearchResult } from "@/lib/api";

const STATUS_STYLES: Record<string, string> = {
  uploaded: "bg-ink/10 text-ink/70",
  processing: "bg-amber-100 text-amber-800",
  ready: "bg-emerald-100 text-emerald-800",
  failed: "bg-red-100 text-red-800",
};

export default function ProjectWorkspacePage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const projectId = params.id;

  const [project, setProject] = useState<Project | null>(null);
  const [documents, setDocuments] = useState<ProjectDocument[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [uploadingDoc, setUploadingDoc] = useState(false);
  const [uploadingZip, setUploadingZip] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const docInputRef = useRef<HTMLInputElement>(null);
  const zipInputRef = useRef<HTMLInputElement>(null);

  const [query, setQuery] = useState("");
  const [contentType, setContentType] = useState<"all" | "requirement" | "code">("all");
  const [results, setResults] = useState<SearchResult[] | null>(null);
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);

  const [requestText, setRequestText] = useState("");
  const [submittingRequest, setSubmittingRequest] = useState(false);
  const [requestError, setRequestError] = useState<string | null>(null);

  async function loadAll() {
    try {
      const [proj, docs] = await Promise.all([api.getProject(projectId), api.listDocuments(projectId)]);
      setProject(proj);
      setDocuments(docs);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        router.push("/sign-in");
      } else {
        setLoadError("Could not load this project.");
      }
    }
  }

  useEffect(() => {
    loadAll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  async function handleUploadDocument(e: React.FormEvent) {
    e.preventDefault();
    const file = docInputRef.current?.files?.[0];
    if (!file) return;
    setUploadingDoc(true);
    setUploadError(null);
    try {
      await api.uploadDocument(projectId, file);
      if (docInputRef.current) docInputRef.current.value = "";
      await loadAll();
    } catch {
      setUploadError("Could not upload that document.");
    } finally {
      setUploadingDoc(false);
    }
  }

  async function handleUploadCodebase(e: React.FormEvent) {
    e.preventDefault();
    const file = zipInputRef.current?.files?.[0];
    if (!file) return;
    setUploadingZip(true);
    setUploadError(null);
    try {
      await api.uploadCodebase(projectId, file);
      if (zipInputRef.current) zipInputRef.current.value = "";
      await loadAll();
    } catch {
      setUploadError("Could not upload that codebase archive.");
    } finally {
      setUploadingZip(false);
    }
  }

  async function handleDelete(documentId: string) {
    await api.deleteDocument(projectId, documentId);
    setDocuments((prev) => prev.filter((d) => d.id !== documentId));
  }

  async function handleNewAnalysis(e: React.FormEvent) {
    e.preventDefault();
    if (!requestText.trim()) return;
    setSubmittingRequest(true);
    setRequestError(null);
    try {
      const changeRequest = await api.createChangeRequest(projectId, requestText.trim());
      const run = await api.analyseRequest(changeRequest.id);
      router.push(`/runs/${run.id}`);
    } catch {
      setRequestError("Could not start the analysis.");
      setSubmittingRequest(false);
    }
  }

  async function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    if (!query.trim()) return;
    setSearching(true);
    setSearchError(null);
    try {
      const res = await api.search(projectId, query.trim(), contentType);
      setResults(res.results);
    } catch {
      setSearchError("Search failed. Try again.");
    } finally {
      setSearching(false);
    }
  }

  return (
    <main className="mx-auto max-w-3xl px-4 py-12">
      <Link href="/dashboard" className="text-sm text-trace">
        ← All projects
      </Link>
      <h1 className="mt-2 font-serif text-2xl font-semibold text-ink">
        {project?.name ?? "Loading…"}
      </h1>

      {loadError && <p className="mt-4 text-sm text-red-700">{loadError}</p>}

      <section className="mt-8">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-ink/50">
          Upload
        </h2>
        <div className="flex flex-col gap-3 sm:flex-row">
          <form onSubmit={handleUploadDocument} className="flex flex-1 items-center gap-2">
            <input
              ref={docInputRef}
              type="file"
              accept=".pdf,.txt,.md"
              className="flex-1 text-xs"
            />
            <button
              type="submit"
              disabled={uploadingDoc}
              className="rounded-md bg-accent px-3 py-2 text-xs font-medium text-white disabled:opacity-60"
            >
              {uploadingDoc ? "Uploading…" : "Add requirement"}
            </button>
          </form>
          <form onSubmit={handleUploadCodebase} className="flex flex-1 items-center gap-2">
            <input ref={zipInputRef} type="file" accept=".zip" className="flex-1 text-xs" />
            <button
              type="submit"
              disabled={uploadingZip}
              className="rounded-md bg-accent px-3 py-2 text-xs font-medium text-white disabled:opacity-60"
            >
              {uploadingZip ? "Uploading…" : "Add codebase"}
            </button>
          </form>
        </div>
        {uploadError && <p className="mt-2 text-sm text-red-700">{uploadError}</p>}
      </section>

      <section className="mt-8">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-ink/50">
          Documents
        </h2>
        {documents.length === 0 ? (
          <p className="text-sm text-ink/60">No documents or code uploaded yet.</p>
        ) : (
          <ul className="flex flex-col gap-2">
            {documents.map((doc) => (
              <li
                key={doc.id}
                className="flex items-center justify-between gap-3 rounded-md border border-ink/10 bg-white px-4 py-3 text-sm"
              >
                <div className="min-w-0">
                  <p className="truncate font-medium text-ink">{doc.filename}</p>
                  <p className="text-xs text-ink/50">{doc.kind === "requirement" ? "Requirement doc" : "Codebase"}</p>
                  {doc.status === "failed" && doc.error && (
                    <p className="mt-1 text-xs text-red-700">{doc.error}</p>
                  )}
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  <span className={`rounded-full px-2 py-1 text-xs font-medium ${STATUS_STYLES[doc.status]}`}>
                    {doc.status}
                  </span>
                  <button
                    onClick={() => handleDelete(doc.id)}
                    className="text-xs text-ink/50 hover:text-red-700"
                  >
                    Delete
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="mt-8">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-ink/50">
          New analysis
        </h2>
        <form onSubmit={handleNewAnalysis} className="flex flex-col gap-2">
          <textarea
            id="change-request-text"
            value={requestText}
            onChange={(e) => setRequestText(e.target.value)}
            placeholder="e.g. Make mobile OTP verification mandatory before a user can proceed with a loan application."
            rows={3}
            className="rounded-md border border-ink/15 bg-white px-3 py-2 text-sm outline-none focus:border-trace"
          />
          <button
            type="submit"
            disabled={submittingRequest}
            className="self-start rounded-md bg-accent px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
          >
            {submittingRequest ? "Starting analysis…" : "Analyse this request"}
          </button>
        </form>
        {requestError && <p className="mt-2 text-sm text-red-700">{requestError}</p>}
      </section>

      <section className="mt-8">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-ink/50">
          Semantic search
        </h2>
        <form onSubmit={handleSearch} className="flex flex-col gap-2 sm:flex-row">
          <input
            id="search-query"
            placeholder="e.g. mobile OTP verification before loan submission"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="flex-1 rounded-md border border-ink/15 bg-white px-3 py-2 text-sm outline-none focus:border-trace"
          />
          <select
            id="search-content-type"
            value={contentType}
            onChange={(e) => setContentType(e.target.value as typeof contentType)}
            className="rounded-md border border-ink/15 bg-white px-3 py-2 text-sm"
          >
            <option value="all">All content</option>
            <option value="requirement">Requirements</option>
            <option value="code">Code</option>
          </select>
          <button
            type="submit"
            disabled={searching}
            className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
          >
            {searching ? "Searching…" : "Search"}
          </button>
        </form>
        {searchError && <p className="mt-2 text-sm text-red-700">{searchError}</p>}

        {results !== null && (
          <ul className="mt-4 flex flex-col gap-3">
            {results.length === 0 && (
              <p className="text-sm text-ink/60">No results above the relevance threshold.</p>
            )}
            {results.map((r) => (
              <li key={r.chunk_id} className="rounded-md border border-ink/10 bg-white p-4 text-sm">
                <div className="mb-1 flex items-center justify-between gap-2 text-xs text-ink/50">
                  <span className="font-medium text-trace">{r.filename}</span>
                  <span>score {r.score.toFixed(2)}</span>
                </div>
                <p className="whitespace-pre-wrap text-ink/80">{r.text.slice(0, 400)}</p>
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}
