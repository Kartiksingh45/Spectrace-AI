"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { TopNav } from "@/components/TopNav";
import { api, ApiError } from "@/lib/api";

type Step = { title: string; body: string; points?: string[] };

const STEPS: Step[] = [
  {
    title: "1. Create a project",
    body:
      "A project is the container for everything - every requirement doc, codebase, change " +
      "request, and analysis run lives inside one project, and one project can never see " +
      "another's content. Create one from the Projects page (the \"Projects\" link in the top " +
      "nav), give it a name, and open it to reach its workspace.",
    points: [
      "Use a separate project per real codebase - don't mix two unrelated codebases into one project, since the agent searches across everything uploaded to that project.",
      "Opening the app (or signing in) automatically drops you back into whichever project you last had open, so you don't have to hunt for it each time. Use \"Projects\" in the nav to switch to a different one.",
    ],
  },
  {
    title: "2. Upload requirement docs and your codebase",
    body:
      "Both uploads happen from the \"Upload\" section of a project's workspace page. Requirement " +
      "documents (PDF, TXT, or Markdown) describe what a feature should do; the codebase is your " +
      "actual source code, which the agent searches to find where to make changes.",
    points: [
      "Five ways to add a codebase: the plain \"Choose file\" + \"Add codebase\" button for a .zip you already made; \"Add codebase folder\" to pick a folder directly (it's zipped in your browser first); dragging a file, .zip, or folder onto the dashed drop zone; copying a file/folder and pasting with Ctrl+V anywhere on the page; or \"Import from GitHub\" (owner/repo/branch) to pull a public repository directly - read-only, no write access is ever requested.",
      "Whichever method you use, junk like node_modules, .git, __pycache__, venv, dist, build, and .next is automatically filtered out before upload, along with anything that isn't a .py/.js/.jsx/.ts/.tsx file - so uploading a whole real project folder is safe and won't blow past size limits.",
      "Each uploaded document shows a status: uploaded, processing, ready, or failed (with an error message if it failed). Only \"ready\" documents are actually searchable.",
      "Re-uploading a requirement document with the same filename doesn't overwrite it - it's kept as a new version, and a \"Compare with previous version\" link appears so you can see exactly what changed (a line-by-line diff) between the two.",
      "Click \"Delete\" next to a document to remove it and every chunk that came from it - useful if you uploaded the wrong folder or want to swap in an updated version.",
    ],
  },
  {
    title: "3. Try semantic search",
    body:
      "Once documents are \"ready\", use the Semantic Search box to test what the agent will " +
      "actually find for a given query - this is the same retrieval the agent uses internally, " +
      "exposed directly so you can sanity-check it without spending an LLM call.",
    points: [
      "Filter by \"Requirements\", \"Code\", or \"All content\" to narrow where it searches.",
      "Each result shows its real location (file path, and for code, the function/class name and line range) plus a relevance score from 0 to 1 - higher means a closer semantic match, not a guarantee of correctness.",
      "Ranking is hybrid, not pure vector similarity: results are blended with a lexical keyword-overlap score and then reordered by a cross-encoder reranker, so an exact identifier or error-code match doesn't get buried under a paraphrased-but-less-relevant chunk.",
      "If a search for a term you expect to match comes back empty or with only low scores, that's a preview of the same gap the full agent will hit - a good way to debug \"why didn't it find X\" before running a whole analysis.",
    ],
  },
  {
    title: "4. Check Previous analyses before starting a new one",
    body:
      "Every change request you've ever submitted to a project is listed under \"Previous " +
      "analyses\" on the workspace page - its status, a preview of the generated plan's summary, " +
      "and its confidence level, each linking straight to that run's full detail page.",
    points: [
      "Nothing is ever lost once a run completes - this list is exactly how you get back to a past result without needing to have bookmarked its URL.",
      "Status badges: Pending, Analysing, Waiting on answer (a clarification is pending), Ready for review, Approved, Rejected, or Failed.",
    ],
  },
  {
    title: "5. Submit a change request",
    body:
      "Describe a change in plain language in the \"New analysis\" box and click \"Analyse this " +
      "request\". This kicks off the actual agent - a multi-step process that can take anywhere " +
      "from several seconds to over a minute.",
    points: [
      "Behind the scenes it: classifies the request (feature/bug/refactor/security/performance/documentation), then repeatedly chooses between searching requirements, searching code, pulling more context around a promising result, checking similar past approved plans, asking you a clarifying question, or generating the final plan - up to a fixed step limit.",
      "A live progress list appears under the button while it runs, showing each step (search, clarification check, plan generation) as it actually happens rather than only once the whole thing finishes.",
      "For the best result, describe the change using the same words your actual code/docs use (e.g. \"sign-in\" if that's what the code calls it, not a generic synonym), and keep the request concrete and scoped rather than vague.",
      "If nothing relevant is found, the agent won't invent an answer - it either asks you a specific clarifying question or returns a low-confidence \"insufficient evidence\" result that still lists whatever weak leads it did find, rather than staying silent.",
    ],
  },
  {
    title: "6. Read the run page: Timeline and Generated plan",
    body:
      "Every run has a Timeline showing each step the agent actually took, and - once it reaches " +
      "one - a Generated plan with the full structured result.",
    points: [
      "Timeline entries are named after the tool used: classify, search_requirements, search_codebase, get_file_context, find_similar_stories, request_clarification, generate_plan - each with a short summary of what it found or did.",
      "The Generated plan includes: a summary, a confidence badge (high/medium/low), a user story, acceptance criteria, affected files (each with a reason and its own confidence), tasks grouped by area (frontend/backend/database/testing/documentation), test cases (positive/negative/boundary/permission/regression), assumptions, risks, and cited evidence - every citation points to a real chunk the agent actually retrieved during that run, never a fabricated one.",
      "\"Export as Markdown\" and \"Export as PDF\" both download the whole plan as a file you can keep, share, or attach to a ticket - independent of the app.",
    ],
  },
  {
    title: "7. Answer a clarifying question, if asked",
    body:
      "If the agent doesn't have enough information to responsibly proceed, the run pauses at " +
      "\"Waiting on your answer\" with a specific question shown at the top of the run page. Type " +
      "your answer and submit - the run then resumes exactly where it left off.",
  },
  {
    title: "8. Review and decide",
    body:
      "Once a plan is ready (\"Ready for review\"), a reviewer must approve, edit-and-approve, " +
      "reject, or ask for regeneration - a plan is never considered final on its own.",
    points: [
      "Approve: accepts the plan exactly as generated.",
      "Edit & approve: opens an editable form pre-filled with the current plan (summary, user story, confidence, acceptance criteria, affected files, tasks, test cases, assumptions, risks). For the list fields, enter one item per line in the format shown in that field's placeholder (e.g. \"path | reason | high\" for affected files). Saving replaces the plan of record everywhere - the run page, exports, and any later reference to it - with your edited version.",
      "Request changes: sends your typed feedback back to the agent, which regenerates a new version of the plan (a new version number, same run) taking that feedback into account.",
      "Reject: ends the run without approval. A rejected plan can never later be marked approved.",
      "Every decision is recorded with who made it, when, and what was decided - this is the audit trail behind \"nothing is final without a human.\"",
    ],
  },
  {
    title: "9. My Profile and Theme",
    body:
      "\"My Profile\" (top nav) shows your email, role, and member-since date, and lets you change " +
      "your password. \"Theme: Auto/Light/Dark\" in the top nav cycles the whole app's color scheme - " +
      "your choice is remembered per-browser.",
  },
];

export default function GuidePage() {
  const router = useRouter();
  const [checkingAuth, setCheckingAuth] = useState(true);

  useEffect(() => {
    api.getCurrentUser().catch((err) => {
      if (err instanceof ApiError && err.status === 401) {
        router.push("/sign-in");
      }
    }).finally(() => setCheckingAuth(false));
  }, [router]);

  if (checkingAuth) {
    return (
      <main className="mx-auto max-w-2xl px-4 py-12">
        <TopNav />
        <p className="text-sm text-ink/60">Loading…</p>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-2xl px-4 py-12">
      <TopNav />
      <h1 className="mb-2 font-serif text-2xl font-semibold text-ink">Guide</h1>
      <p className="mb-8 text-sm text-ink/60">
        A detailed walkthrough of how Spectrace AI's workflow fits together, end to end.
      </p>

      <ol className="flex flex-col gap-5">
        {STEPS.map((step) => (
          <li key={step.title} className="rounded-md border border-ink/10 bg-surface p-5">
            <h2 className="mb-1 text-sm font-semibold text-ink">{step.title}</h2>
            <p className="text-sm text-ink/70">{step.body}</p>
            {step.points && (
              <ul className="mt-2 list-disc pl-5 text-sm text-ink/70">
                {step.points.map((point, i) => (
                  <li key={i} className="mt-1">
                    {point}
                  </li>
                ))}
              </ul>
            )}
          </li>
        ))}
      </ol>
    </main>
  );
}
