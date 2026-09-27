"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { TopNav } from "@/components/TopNav";
import { api, ApiError, BrdDocument, BrdInput, GeneratedBrd } from "@/lib/api";

function brdToMarkdown(brd: GeneratedBrd, projectName: string): string {
  const lines: string[] = [];
  lines.push(`# Business Requirements Document: ${projectName}`, "");
  lines.push("## Executive summary", brd.executive_summary, "");
  lines.push("## Business objectives", ...brd.business_objectives.map((o) => `- ${o}`), "");
  lines.push("## In scope", ...brd.in_scope.map((s) => `- ${s}`), "");
  lines.push("## Out of scope", ...brd.out_of_scope.map((s) => `- ${s}`), "");
  lines.push("## Stakeholders", ...brd.stakeholders.map((s) => `- ${s}`), "");
  lines.push(
    "## Functional requirements",
    ...brd.functional_requirements.map((r) => `- [${r.priority}] ${r.description}`),
    ""
  );
  lines.push(
    "## Non-functional requirements",
    ...brd.non_functional_requirements.map((r) => `- [${r.priority}] ${r.description}`),
    ""
  );
  if (brd.assumptions.length > 0) lines.push("## Assumptions", ...brd.assumptions.map((a) => `- ${a}`), "");
  if (brd.constraints.length > 0) lines.push("## Constraints", ...brd.constraints.map((c) => `- ${c}`), "");
  if (brd.risks.length > 0) lines.push("## Risks", ...brd.risks.map((r) => `- ${r}`), "");
  lines.push("## Success criteria", ...brd.success_criteria.map((c) => `- ${c}`), "");
  return lines.join("\n");
}

function downloadMarkdown(filename: string, content: string) {
  const blob = new Blob([content], { type: "text/markdown" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

async function downloadBrdPdf(filename: string, brd: GeneratedBrd, projectName: string) {
  const { jsPDF } = await import("jspdf");
  const doc = new jsPDF({ unit: "pt", format: "a4" });
  const pageWidth = doc.internal.pageSize.getWidth();
  const margin = 48;
  const maxWidth = pageWidth - margin * 2;
  let y = margin;

  function ensureSpace(lineHeight: number) {
    const pageHeight = doc.internal.pageSize.getHeight();
    if (y + lineHeight > pageHeight - margin) {
      doc.addPage();
      y = margin;
    }
  }

  function heading(text: string) {
    ensureSpace(24);
    doc.setFont("helvetica", "bold").setFontSize(13);
    doc.text(text, margin, y);
    y += 20;
    doc.setFont("helvetica", "normal").setFontSize(10);
  }

  function paragraph(text: string) {
    const lines = doc.splitTextToSize(text, maxWidth);
    for (const line of lines) {
      ensureSpace(14);
      doc.text(line, margin, y);
      y += 14;
    }
    y += 6;
  }

  function bullets(items: string[]) {
    for (const item of items) {
      const lines = doc.splitTextToSize(`- ${item}`, maxWidth - 10);
      for (const line of lines) {
        ensureSpace(14);
        doc.text(line, margin + 10, y);
        y += 14;
      }
    }
    y += 6;
  }

  doc.setFont("helvetica", "bold").setFontSize(16);
  doc.text(`BRD: ${projectName}`, margin, y, { maxWidth });
  y += 26;
  doc.setFont("helvetica", "normal").setFontSize(10);

  heading("Executive summary");
  paragraph(brd.executive_summary);
  heading("Business objectives");
  bullets(brd.business_objectives);
  heading("In scope");
  bullets(brd.in_scope);
  heading("Out of scope");
  bullets(brd.out_of_scope);
  heading("Stakeholders");
  bullets(brd.stakeholders);
  heading("Functional requirements");
  bullets(brd.functional_requirements.map((r) => `[${r.priority}] ${r.description}`));
  heading("Non-functional requirements");
  bullets(brd.non_functional_requirements.map((r) => `[${r.priority}] ${r.description}`));
  if (brd.assumptions.length > 0) {
    heading("Assumptions");
    bullets(brd.assumptions);
  }
  if (brd.constraints.length > 0) {
    heading("Constraints");
    bullets(brd.constraints);
  }
  if (brd.risks.length > 0) {
    heading("Risks");
    bullets(brd.risks);
  }
  heading("Success criteria");
  bullets(brd.success_criteria);

  doc.save(filename);
}

const PRIORITY_LABEL: Record<string, string> = {
  must_have: "Must have",
  should_have: "Should have",
  could_have: "Could have",
  wont_have: "Won't have",
};

const PRIORITY_STYLE: Record<string, string> = {
  must_have: "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300",
  should_have: "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300",
  could_have: "bg-ink/10 text-ink/70",
  wont_have: "bg-ink/5 text-ink/40",
};

function Section({ title, items }: { title: string; items: string[] }) {
  if (items.length === 0) return null;
  return (
    <div>
      <p className="font-medium text-ink">{title}</p>
      <ul className="mt-1 list-disc pl-5 text-ink/70">
        {items.map((item, i) => (
          <li key={i}>{item}</li>
        ))}
      </ul>
    </div>
  );
}

function RequirementSection({
  title,
  items,
}: {
  title: string;
  items: { description: string; priority: string }[];
}) {
  if (items.length === 0) return null;
  return (
    <div>
      <p className="font-medium text-ink">{title}</p>
      <ul className="mt-1 flex flex-col gap-1.5">
        {items.map((item, i) => (
          <li key={i} className="flex items-start gap-2 text-ink/70">
            <span
              className={`mt-0.5 shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ${
                PRIORITY_STYLE[item.priority] ?? "bg-ink/10"
              }`}
            >
              {PRIORITY_LABEL[item.priority] ?? item.priority}
            </span>
            <span>{item.description}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function BrdView({ brd }: { brd: GeneratedBrd }) {
  return (
    <div className="flex flex-col gap-5 rounded-lg border border-ink/10 bg-surface p-5 shadow-sm text-sm">
      <div>
        <p className="font-medium text-ink">Executive summary</p>
        <p className="mt-1 text-ink/70">{brd.executive_summary}</p>
      </div>
      <Section title="Business objectives" items={brd.business_objectives} />
      <div className="grid gap-4 sm:grid-cols-2">
        <Section title="In scope" items={brd.in_scope} />
        <Section title="Out of scope" items={brd.out_of_scope} />
      </div>
      <Section title="Stakeholders" items={brd.stakeholders} />
      <RequirementSection title="Functional requirements" items={brd.functional_requirements} />
      <RequirementSection title="Non-functional requirements" items={brd.non_functional_requirements} />
      <Section title="Assumptions" items={brd.assumptions} />
      <Section title="Constraints" items={brd.constraints} />
      <Section title="Risks" items={brd.risks} />
      <Section title="Success criteria" items={brd.success_criteria} />
    </div>
  );
}

export default function BrdGeneratorPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const projectId = params.id;

  const [history, setHistory] = useState<BrdDocument[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [projectName, setProjectName] = useState("");
  const [background, setBackground] = useState("");
  const [objectives, setObjectives] = useState("");
  const [targetUsers, setTargetUsers] = useState("");
  const [keyFeatures, setKeyFeatures] = useState("");
  const [constraints, setConstraints] = useState("");

  const [generating, setGenerating] = useState(false);
  const [generateError, setGenerateError] = useState<string | null>(null);
  const [current, setCurrent] = useState<BrdDocument | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  async function loadHistory() {
    try {
      const docs = await api.listBrdDocuments(projectId);
      setHistory(docs);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        // A signed-out visitor can still see and fill out this form - only actually generating
        // (below) requires signing in, so this just leaves history empty rather than bouncing
        // them away before they've done anything.
        setHistory([]);
      } else {
        setLoadError("Could not load previous BRDs.");
      }
    }
  }

  useEffect(() => {
    loadHistory();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  async function handleGenerate(e: React.FormEvent) {
    e.preventDefault();
    if (
      !projectName.trim() ||
      !background.trim() ||
      !objectives.trim() ||
      !targetUsers.trim() ||
      !keyFeatures.trim()
    ) {
      return;
    }
    setGenerating(true);
    setGenerateError(null);
    try {
      const payload: BrdInput = {
        project_name: projectName.trim(),
        background: background.trim(),
        objectives: objectives.trim(),
        target_users: targetUsers.trim(),
        key_features: keyFeatures.trim(),
        constraints: constraints.trim() || null,
      };
      const doc = await api.generateBrd(projectId, payload);
      setCurrent(doc);
      setHistory((prev) => [doc, ...(prev ?? [])]);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        // The real gate: trying to actually generate is what requires an account, not viewing
        // the form. replace(), not push(), so the back button from sign-in returns straight to
        // this page rather than to a redirect that immediately bounces forward again.
        router.replace("/sign-in");
        return;
      }
      setGenerateError(err instanceof ApiError ? err.message : "Could not generate a BRD right now.");
    } finally {
      setGenerating(false);
    }
  }

  async function handleDelete(id: string) {
    setDeleteError(null);
    try {
      await api.deleteBrdDocument(projectId, id);
      setHistory((prev) => prev?.filter((d) => d.id !== id) ?? prev);
      setCurrent((prev) => (prev?.id === id ? null : prev));
    } catch (err) {
      setDeleteError(err instanceof ApiError ? err.message : "Could not delete that BRD.");
    }
  }

  return (
    <main className="mx-auto max-w-5xl px-4 py-12">
      <TopNav />
      <div className="mx-auto max-w-2xl">
      <div className="auth-background rounded-lg px-6 py-10 text-white">
        <Link href={`/projects/${projectId}`} className="text-sm text-white/70 hover:text-white">
          ← Back to project
        </Link>
        <p className="mt-4 inline-block rounded-full border border-white/20 px-3 py-1 text-xs font-medium text-white/70">
          Agentic SDLC & codebase intelligence
        </p>
        <h1 className="mt-4 font-serif text-3xl font-semibold leading-tight sm:text-4xl">BRD generator</h1>
        <p className="mt-3 max-w-xl text-sm leading-relaxed text-white/80 sm:text-base">
          Fill in a few plain-language details and the LLM expands them into a full Business
          Requirements Document - scope, stakeholders, functional and non-functional requirements,
          risks, and success criteria.
        </p>
      </div>

      <form onSubmit={handleGenerate} className="mt-8 flex flex-col gap-4 rounded-lg border border-ink/10 bg-background p-6 shadow-lg">
        <label className="flex flex-col gap-1 text-sm">
          Project name
          <input
            value={projectName}
            onChange={(e) => setProjectName(e.target.value)}
            className="rounded-md border border-ink/15 bg-surface px-3 py-2 text-sm outline-none focus:border-trace"
          />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          Background
          <textarea
            value={background}
            onChange={(e) => setBackground(e.target.value)}
            rows={3}
            placeholder="What business problem is driving this project?"
            className="rounded-md border border-ink/15 bg-surface px-3 py-2 text-sm outline-none focus:border-trace"
          />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          Objectives
          <textarea
            value={objectives}
            onChange={(e) => setObjectives(e.target.value)}
            rows={2}
            placeholder="What should this project achieve?"
            className="rounded-md border border-ink/15 bg-surface px-3 py-2 text-sm outline-none focus:border-trace"
          />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          Target users
          <input
            value={targetUsers}
            onChange={(e) => setTargetUsers(e.target.value)}
            placeholder="Who will use this?"
            className="rounded-md border border-ink/15 bg-surface px-3 py-2 text-sm outline-none focus:border-trace"
          />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          Key features
          <textarea
            value={keyFeatures}
            onChange={(e) => setKeyFeatures(e.target.value)}
            rows={3}
            placeholder="What capabilities do you want, in your own words?"
            className="rounded-md border border-ink/15 bg-surface px-3 py-2 text-sm outline-none focus:border-trace"
          />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          Constraints <span className="text-ink/40">(optional)</span>
          <textarea
            value={constraints}
            onChange={(e) => setConstraints(e.target.value)}
            rows={2}
            placeholder="Budget, timeline, technology, or regulatory constraints"
            className="rounded-md border border-ink/15 bg-surface px-3 py-2 text-sm outline-none focus:border-trace"
          />
        </label>
        <button
          type="submit"
          disabled={generating}
          className="mt-2 self-start rounded-md bg-accent px-6 py-3 text-sm font-semibold text-white hover:opacity-90 disabled:opacity-60"
        >
          {generating ? "Generating…" : "Generate BRD"}
        </button>
        {generateError && <p className="text-sm text-red-700">{generateError}</p>}
      </form>

      {current && (
        <section className="mt-8">
          <div className="mb-3 flex items-center justify-between gap-2">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-ink/50">Generated BRD</h2>
            <div className="flex items-center gap-2">
              <button
                onClick={() =>
                  downloadMarkdown(
                    `brd-${current.inputs.project_name}.md`,
                    brdToMarkdown(current.content, current.inputs.project_name)
                  )
                }
                className="text-xs text-trace hover:underline"
              >
                Export as Markdown
              </button>
              <button
                onClick={() => downloadBrdPdf(`brd-${current.inputs.project_name}.pdf`, current.content, current.inputs.project_name)}
                className="text-xs text-trace hover:underline"
              >
                Export as PDF
              </button>
            </div>
          </div>
          <BrdView brd={current.content} />
        </section>
      )}

      <section className="mt-10">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-ink/50">Previously generated</h2>
        {loadError && <p className="text-sm text-red-700">{loadError}</p>}
        {deleteError && <p className="mb-2 text-sm text-red-700">{deleteError}</p>}
        {history === null ? (
          <p className="text-sm text-ink/60">Loading…</p>
        ) : history.length === 0 ? (
          <p className="text-sm text-ink/60">No BRDs generated yet for this project.</p>
        ) : (
          <ul className="flex flex-col gap-2">
            {history.map((doc) => (
              <li
                key={doc.id}
                className="flex items-center justify-between gap-3 rounded-lg border border-ink/10 bg-surface px-4 py-3 transition-colors hover:border-trace text-sm"
              >
                <button
                  onClick={() => setCurrent(doc)}
                  className="min-w-0 flex-1 truncate text-left text-ink hover:text-trace"
                >
                  {doc.inputs.project_name}
                </button>
                <div className="flex shrink-0 items-center gap-3">
                  <span className="text-xs text-ink/40">{new Date(doc.created_at).toLocaleString()}</span>
                  <button onClick={() => handleDelete(doc.id)} className="text-xs text-ink/50 hover:text-red-700">
                    Delete
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
      </div>
    </main>
  );
}
