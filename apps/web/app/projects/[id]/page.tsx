"use client";

import JSZip from "jszip";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { TopNav } from "@/components/TopNav";
import { api, ApiError, ChangeRequestSummary, DocumentDiff, Project, ProjectDocument, SearchResult } from "@/lib/api";
import { setLastProjectId } from "@/lib/lastProject";

/** The API only labels a search result with the uploaded document's own filename (e.g. a whole
 * .zip) - the actual file path/line range lives in source_metadata. Surface that instead so a
 * result reads as "here's exactly where this came from," not just "somewhere in this archive." */
function resultLocation(r: SearchResult): string {
  const meta = r.source_metadata;
  if (r.content_type === "code") {
    const filePath = typeof meta.file_path === "string" ? meta.file_path : r.filename;
    const symbol = typeof meta.symbol_name === "string" ? meta.symbol_name : null;
    const startLine = typeof meta.start_line === "number" ? meta.start_line : null;
    const endLine = typeof meta.end_line === "number" ? meta.end_line : null;
    let location = filePath;
    if (symbol) location += ` · ${symbol}`;
    if (startLine != null && endLine != null) location += ` · lines ${startLine}-${endLine}`;
    return location;
  }
  const filename = typeof meta.filename === "string" ? meta.filename : r.filename;
  const page = typeof meta.page_number === "number" ? meta.page_number : null;
  return page != null ? `${filename} · page ${page}` : filename;
}

const REQUEST_STATUS_STYLES: Record<string, string> = {
  pending: "bg-ink/10 text-ink/70",
  analysing: "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300",
  awaiting_clarification: "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300",
  awaiting_approval: "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300",
  approved: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300",
  rejected: "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300",
  failed: "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300",
};

const REQUEST_STATUS_LABEL: Record<string, string> = {
  pending: "Pending",
  analysing: "Analysing…",
  awaiting_clarification: "Waiting on answer",
  awaiting_approval: "Ready for review",
  approved: "Approved",
  rejected: "Rejected",
  failed: "Failed",
};

const STATUS_STYLES: Record<string, string> = {
  uploaded: "bg-ink/10 text-ink/70",
  processing: "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300",
  ready: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300",
  failed: "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300",
};

const DOC_EXTENSIONS = [".pdf", ".txt", ".md"];

function isDocFile(name: string) {
  const lower = name.toLowerCase();
  return DOC_EXTENSIONS.some((ext) => lower.endsWith(ext));
}

function isZipFile(name: string) {
  return name.toLowerCase().endsWith(".zip");
}

// Mirrors apps/api/app/services/archive.py so the client never zips (and gets rejected for) the
// same junk the backend would have ignored anyway - node_modules alone can be thousands of files.
const IGNORED_DIR_SEGMENTS = new Set(["node_modules", ".git", "__pycache__", "venv", ".venv", "dist", "build", ".next"]);
const ALLOWED_SOURCE_EXTENSIONS = [".py", ".js", ".jsx", ".ts", ".tsx"];

function isIgnoredPath(path: string): boolean {
  const segments = path.split("/");
  return segments.slice(0, -1).some((segment) => IGNORED_DIR_SEGMENTS.has(segment));
}

function isAllowedSourceFile(path: string): boolean {
  const lower = path.toLowerCase();
  return ALLOWED_SOURCE_EXTENSIONS.some((ext) => lower.endsWith(ext));
}

type PathedFile = { path: string; file: File };

/** Builds a codebase zip from a folder's worth of files, dropping ignored directories and
 * non-source files first so a whole project (node_modules included) doesn't blow past the
 * backend's entry-count safety cap. Returns null if nothing source-relevant survived the filter. */
async function buildCodebaseZip(
  entries: PathedFile[],
  onProgress?: (percent: number) => void
): Promise<File | null> {
  const relevant = entries.filter(({ path }) => !isIgnoredPath(path) && isAllowedSourceFile(path));
  if (relevant.length === 0) return null;

  const zip = new JSZip();
  for (const { path, file } of relevant) {
    zip.file(path, file);
  }
  const blob = await zip.generateAsync({ type: "blob" }, (metadata) => {
    onProgress?.(Math.round(metadata.percent));
  });
  const topLevelName = relevant[0].path.split("/")[0] || "codebase";
  return new File([blob], `${topLevelName}.zip`, { type: "application/zip" });
}

/** Same filtering as buildCodebaseZip, but for a .zip the user already produced themselves (e.g.
 * via Explorer's "Compress to zip" on the whole project folder) rather than one we're building
 * from loose files - those commonly include node_modules/.git/build output too, and previously
 * went straight to the backend unfiltered, hitting the same entry-count cap. Returns the original
 * file unchanged if it's already small enough to not need filtering. */
async function filterExistingZip(file: File, onProgress?: (percent: number) => void): Promise<File | null> {
  const zip = await JSZip.loadAsync(file);
  const entries = Object.values(zip.files).filter((entry) => !entry.dir);
  if (entries.length <= 2000) return file;

  const relevant = entries.filter((entry) => !isIgnoredPath(entry.name) && isAllowedSourceFile(entry.name));
  if (relevant.length === 0) return null;

  const filtered = new JSZip();
  for (const [i, entry] of relevant.entries()) {
    filtered.file(entry.name, await entry.async("blob"));
    // Reading each entry back out of the original zip is its own slow pass over potentially
    // thousands of files - counts for the first half of the bar, generateAsync's own progress
    // (re-compressing the filtered set) fills the second half.
    onProgress?.(Math.round(((i + 1) / relevant.length) * 50));
  }
  const blob = await filtered.generateAsync({ type: "blob" }, (metadata) => {
    onProgress?.(50 + Math.round(metadata.percent / 2));
  });
  return new File([blob], file.name, { type: "application/zip" });
}

/** Surfaces the API's actual error detail (e.g. "Not a valid ZIP archive") instead of masking
 * every failure behind the same generic message. */
function describeError(err: unknown, fallback: string): string {
  return err instanceof ApiError ? err.message : fallback;
}

/** Recursively walks a dropped folder's FileSystemDirectoryEntry, preserving relative paths. */
async function readDirectoryEntry(entry: FileSystemDirectoryEntry): Promise<PathedFile[]> {
  const reader = entry.createReader();
  const children: FileSystemEntry[] = [];
  // readEntries only returns up to 100 entries per call - keep calling until it's empty.
  for (;;) {
    const batch = await new Promise<FileSystemEntry[]>((resolve, reject) => reader.readEntries(resolve, reject));
    if (batch.length === 0) break;
    children.push(...batch);
  }

  const results: PathedFile[] = [];
  for (const child of children) {
    if (child.isDirectory) {
      results.push(...(await readDirectoryEntry(child as FileSystemDirectoryEntry)));
    } else {
      const file = await new Promise<File>((resolve, reject) => (child as FileSystemFileEntry).file(resolve, reject));
      results.push({ path: child.fullPath.replace(/^\//, ""), file });
    }
  }
  return results;
}

/** Reads whatever was dropped (loose files and/or whole folders) into a flat, path-preserving list. */
async function collectDroppedEntries(dataTransfer: DataTransfer): Promise<PathedFile[]> {
  const results: PathedFile[] = [];
  for (const item of Array.from(dataTransfer.items)) {
    const entry = item.webkitGetAsEntry?.();
    if (entry?.isDirectory) {
      results.push(...(await readDirectoryEntry(entry as FileSystemDirectoryEntry)));
    } else if (entry?.isFile) {
      const file = await new Promise<File>((resolve, reject) => (entry as FileSystemFileEntry).file(resolve, reject));
      results.push({ path: file.name, file });
    } else {
      const file = item.getAsFile();
      if (file) results.push({ path: file.name, file });
    }
  }
  return results;
}

export default function ProjectWorkspacePage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const projectId = params.id;

  const [project, setProject] = useState<Project | null>(null);
  const [documents, setDocuments] = useState<ProjectDocument[]>([]);
  const [changeRequests, setChangeRequests] = useState<ChangeRequestSummary[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [uploadingDoc, setUploadingDoc] = useState(false);
  const [uploadingZip, setUploadingZip] = useState(false);
  const [uploadingFolder, setUploadingFolder] = useState(false);
  const [uploadingDrop, setUploadingDrop] = useState(false);
  const [dragActive, setDragActive] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadProgress, setUploadProgress] = useState<{ phase: "zipping" | "uploading"; percent: number } | null>(
    null
  );
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [githubOwner, setGithubOwner] = useState("");
  const [githubRepo, setGithubRepo] = useState("");
  const [githubBranch, setGithubBranch] = useState("main");
  const [importingGithub, setImportingGithub] = useState(false);
  const [diff, setDiff] = useState<DocumentDiff | null>(null);
  const [diffError, setDiffError] = useState<string | null>(null);
  const docInputRef = useRef<HTMLInputElement>(null);
  const zipInputRef = useRef<HTMLInputElement>(null);
  const folderInputRef = useRef<HTMLInputElement>(null);

  const [query, setQuery] = useState("");
  const [contentType, setContentType] = useState<"all" | "requirement" | "code">("all");
  const [results, setResults] = useState<SearchResult[] | null>(null);
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);

  const [requestText, setRequestText] = useState("");
  const [submittingRequest, setSubmittingRequest] = useState(false);
  const [requestError, setRequestError] = useState<string | null>(null);
  const [liveSteps, setLiveSteps] = useState<{ tool_name: string | null; output_summary: string }[]>([]);

  async function loadAll() {
    try {
      const [proj, docs, requests] = await Promise.all([
        api.getProject(projectId),
        api.listDocuments(projectId),
        api.listChangeRequests(projectId),
      ]);
      setProject(proj);
      setDocuments(docs);
      setChangeRequests(requests);
      setLastProjectId(projectId);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        router.replace("/sign-in");
      } else {
        setLoadError("Could not load this project.");
      }
    }
  }

  useEffect(() => {
    loadAll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  // Ingestion (embedding) now runs as a background task on the API, so a freshly uploaded
  // document comes back as "uploaded"/"processing" - poll until every document has reached a
  // terminal status (ready/failed) instead of leaving the badge stuck.
  useEffect(() => {
    if (!documents.some((d) => d.status === "uploaded" || d.status === "processing")) return;
    let cancelled = false;
    const timer = setTimeout(async () => {
      if (cancelled) return;
      try {
        const docs = await api.listDocuments(projectId);
        if (!cancelled) setDocuments(docs);
      } catch {
        // transient - next poll (or a manual reload) will pick it back up
      }
    }, 2000);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [documents, projectId]);

  useEffect(() => {
    // webkitdirectory/directory aren't part of React's HTMLInputElement typings - set them
    // imperatively on the underlying DOM node instead of fighting the JSX types over it.
    const el = folderInputRef.current;
    if (el) {
      el.setAttribute("webkitdirectory", "");
      el.setAttribute("directory", "");
    }
  }, []);

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
    } catch (err) {
      setUploadError(describeError(err, "Could not upload that document."));
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
    setUploadProgress({ phase: "zipping", percent: 0 });
    try {
      const filtered = await filterExistingZip(file, (percent) => setUploadProgress({ phase: "zipping", percent }));
      if (!filtered) {
        setUploadError("No supported source files (.py/.js/.jsx/.ts/.tsx) found outside ignored folders like node_modules.");
        return;
      }
      setUploadProgress({ phase: "uploading", percent: 0 });
      await api.uploadCodebase(projectId, filtered, (percent) => setUploadProgress({ phase: "uploading", percent }));
      if (zipInputRef.current) zipInputRef.current.value = "";
      await loadAll();
    } catch (err) {
      setUploadError(describeError(err, "Could not upload that codebase archive."));
    } finally {
      setUploadingZip(false);
      setUploadProgress(null);
    }
  }

  async function handleFolderSelected(e: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files ?? []);
    if (files.length === 0) return;
    setUploadingFolder(true);
    setUploadError(null);
    setUploadProgress({ phase: "zipping", percent: 0 });
    try {
      const entries = files.map((file) => ({
        path: (file as File & { webkitRelativePath?: string }).webkitRelativePath || file.name,
        file,
      }));
      const zipFile = await buildCodebaseZip(entries, (percent) => setUploadProgress({ phase: "zipping", percent }));
      if (!zipFile) {
        setUploadError("No supported source files (.py/.js/.jsx/.ts/.tsx) found outside ignored folders like node_modules.");
        return;
      }

      setUploadProgress({ phase: "uploading", percent: 0 });
      await api.uploadCodebase(projectId, zipFile, (percent) => setUploadProgress({ phase: "uploading", percent }));
      await loadAll();
    } catch (err) {
      setUploadError(describeError(err, "Could not upload that codebase folder."));
    } finally {
      setUploadingFolder(false);
      setUploadProgress(null);
      if (folderInputRef.current) folderInputRef.current.value = "";
    }
  }

  /** Routes drag-and-dropped or pasted files: a lone doc/zip uploads directly as itself, anything
   * else (a folder's worth of files, or several loose source files) is zipped client-side and
   * uploaded as a codebase, same as the folder picker above. */
  async function uploadEntries(entries: PathedFile[]) {
    if (entries.length === 0) return;
    setUploadError(null);
    setUploadingDrop(true);
    try {
      if (entries.length === 1 && isZipFile(entries[0].file.name)) {
        setUploadProgress({ phase: "zipping", percent: 0 });
        const filtered = await filterExistingZip(entries[0].file, (percent) =>
          setUploadProgress({ phase: "zipping", percent })
        );
        if (!filtered) {
          setUploadError(
            "No supported source files (.py/.js/.jsx/.ts/.tsx) found outside ignored folders like node_modules."
          );
          return;
        }
        setUploadProgress({ phase: "uploading", percent: 0 });
        await api.uploadCodebase(projectId, filtered, (percent) => setUploadProgress({ phase: "uploading", percent }));
      } else if (entries.length === 1 && isDocFile(entries[0].file.name)) {
        await api.uploadDocument(projectId, entries[0].file);
      } else {
        setUploadProgress({ phase: "zipping", percent: 0 });
        const zipFile = await buildCodebaseZip(entries, (percent) => setUploadProgress({ phase: "zipping", percent }));
        if (!zipFile) {
          setUploadError(
            "No supported source files (.py/.js/.jsx/.ts/.tsx) found outside ignored folders like node_modules."
          );
          return;
        }
        setUploadProgress({ phase: "uploading", percent: 0 });
        await api.uploadCodebase(projectId, zipFile, (percent) => setUploadProgress({ phase: "uploading", percent }));
      }
      await loadAll();
    } catch (err) {
      setUploadError(describeError(err, "Could not upload that."));
    } finally {
      setUploadingDrop(false);
      setUploadProgress(null);
    }
  }

  async function handleDrop(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setDragActive(false);
    await uploadEntries(await collectDroppedEntries(e.dataTransfer));
  }

  function handleDragOver(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setDragActive(true);
  }

  useEffect(() => {
    function onPaste(e: ClipboardEvent) {
      const files = Array.from(e.clipboardData?.files ?? []);
      if (files.length === 0) return;
      e.preventDefault();
      uploadEntries(files.map((file) => ({ path: file.name, file })));
    }
    window.addEventListener("paste", onPaste);
    return () => window.removeEventListener("paste", onPaste);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  async function handleDelete(documentId: string) {
    setDeleteError(null);
    try {
      await api.deleteDocument(projectId, documentId);
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        // Already gone server-side (e.g. a duplicate click) - just drop it from the list below,
        // no need to alarm the user with an error for something that's already the desired state.
      } else {
        setDeleteError(describeError(err, "Could not delete that document."));
        return;
      }
    }
    setDocuments((prev) => prev.filter((d) => d.id !== documentId));
  }

  async function handleGithubImport(e: React.FormEvent) {
    e.preventDefault();
    if (!githubOwner.trim() || !githubRepo.trim()) return;
    setImportingGithub(true);
    setUploadError(null);
    try {
      await api.importGithubRepo(projectId, githubOwner.trim(), githubRepo.trim(), githubBranch.trim() || "main");
      setGithubOwner("");
      setGithubRepo("");
      setGithubBranch("main");
      await loadAll();
    } catch (err) {
      setUploadError(describeError(err, "Could not import that repository."));
    } finally {
      setImportingGithub(false);
    }
  }

  async function handleCompare(documentId: string, againstId: string) {
    setDiffError(null);
    setDiff(null);
    try {
      const result = await api.diffDocumentVersions(projectId, documentId, againstId);
      setDiff(result);
    } catch (err) {
      setDiffError(describeError(err, "Could not compare these versions."));
    }
  }

  async function handleNewAnalysis(e: React.FormEvent) {
    e.preventDefault();
    if (!requestText.trim()) return;
    setSubmittingRequest(true);
    setRequestError(null);
    setLiveSteps([]);

    let eventSource: EventSource | null = null;
    try {
      const changeRequest = await api.createChangeRequest(projectId, requestText.trim());

      // Live progress: subscribe before kicking off analysis, since analyse itself blocks until
      // the whole run finishes (or pauses) - without this, nothing would show until the very end.
      eventSource = new EventSource(api.runEventsUrl(changeRequest.id), { withCredentials: true });
      eventSource.onmessage = (event) => {
        try {
          const step = JSON.parse(event.data);
          setLiveSteps((prev) => [...prev, { tool_name: step.tool_name, output_summary: step.output_summary }]);
        } catch {
          // ignore malformed/heartbeat payloads
        }
      };
      eventSource.addEventListener("done", () => {
        eventSource?.close();
      });

      const run = await api.analyseRequest(changeRequest.id);
      router.push(`/runs/${run.id}`);
    } catch (err) {
      setRequestError(describeError(err, "Could not start the analysis."));
      setSubmittingRequest(false);
    } finally {
      eventSource?.close();
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
    } catch (err) {
      setSearchError(describeError(err, "Search failed. Try again."));
    } finally {
      setSearching(false);
    }
  }

  return (
    <main className="mx-auto max-w-3xl px-4 py-12">
      <TopNav />
      <h1 className="font-serif text-2xl font-semibold text-ink">
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
        <div className="mt-2 flex items-center gap-2">
          <input ref={folderInputRef} type="file" onChange={handleFolderSelected} className="hidden" />
          <button
            type="button"
            onClick={() => folderInputRef.current?.click()}
            disabled={uploadingFolder}
            className="rounded-md border border-ink/20 px-3 py-2 text-xs font-medium text-ink disabled:opacity-60"
          >
            {uploadingFolder ? "Zipping and uploading…" : "Add codebase folder"}
          </button>
          <span className="text-xs text-ink/50">
            Pick a project folder directly - it's zipped in your browser before upload.
          </span>
        </div>

        <form onSubmit={handleGithubImport} className="mt-3 flex flex-wrap items-center gap-2">
          <input
            value={githubOwner}
            onChange={(e) => setGithubOwner(e.target.value)}
            placeholder="owner"
            className="w-28 rounded-md border border-ink/15 bg-background px-2 py-1.5 text-xs outline-none focus:border-trace"
          />
          <span className="text-xs text-ink/40">/</span>
          <input
            value={githubRepo}
            onChange={(e) => setGithubRepo(e.target.value)}
            placeholder="repo"
            className="w-32 rounded-md border border-ink/15 bg-background px-2 py-1.5 text-xs outline-none focus:border-trace"
          />
          <input
            value={githubBranch}
            onChange={(e) => setGithubBranch(e.target.value)}
            placeholder="branch"
            className="w-24 rounded-md border border-ink/15 bg-background px-2 py-1.5 text-xs outline-none focus:border-trace"
          />
          <button
            type="submit"
            disabled={importingGithub}
            className="rounded-md border border-ink/20 px-3 py-1.5 text-xs font-medium text-ink disabled:opacity-60"
          >
            {importingGithub ? "Importing…" : "Import from GitHub"}
          </button>
          <span className="text-xs text-ink/50">Public repos only - read-only, no write access requested.</span>
        </form>

        <div
          onDrop={handleDrop}
          onDragOver={handleDragOver}
          onDragLeave={() => setDragActive(false)}
          className={`mt-3 flex flex-col items-center justify-center gap-1 rounded-md border-2 border-dashed px-4 py-6 text-center transition-colors ${
            dragActive ? "border-trace bg-trace/5" : "border-ink/20"
          }`}
        >
          <p className="text-sm text-ink/70">
            {uploadingDrop
              ? "Uploading…"
              : "Drag & drop a requirement doc, a .zip, or a whole folder here"}
          </p>
          <p className="text-xs text-ink/50">
            or copy a file in your file explorer and paste it (Ctrl+V) anywhere on this page
          </p>
        </div>
        {uploadProgress && (
          <div className="mt-3">
            <div className="mb-1 flex items-center justify-between text-xs text-ink/60">
              <span>{uploadProgress.phase === "zipping" ? "Zipping files…" : "Uploading…"}</span>
              <span>{uploadProgress.percent}%</span>
            </div>
            <div className="h-2 w-full overflow-hidden rounded-full bg-ink/10">
              <div
                className="h-full rounded-full bg-accent transition-[width] duration-150"
                style={{ width: `${uploadProgress.percent}%` }}
              />
            </div>
          </div>
        )}
        {uploadError && <p className="mt-2 text-sm text-red-700">{uploadError}</p>}
      </section>

      <section className="mt-8">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-ink/50">
          Documents
        </h2>
        {deleteError && <p className="mb-2 text-sm text-red-700">{deleteError}</p>}
        {documents.length === 0 ? (
          <p className="text-sm text-ink/60">No documents or code uploaded yet.</p>
        ) : (
          <ul className="flex flex-col gap-2">
            {documents.map((doc) => (
              <li
                key={doc.id}
                className="flex items-center justify-between gap-3 rounded-md border border-ink/10 bg-surface px-4 py-3 text-sm"
              >
                <div className="min-w-0">
                  <p className="truncate font-medium text-ink">
                    {doc.filename}
                    {doc.version > 1 && <span className="ml-1 text-xs text-ink/40">v{doc.version}</span>}
                  </p>
                  <p className="text-xs text-ink/50">{doc.kind === "requirement" ? "Requirement doc" : "Codebase"}</p>
                  {doc.status === "processing" && !!doc.chunks_total && (
                    <div className="mt-1.5 w-40">
                      <div className="mb-0.5 flex items-center justify-between text-[10px] text-ink/50">
                        <span>Embedding…</span>
                        <span>
                          {doc.chunks_embedded ?? 0}/{doc.chunks_total}
                        </span>
                      </div>
                      <div className="h-1.5 w-full overflow-hidden rounded-full bg-ink/10">
                        <div
                          className="h-full rounded-full bg-accent transition-[width] duration-300"
                          style={{
                            width: `${Math.round(((doc.chunks_embedded ?? 0) / doc.chunks_total) * 100)}%`,
                          }}
                        />
                      </div>
                    </div>
                  )}
                  {doc.status === "failed" && doc.error && (
                    <p className="mt-1 text-xs text-red-700">{doc.error}</p>
                  )}
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  <span className={`rounded-full px-2 py-1 text-xs font-medium ${STATUS_STYLES[doc.status]}`}>
                    {doc.status}
                  </span>
                  {doc.previous_version_id && doc.status === "ready" && (
                    <button
                      onClick={() => handleCompare(doc.id, doc.previous_version_id!)}
                      className="text-xs text-trace hover:underline"
                    >
                      Compare with previous version
                    </button>
                  )}
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
        {diffError && <p className="mt-2 text-sm text-red-700">{diffError}</p>}
        {diff && (
          <div className="mt-3 rounded-md border border-ink/10 bg-surface p-4">
            <div className="mb-2 flex items-center justify-between">
              <p className="text-xs font-medium text-ink/70">
                v{diff.from_version} → v{diff.to_version}
              </p>
              <button onClick={() => setDiff(null)} className="text-xs text-ink/50 hover:text-ink">
                Close
              </button>
            </div>
            <pre className="max-h-96 overflow-auto whitespace-pre-wrap break-all font-mono text-xs">
              {diff.diff_lines.map((line, i) => (
                <div
                  key={i}
                  className={
                    line.startsWith("+") && !line.startsWith("+++")
                      ? "bg-green-50 text-green-800"
                      : line.startsWith("-") && !line.startsWith("---")
                      ? "bg-red-50 text-red-800"
                      : "text-ink/60"
                  }
                >
                  {line}
                </div>
              ))}
            </pre>
          </div>
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
            className="rounded-md border border-ink/15 bg-surface px-3 py-2 text-sm outline-none focus:border-trace"
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
        {submittingRequest && liveSteps.length > 0 && (
          <ul className="mt-3 flex flex-col gap-1 rounded-md border border-ink/10 bg-surface p-3 text-xs text-ink/70">
            {liveSteps.map((step, i) => (
              <li key={i}>
                <span className="font-medium text-ink">{step.tool_name ?? "classify"}</span> — {step.output_summary}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="mt-8">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-ink/50">
          Previous analyses
        </h2>
        {changeRequests.length === 0 ? (
          <p className="text-sm text-ink/60">No analyses submitted yet.</p>
        ) : (
          <ul className="flex flex-col gap-2">
            {changeRequests.map((cr) => {
              const body = (
                <>
                  <div className="min-w-0">
                    <p className="truncate text-sm text-ink">{cr.request_text}</p>
                    {cr.plan_summary && (
                      <p className="mt-1 truncate text-xs text-ink/50">{cr.plan_summary}</p>
                    )}
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    {cr.confidence && (
                      <span className="text-xs text-ink/40">{cr.confidence} confidence</span>
                    )}
                    <span
                      className={`rounded-full px-2 py-1 text-xs font-medium ${
                        REQUEST_STATUS_STYLES[cr.status] ?? "bg-ink/10 text-ink/70"
                      }`}
                    >
                      {REQUEST_STATUS_LABEL[cr.status] ?? cr.status}
                    </span>
                  </div>
                </>
              );
              return (
                <li key={cr.id}>
                  {cr.latest_run_id ? (
                    <Link
                      href={`/runs/${cr.latest_run_id}`}
                      className="flex items-center justify-between gap-3 rounded-md border border-ink/10 bg-surface px-4 py-3 hover:border-trace"
                    >
                      {body}
                    </Link>
                  ) : (
                    <div className="flex items-center justify-between gap-3 rounded-md border border-ink/10 bg-surface px-4 py-3">
                      {body}
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        )}
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
            className="flex-1 rounded-md border border-ink/15 bg-surface px-3 py-2 text-sm outline-none focus:border-trace"
          />
          <select
            id="search-content-type"
            value={contentType}
            onChange={(e) => setContentType(e.target.value as typeof contentType)}
            className="rounded-md border border-ink/15 bg-surface px-3 py-2 text-sm"
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
              <li key={r.chunk_id} className="rounded-md border border-ink/10 bg-surface p-4 text-sm">
                <div className="mb-1 flex items-center justify-between gap-2 text-xs text-ink/50">
                  <span className="font-mono font-medium text-trace">{resultLocation(r)}</span>
                  <span className="shrink-0">score {r.score.toFixed(2)}</span>
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
