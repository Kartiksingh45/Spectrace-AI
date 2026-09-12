"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import {
  api,
  ApiError,
  EvaluationBehavior,
  EvaluationCase,
  EvaluationCategory,
  EvaluationReport,
  EvaluationResult,
} from "@/lib/api";

const CATEGORY_LABEL: Record<EvaluationCategory, string> = {
  clear: "Clear",
  cross_source: "Cross-source",
  ambiguous: "Ambiguous",
  unsupported: "Unsupported",
};

const BEHAVIOR_LABEL: Record<EvaluationBehavior, string> = {
  direct_answer: "Direct answer",
  clarification: "Clarification",
  insufficient_evidence: "Insufficient evidence",
  failed: "Failed",
};

function Metric({ label, value }: { label: string; value: number | null }) {
  return (
    <div className="rounded-md border border-ink/10 bg-white p-4">
      <p className="text-xs font-medium uppercase tracking-wide text-ink/50">{label}</p>
      <p className="mt-1 text-xl font-semibold text-ink">
        {value === null ? "—" : `${Math.round(value * 100)}%`}
      </p>
    </div>
  );
}

export default function EvaluationPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const projectId = params.id;

  const [cases, setCases] = useState<EvaluationCase[]>([]);
  const [report, setReport] = useState<EvaluationReport | null>(null);
  const [results, setResults] = useState<EvaluationResult[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [title, setTitle] = useState("");
  const [requestText, setRequestText] = useState("");
  const [category, setCategory] = useState<EvaluationCategory>("clear");
  const [expectedBehavior, setExpectedBehavior] = useState<EvaluationBehavior>("direct_answer");
  const [expectedSources, setExpectedSources] = useState("");
  const [expectedAffectedFiles, setExpectedAffectedFiles] = useState("");
  const [creating, setCreating] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const [running, setRunning] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);

  async function loadAll() {
    try {
      const [caseList, latestReport] = await Promise.all([
        api.listEvaluationCases(projectId),
        api.getEvaluationReport(projectId),
      ]);
      setCases(caseList);
      setReport(latestReport);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        router.push("/sign-in");
      } else {
        setLoadError("Could not load the evaluation dataset.");
      }
    }
  }

  useEffect(() => {
    loadAll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  async function handleCreateCase(e: React.FormEvent) {
    e.preventDefault();
    if (!title.trim() || !requestText.trim()) return;
    setCreating(true);
    setFormError(null);
    try {
      await api.createEvaluationCase(projectId, {
        title: title.trim(),
        request_text: requestText.trim(),
        category,
        expected_behavior: expectedBehavior,
        expected_sources: expectedSources
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean),
        expected_affected_files: expectedAffectedFiles
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean),
      });
      setTitle("");
      setRequestText("");
      setExpectedSources("");
      setExpectedAffectedFiles("");
      await loadAll();
    } catch {
      setFormError("Could not add that case.");
    } finally {
      setCreating(false);
    }
  }

  async function handleDeleteCase(caseId: string) {
    await api.deleteEvaluationCase(projectId, caseId);
    setCases((prev) => prev.filter((c) => c.id !== caseId));
  }

  async function handleRun() {
    setRunning(true);
    setRunError(null);
    try {
      const runResults = await api.runEvaluation(projectId);
      setResults(runResults);
      setReport(await api.getEvaluationReport(projectId));
    } catch {
      setRunError("The evaluation run failed. Check the API logs for details.");
    } finally {
      setRunning(false);
    }
  }

  return (
    <main className="mx-auto max-w-3xl px-4 py-12">
      <Link href={`/projects/${projectId}`} className="text-sm text-trace">
        ← Back to project
      </Link>
      <h1 className="mt-2 font-serif text-2xl font-semibold text-ink">Evaluation</h1>
      <p className="mt-1 text-sm text-ink/60">
        BRD Section 14 test dataset: at least 15 cases across clear, cross-source, ambiguous, and
        unsupported requests, with measured retrieval and generation quality metrics.
      </p>

      {loadError && <p className="mt-4 text-sm text-red-700">{loadError}</p>}

      <section className="mt-8">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-ink/50">Report</h2>
          <button
            onClick={handleRun}
            disabled={running || cases.length === 0}
            className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
          >
            {running ? "Running…" : "Run evaluation"}
          </button>
        </div>
        {runError && <p className="mb-3 text-sm text-red-700">{runError}</p>}
        {report && (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
            <Metric label="Overall pass rate" value={report.overall_pass_rate} />
            <Metric label="Retrieval hit rate" value={report.retrieval_hit_rate} />
            <Metric label="Affected file precision" value={report.affected_file_precision} />
            <Metric label="Citation correctness" value={report.citation_correctness} />
            <Metric label="Clarification accuracy" value={report.clarification_accuracy} />
            <Metric label="Unsupported claim rate" value={report.unsupported_claim_rate} />
            <Metric label="Reviewer acceptance" value={report.reviewer_acceptance} />
          </div>
        )}
        {report && (report.median_latency_ms !== null || report.max_latency_ms !== null) && (
          <p className="mt-2 text-xs text-ink/50">
            Median latency {report.median_latency_ms} ms · Slowest {report.max_latency_ms} ms ·{" "}
            {report.total_results}/{report.total_cases} cases have a result
          </p>
        )}
      </section>

      {results && (
        <section className="mt-8">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-ink/50">
            Latest run results
          </h2>
          <ul className="flex flex-col gap-2">
            {results.map((r) => (
              <li
                key={r.id}
                className="rounded-md border border-ink/10 bg-white p-3 text-sm"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className={r.passed ? "text-emerald-700" : "text-red-700"}>
                    {r.passed ? "Passed" : "Failed"}
                  </span>
                  <span className="text-xs text-ink/50">{BEHAVIOR_LABEL[r.actual_behavior]}</span>
                </div>
                {r.notes && <p className="mt-1 text-xs text-ink/60">{r.notes}</p>}
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="mt-8">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-ink/50">
          Add a test case
        </h2>
        <form onSubmit={handleCreateCase} className="flex flex-col gap-2 rounded-md border border-ink/10 bg-white p-4">
          <input
            placeholder="Title"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className="rounded-md border border-ink/15 px-3 py-2 text-sm outline-none focus:border-trace"
          />
          <textarea
            placeholder="Change request text, e.g. Make mobile OTP verification mandatory before loan submission."
            value={requestText}
            onChange={(e) => setRequestText(e.target.value)}
            rows={2}
            className="rounded-md border border-ink/15 px-3 py-2 text-sm outline-none focus:border-trace"
          />
          <div className="flex flex-col gap-2 sm:flex-row">
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value as EvaluationCategory)}
              className="flex-1 rounded-md border border-ink/15 px-3 py-2 text-sm"
            >
              {Object.entries(CATEGORY_LABEL).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
            <select
              value={expectedBehavior}
              onChange={(e) => setExpectedBehavior(e.target.value as EvaluationBehavior)}
              className="flex-1 rounded-md border border-ink/15 px-3 py-2 text-sm"
            >
              {Object.entries(BEHAVIOR_LABEL)
                .filter(([value]) => value !== "failed")
                .map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
            </select>
          </div>
          <input
            placeholder="Expected sources (comma-separated file paths, optional)"
            value={expectedSources}
            onChange={(e) => setExpectedSources(e.target.value)}
            className="rounded-md border border-ink/15 px-3 py-2 text-sm outline-none focus:border-trace"
          />
          <input
            placeholder="Expected affected files (comma-separated, optional)"
            value={expectedAffectedFiles}
            onChange={(e) => setExpectedAffectedFiles(e.target.value)}
            className="rounded-md border border-ink/15 px-3 py-2 text-sm outline-none focus:border-trace"
          />
          <button
            type="submit"
            disabled={creating}
            className="self-start rounded-md bg-accent px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
          >
            {creating ? "Adding…" : "Add case"}
          </button>
          {formError && <p className="text-sm text-red-700">{formError}</p>}
        </form>
      </section>

      <section className="mt-8">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-ink/50">
          Dataset ({cases.length})
        </h2>
        {cases.length === 0 ? (
          <p className="text-sm text-ink/60">
            No test cases yet. The BRD requires at least 15: 6 clear, 4 cross-source, 3 ambiguous, 2
            unsupported.
          </p>
        ) : (
          <ul className="flex flex-col gap-2">
            {cases.map((c) => (
              <li
                key={c.id}
                className="flex items-start justify-between gap-3 rounded-md border border-ink/10 bg-white p-3 text-sm"
              >
                <div className="min-w-0">
                  <p className="font-medium text-ink">{c.title}</p>
                  <p className="text-xs text-ink/50">
                    {CATEGORY_LABEL[c.category]} · expects {BEHAVIOR_LABEL[c.expected_behavior]}
                  </p>
                </div>
                <button
                  onClick={() => handleDeleteCase(c.id)}
                  className="shrink-0 text-xs text-ink/50 hover:text-red-700"
                >
                  Delete
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}
