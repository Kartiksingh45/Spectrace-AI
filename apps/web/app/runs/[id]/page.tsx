"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { TopNav } from "@/components/TopNav";
import { api, ApiError, Decision, GeneratedPlan, Run } from "@/lib/api";

function planToMarkdown(plan: GeneratedPlan): string {
  const lines: string[] = [];
  lines.push(`# ${plan.summary}`, "");
  lines.push(`**Request type:** ${plan.request_type}  `, `**Confidence:** ${plan.confidence}`, "");

  if (plan.questions.length > 0) {
    lines.push("## Open questions", ...plan.questions.map((q) => `- ${q}`), "");
  }

  lines.push("## User story", plan.user_story, "");

  if (plan.acceptance_criteria.length > 0) {
    lines.push("## Acceptance criteria", ...plan.acceptance_criteria.map((c) => `- ${c}`), "");
  }

  if (plan.affected_files.length > 0) {
    lines.push(
      "## Affected files",
      ...plan.affected_files.map((f) => `- \`${f.file_path}\` — ${f.reason} (${f.confidence})`),
      ""
    );
  }

  if (plan.tasks.length > 0) {
    lines.push("## Tasks", ...plan.tasks.map((t) => `- [${t.category}] ${t.description}`), "");
  }

  if (plan.test_cases.length > 0) {
    lines.push("## Test cases", ...plan.test_cases.map((t) => `- **${t.kind}:** ${t.description}`), "");
  }

  if (plan.assumptions.length > 0) {
    lines.push("## Assumptions", ...plan.assumptions.map((a) => `- ${a}`), "");
  }

  if (plan.risks.length > 0) {
    lines.push("## Risks", ...plan.risks.map((r) => `- ${r}`), "");
  }

  if (plan.evidence.length > 0) {
    lines.push("## Cited evidence", ...plan.evidence.map((e) => `- \`${e.chunk_id}\`: ${e.note}`), "");
  }

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

async function downloadPdf(filename: string, plan: GeneratedPlan) {
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
  doc.text(plan.summary, margin, y, { maxWidth });
  y += 26;
  doc.setFont("helvetica", "normal").setFontSize(10);
  paragraph(`Request type: ${plan.request_type}    Confidence: ${plan.confidence}`);

  if (plan.questions.length > 0) {
    heading("Open questions");
    bullets(plan.questions);
  }

  heading("User story");
  paragraph(plan.user_story);

  if (plan.acceptance_criteria.length > 0) {
    heading("Acceptance criteria");
    bullets(plan.acceptance_criteria);
  }

  if (plan.affected_files.length > 0) {
    heading("Affected files");
    bullets(plan.affected_files.map((f) => `${f.file_path} — ${f.reason} (${f.confidence})`));
  }

  if (plan.tasks.length > 0) {
    heading("Tasks");
    bullets(plan.tasks.map((t) => `[${t.category}] ${t.description}`));
  }

  if (plan.test_cases.length > 0) {
    heading("Test cases");
    bullets(plan.test_cases.map((t) => `${t.kind}: ${t.description}`));
  }

  if (plan.assumptions.length > 0) {
    heading("Assumptions");
    bullets(plan.assumptions);
  }

  if (plan.risks.length > 0) {
    heading("Risks");
    bullets(plan.risks);
  }

  if (plan.evidence.length > 0) {
    heading("Cited evidence");
    bullets(plan.evidence.map((e) => `${e.chunk_id}: ${e.note}`));
  }

  doc.save(filename);
}

function linesOf(text: string): string[] {
  return text
    .split("\n")
    .map((l) => l.trim())
    .filter(Boolean);
}

// Structured list fields (affected files, tasks, test cases) are edited as one "a | b | c" line
// per item rather than a full dynamic add/remove-row builder - simpler to build and to use for
// tweaking a few fields than reconstructing the whole plan from scratch.
function parseAffectedFiles(text: string): GeneratedPlan["affected_files"] {
  return linesOf(text).map((line) => {
    const [file_path, reason, confidence] = line.split("|").map((s) => s.trim());
    const conf = confidence?.toLowerCase();
    return {
      file_path: file_path || "",
      reason: reason || "",
      confidence: conf === "high" || conf === "medium" || conf === "low" ? conf : "low",
    };
  });
}

function parseTasks(text: string): GeneratedPlan["tasks"] {
  const allowed = ["frontend", "backend", "database", "testing", "documentation"] as const;
  return linesOf(text).map((line) => {
    const [category, description] = line.split("|").map((s) => s.trim());
    const cat = category?.toLowerCase();
    return {
      category: (allowed as readonly string[]).includes(cat ?? "") ? (cat as (typeof allowed)[number]) : "frontend",
      description: description || "",
    };
  });
}

function parseTestCases(text: string): GeneratedPlan["test_cases"] {
  const allowed = ["positive", "negative", "boundary", "permission", "regression"] as const;
  return linesOf(text).map((line) => {
    const [kind, description] = line.split("|").map((s) => s.trim());
    const k = kind?.toLowerCase();
    return {
      kind: (allowed as readonly string[]).includes(k ?? "") ? (k as (typeof allowed)[number]) : "positive",
      description: description || "",
    };
  });
}

const STATUS_LABEL: Record<string, string> = {
  pending: "Pending",
  analysing: "Analysing…",
  awaiting_clarification: "Waiting on your answer",
  awaiting_approval: "Ready for review",
  running: "Running…",
  completed: "Completed",
  failed: "Failed",
};

function ConfidenceBadge({ confidence }: { confidence: string }) {
  const styles: Record<string, string> = {
    high: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300",
    medium: "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300",
    low: "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300",
  };
  return (
    <span className={`rounded-full px-2 py-1 text-xs font-medium ${styles[confidence] ?? "bg-ink/10"}`}>
      {confidence} confidence
    </span>
  );
}

export default function RunDetailPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const runId = params.id;

  const [run, setRun] = useState<Run | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [answer, setAnswer] = useState("");
  const [submittingAnswer, setSubmittingAnswer] = useState(false);

  const [feedback, setFeedback] = useState("");
  const [submittingDecision, setSubmittingDecision] = useState<Decision | null>(null);

  const [isEditing, setIsEditing] = useState(false);
  const [editSummary, setEditSummary] = useState("");
  const [editUserStory, setEditUserStory] = useState("");
  const [editConfidence, setEditConfidence] = useState<"high" | "medium" | "low">("medium");
  const [editAcceptanceCriteria, setEditAcceptanceCriteria] = useState("");
  const [editAffectedFiles, setEditAffectedFiles] = useState("");
  const [editTasks, setEditTasks] = useState("");
  const [editTestCases, setEditTestCases] = useState("");
  const [editAssumptions, setEditAssumptions] = useState("");
  const [editRisks, setEditRisks] = useState("");
  const [editError, setEditError] = useState<string | null>(null);

  async function load(): Promise<Run | undefined> {
    try {
      const data = await api.getRun(runId);
      setRun(data);
      return data;
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        router.replace("/sign-in");
      } else {
        setError("Could not load this run.");
      }
      return undefined;
    }
  }

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;

    // The agent now executes in the background (a full run can take over a minute, longer than
    // many hosts' proxy timeout), so this page polls while a run is actively in progress rather
    // than assuming the one initial fetch already reflects the final state.
    async function poll() {
      const data = await load();
      if (!cancelled && data?.status === "running") {
        timer = setTimeout(poll, 2000);
      }
    }
    poll();

    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runId]);

  async function handleAnswer(e: React.FormEvent) {
    e.preventDefault();
    if (!answer.trim()) return;
    setSubmittingAnswer(true);
    try {
      const updated = await api.answerClarification(runId, answer.trim());
      setRun(updated);
      setAnswer("");
    } catch {
      setError("Could not submit that answer.");
    } finally {
      setSubmittingAnswer(false);
    }
  }

  async function handleDecision(decision: Decision) {
    if (!run?.plan_id) return;
    setSubmittingDecision(decision);
    try {
      const updated = await api.submitDecision(run.plan_id, decision, feedback.trim() || undefined);
      setRun(updated);
      setFeedback("");
    } catch {
      setError("Could not submit that decision.");
    } finally {
      setSubmittingDecision(null);
    }
  }

  function startEditing() {
    const plan = run?.generated_plan;
    if (!plan) return;
    setEditSummary(plan.summary);
    setEditUserStory(plan.user_story);
    setEditConfidence(plan.confidence);
    setEditAcceptanceCriteria(plan.acceptance_criteria.join("\n"));
    setEditAffectedFiles(plan.affected_files.map((f) => `${f.file_path} | ${f.reason} | ${f.confidence}`).join("\n"));
    setEditTasks(plan.tasks.map((t) => `${t.category} | ${t.description}`).join("\n"));
    setEditTestCases(plan.test_cases.map((t) => `${t.kind} | ${t.description}`).join("\n"));
    setEditAssumptions(plan.assumptions.join("\n"));
    setEditRisks(plan.risks.join("\n"));
    setEditError(null);
    setIsEditing(true);
  }

  async function handleSaveAndApprove() {
    const plan = run?.generated_plan;
    if (!plan || !run?.plan_id) return;
    setSubmittingDecision("edit_approved");
    setEditError(null);
    try {
      const finalContent: GeneratedPlan = {
        ...plan,
        summary: editSummary,
        user_story: editUserStory,
        confidence: editConfidence,
        acceptance_criteria: linesOf(editAcceptanceCriteria),
        affected_files: parseAffectedFiles(editAffectedFiles),
        tasks: parseTasks(editTasks),
        test_cases: parseTestCases(editTestCases),
        assumptions: linesOf(editAssumptions),
        risks: linesOf(editRisks),
      };
      const updated = await api.submitDecision(run.plan_id, "edit_approved", feedback.trim() || undefined, finalContent);
      setRun(updated);
      setFeedback("");
      setIsEditing(false);
    } catch (err) {
      setEditError(err instanceof ApiError ? err.message : "Could not save your edits.");
    } finally {
      setSubmittingDecision(null);
    }
  }

  if (!run) {
    return (
      <main className="mx-auto max-w-2xl px-4 py-12">
        <p className="text-sm text-ink/60">{error ?? "Loading…"}</p>
      </main>
    );
  }

  const plan = run.generated_plan;

  return (
    <main className="mx-auto max-w-2xl px-4 py-12">
      <TopNav />
      <Link href="/dashboard" className="text-sm text-trace">
        ← All projects
      </Link>
      <div className="mt-2 flex items-center justify-between">
        <h1 className="font-serif text-2xl font-semibold text-ink">Analysis run</h1>
        <span className="rounded-full bg-ink/10 px-3 py-1 text-xs font-medium text-ink/70">
          {STATUS_LABEL[run.status] ?? run.status}
        </span>
      </div>

      {error && <p className="mt-4 text-sm text-red-700">{error}</p>}

      <section className="mt-8">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-ink/50">Timeline</h2>
        <div className="border-l-2 border-ink/10 pl-4">
          {run.steps.map((step) => (
            <div key={step.step_index} className="mb-3 text-sm">
              <p className="font-medium text-ink">{step.tool_name ?? "classify"}</p>
              <p className="text-ink/60">{step.output_summary}</p>
            </div>
          ))}
        </div>
      </section>

      {run.status === "awaiting_clarification" && (
        <section className="mt-8 rounded-md border border-amber-200 bg-amber-50 p-4 dark:border-amber-900/50 dark:bg-amber-900/20">
          <p className="mb-3 text-sm font-medium text-ink">{run.pending_question}</p>
          <form onSubmit={handleAnswer} className="flex gap-2">
            <input
              id="clarification-answer"
              value={answer}
              onChange={(e) => setAnswer(e.target.value)}
              placeholder="Your answer"
              className="flex-1 rounded-md border border-ink/15 bg-surface px-3 py-2 text-sm outline-none focus:border-trace"
            />
            <button
              type="submit"
              disabled={submittingAnswer}
              className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
            >
              Submit
            </button>
          </form>
        </section>
      )}

      {plan && (
        <section className="mt-8">
          <div className="mb-3 flex items-center justify-between gap-2">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-ink/50">Generated plan</h2>
            <div className="flex items-center gap-2">
              <button
                onClick={() => downloadMarkdown(`spectrace-plan-${runId}.md`, planToMarkdown(plan))}
                className="text-xs text-trace hover:underline"
              >
                Export as Markdown
              </button>
              <button
                onClick={() => downloadPdf(`spectrace-plan-${runId}.pdf`, plan)}
                className="text-xs text-trace hover:underline"
              >
                Export as PDF
              </button>
              <ConfidenceBadge confidence={plan.confidence} />
            </div>
          </div>

          <div className="flex flex-col gap-4 rounded-md border border-ink/10 bg-surface p-5 text-sm">
            <p className="text-ink">{plan.summary}</p>

            <div>
              <p className="font-medium text-ink">User story</p>
              <p className="text-ink/70">{plan.user_story}</p>
            </div>

            {plan.acceptance_criteria.length > 0 && (
              <div>
                <p className="font-medium text-ink">Acceptance criteria</p>
                <ul className="list-disc pl-5 text-ink/70">
                  {plan.acceptance_criteria.map((c, i) => (
                    <li key={i}>{c}</li>
                  ))}
                </ul>
              </div>
            )}

            {plan.affected_files.length > 0 && (
              <div>
                <p className="font-medium text-ink">Affected files</p>
                <ul className="flex flex-col gap-1 text-ink/70">
                  {plan.affected_files.map((f, i) => (
                    <li key={i}>
                      <span className="font-mono text-xs">{f.file_path}</span> — {f.reason} ({f.confidence})
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {plan.test_cases.length > 0 && (
              <div>
                <p className="font-medium text-ink">Test cases</p>
                <ul className="flex flex-col gap-1 text-ink/70">
                  {plan.test_cases.map((t, i) => (
                    <li key={i}>
                      <span className="text-xs uppercase text-ink/40">{t.kind}</span> {t.description}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {plan.risks.length > 0 && (
              <div>
                <p className="font-medium text-ink">Risks</p>
                <ul className="list-disc pl-5 text-ink/70">
                  {plan.risks.map((r, i) => (
                    <li key={i}>{r}</li>
                  ))}
                </ul>
              </div>
            )}

            {plan.evidence.length > 0 && (
              <div>
                <p className="font-medium text-ink">Cited evidence</p>
                <ul className="flex flex-col gap-1 text-xs text-ink/50">
                  {plan.evidence.map((e, i) => (
                    <li key={i} className="font-mono">
                      [{e.chunk_id}] {e.note}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          {run.status === "awaiting_approval" && !isEditing && (
            <div className="mt-4 flex flex-col gap-3">
              <textarea
                id="decision-feedback"
                value={feedback}
                onChange={(e) => setFeedback(e.target.value)}
                placeholder="Optional feedback (used for regenerate, or noted alongside your decision)"
                className="rounded-md border border-ink/15 bg-surface px-3 py-2 text-sm outline-none focus:border-trace"
                rows={2}
              />
              <div className="flex flex-wrap gap-2">
                <button
                  onClick={() => handleDecision("approved")}
                  disabled={submittingDecision !== null}
                  className="rounded-md bg-emerald-600 px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
                >
                  Approve
                </button>
                <button
                  onClick={startEditing}
                  disabled={submittingDecision !== null}
                  className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
                >
                  Edit &amp; approve
                </button>
                <button
                  onClick={() => handleDecision("regenerate_requested")}
                  disabled={submittingDecision !== null}
                  className="rounded-md border border-ink/20 px-4 py-2 text-sm font-medium text-ink disabled:opacity-60"
                >
                  Request changes
                </button>
                <button
                  onClick={() => handleDecision("rejected")}
                  disabled={submittingDecision !== null}
                  className="rounded-md border border-red-200 px-4 py-2 text-sm font-medium text-red-700 disabled:opacity-60 dark:border-red-900/50 dark:text-red-400"
                >
                  Reject
                </button>
              </div>
            </div>
          )}

          {run.status === "awaiting_approval" && isEditing && (
            <div className="mt-4 flex flex-col gap-3 rounded-md border border-trace/30 bg-surface p-4">
              <p className="text-xs text-ink/50">
                Edit the plan below, then save. For affected files, tasks, and test cases, put one
                item per line in the format shown in each field&apos;s placeholder.
              </p>
              <label className="flex flex-col gap-1 text-sm">
                Summary
                <textarea
                  value={editSummary}
                  onChange={(e) => setEditSummary(e.target.value)}
                  rows={2}
                  className="rounded-md border border-ink/15 bg-surface px-3 py-2 text-sm outline-none focus:border-trace"
                />
              </label>
              <label className="flex flex-col gap-1 text-sm">
                User story
                <textarea
                  value={editUserStory}
                  onChange={(e) => setEditUserStory(e.target.value)}
                  rows={2}
                  className="rounded-md border border-ink/15 bg-surface px-3 py-2 text-sm outline-none focus:border-trace"
                />
              </label>
              <label className="flex flex-col gap-1 text-sm">
                Confidence
                <select
                  value={editConfidence}
                  onChange={(e) => setEditConfidence(e.target.value as "high" | "medium" | "low")}
                  className="rounded-md border border-ink/15 bg-surface px-3 py-2 text-sm text-ink"
                >
                  <option value="high">High</option>
                  <option value="medium">Medium</option>
                  <option value="low">Low</option>
                </select>
              </label>
              <label className="flex flex-col gap-1 text-sm">
                Acceptance criteria (one per line)
                <textarea
                  value={editAcceptanceCriteria}
                  onChange={(e) => setEditAcceptanceCriteria(e.target.value)}
                  rows={3}
                  className="rounded-md border border-ink/15 bg-surface px-3 py-2 text-sm outline-none focus:border-trace"
                />
              </label>
              <label className="flex flex-col gap-1 text-sm">
                Affected files (one per line: path | reason | high/medium/low)
                <textarea
                  value={editAffectedFiles}
                  onChange={(e) => setEditAffectedFiles(e.target.value)}
                  placeholder="src/pages/Login.tsx | Add captcha widget | high"
                  rows={3}
                  className="rounded-md border border-ink/15 bg-surface px-3 py-2 text-sm outline-none focus:border-trace"
                />
              </label>
              <label className="flex flex-col gap-1 text-sm">
                Tasks (one per line: frontend/backend/database/testing/documentation | description)
                <textarea
                  value={editTasks}
                  onChange={(e) => setEditTasks(e.target.value)}
                  placeholder="backend | Verify captcha token before password check"
                  rows={3}
                  className="rounded-md border border-ink/15 bg-surface px-3 py-2 text-sm outline-none focus:border-trace"
                />
              </label>
              <label className="flex flex-col gap-1 text-sm">
                Test cases (one per line: positive/negative/boundary/permission/regression | description)
                <textarea
                  value={editTestCases}
                  onChange={(e) => setEditTestCases(e.target.value)}
                  placeholder="negative | Login fails when captcha token is missing"
                  rows={3}
                  className="rounded-md border border-ink/15 bg-surface px-3 py-2 text-sm outline-none focus:border-trace"
                />
              </label>
              <label className="flex flex-col gap-1 text-sm">
                Assumptions (one per line)
                <textarea
                  value={editAssumptions}
                  onChange={(e) => setEditAssumptions(e.target.value)}
                  rows={2}
                  className="rounded-md border border-ink/15 bg-surface px-3 py-2 text-sm outline-none focus:border-trace"
                />
              </label>
              <label className="flex flex-col gap-1 text-sm">
                Risks (one per line)
                <textarea
                  value={editRisks}
                  onChange={(e) => setEditRisks(e.target.value)}
                  rows={2}
                  className="rounded-md border border-ink/15 bg-surface px-3 py-2 text-sm outline-none focus:border-trace"
                />
              </label>
              <textarea
                value={feedback}
                onChange={(e) => setFeedback(e.target.value)}
                placeholder="Optional feedback (noted alongside your decision)"
                className="rounded-md border border-ink/15 bg-surface px-3 py-2 text-sm outline-none focus:border-trace"
                rows={2}
              />
              {editError && <p className="text-sm text-red-700">{editError}</p>}
              <div className="flex flex-wrap gap-2">
                <button
                  onClick={handleSaveAndApprove}
                  disabled={submittingDecision !== null}
                  className="rounded-md bg-emerald-600 px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
                >
                  {submittingDecision === "edit_approved" ? "Saving…" : "Save & approve"}
                </button>
                <button
                  onClick={() => setIsEditing(false)}
                  disabled={submittingDecision !== null}
                  className="rounded-md border border-ink/20 px-4 py-2 text-sm font-medium text-ink disabled:opacity-60"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}
        </section>
      )}
    </main>
  );
}
