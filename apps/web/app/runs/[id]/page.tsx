"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, ApiError, Decision, Run } from "@/lib/api";

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
    high: "bg-emerald-100 text-emerald-800",
    medium: "bg-amber-100 text-amber-800",
    low: "bg-red-100 text-red-800",
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

  async function load() {
    try {
      const data = await api.getRun(runId);
      setRun(data);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        router.push("/sign-in");
      } else {
        setError("Could not load this run.");
      }
    }
  }

  useEffect(() => {
    load();
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
        <section className="mt-8 rounded-md border border-amber-200 bg-amber-50 p-4">
          <p className="mb-3 text-sm font-medium text-ink">{run.pending_question}</p>
          <form onSubmit={handleAnswer} className="flex gap-2">
            <input
              id="clarification-answer"
              value={answer}
              onChange={(e) => setAnswer(e.target.value)}
              placeholder="Your answer"
              className="flex-1 rounded-md border border-ink/15 bg-white px-3 py-2 text-sm outline-none focus:border-trace"
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
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-ink/50">Generated plan</h2>
            <ConfidenceBadge confidence={plan.confidence} />
          </div>

          <div className="flex flex-col gap-4 rounded-md border border-ink/10 bg-white p-5 text-sm">
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

          {run.status === "awaiting_approval" && (
            <div className="mt-4 flex flex-col gap-3">
              <textarea
                id="decision-feedback"
                value={feedback}
                onChange={(e) => setFeedback(e.target.value)}
                placeholder="Optional feedback (used for regenerate, or noted alongside your decision)"
                className="rounded-md border border-ink/15 bg-white px-3 py-2 text-sm outline-none focus:border-trace"
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
                  onClick={() => handleDecision("edit_approved")}
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
                  className="rounded-md border border-red-200 px-4 py-2 text-sm font-medium text-red-700 disabled:opacity-60"
                >
                  Reject
                </button>
              </div>
            </div>
          )}
        </section>
      )}
    </main>
  );
}
