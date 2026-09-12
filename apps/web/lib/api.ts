const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const isFormData = options.body instanceof FormData;
  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    credentials: "include",
    headers: {
      ...(isFormData ? {} : { "Content-Type": "application/json" }),
      ...options.headers,
    },
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new ApiError(res.status, body.detail ?? "Request failed");
  }

  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export type User = {
  id: string;
  email: string;
  role: "contributor" | "reviewer" | "administrator";
};

export type Project = {
  id: string;
  name: string;
  owner_id: string;
  created_at: string;
};

export type DocumentStatus = "uploaded" | "processing" | "ready" | "failed";

export type ProjectDocument = {
  id: string;
  kind: "requirement" | "code";
  filename: string;
  status: DocumentStatus;
  error: string | null;
  created_at: string;
};

export type SearchResult = {
  chunk_id: string;
  document_id: string;
  filename: string;
  content_type: "requirement" | "code";
  text: string;
  score: number;
  source_metadata: Record<string, unknown>;
};

export type ChangeRequest = {
  id: string;
  project_id: string;
  request_text: string;
  request_type: string | null;
  status: string;
  created_at: string;
};

export type RunStep = {
  step_index: number;
  tool_name: string | null;
  input_summary: string;
  output_summary: string;
  status: string;
};

export type EvidenceRef = { chunk_id: string; note: string };
export type AffectedFile = { file_path: string; reason: string; confidence: "high" | "medium" | "low" };
export type TaskItem = {
  category: "frontend" | "backend" | "database" | "testing" | "documentation";
  description: string;
};
export type TestCaseItem = {
  kind: "positive" | "negative" | "boundary" | "permission" | "regression";
  description: string;
};

export type GeneratedPlan = {
  summary: string;
  request_type: string;
  questions: string[];
  evidence: EvidenceRef[];
  affected_files: AffectedFile[];
  user_story: string;
  acceptance_criteria: string[];
  tasks: TaskItem[];
  test_cases: TestCaseItem[];
  assumptions: string[];
  risks: string[];
  confidence: "high" | "medium" | "low";
};

export type Run = {
  id: string;
  change_request_id: string;
  status: string;
  steps: RunStep[];
  pending_question: string | null;
  generated_plan: GeneratedPlan | null;
  plan_id: string | null;
};

export type Decision = "approved" | "edit_approved" | "rejected" | "regenerate_requested";

export type EvaluationCategory = "clear" | "cross_source" | "ambiguous" | "unsupported";
export type EvaluationBehavior = "direct_answer" | "clarification" | "insufficient_evidence" | "failed";

export type EvaluationCase = {
  id: string;
  title: string;
  request_text: string;
  category: EvaluationCategory;
  expected_behavior: EvaluationBehavior;
  expected_sources: string[];
  expected_affected_files: string[];
  created_at: string;
};

export type EvaluationCaseInput = {
  title: string;
  request_text: string;
  category: EvaluationCategory;
  expected_behavior: EvaluationBehavior;
  expected_sources?: string[];
  expected_affected_files?: string[];
};

export type EvaluationResult = {
  id: string;
  case_id: string;
  run_id: string | null;
  actual_behavior: EvaluationBehavior;
  retrieved_sources: string[];
  affected_files: string[];
  confidence: string | null;
  passed: boolean;
  notes: string | null;
  latency_ms: number;
  created_at: string;
};

export type EvaluationReport = {
  total_cases: number;
  total_results: number;
  overall_pass_rate: number | null;
  retrieval_hit_rate: number | null;
  affected_file_precision: number | null;
  citation_correctness: number | null;
  clarification_accuracy: number | null;
  unsupported_claim_rate: number | null;
  reviewer_acceptance: number | null;
  median_latency_ms: number | null;
  max_latency_ms: number | null;
};

export const api = {
  register: (email: string, password: string) =>
    request<User>("/auth/register", { method: "POST", body: JSON.stringify({ email, password }) }),
  login: (email: string, password: string) =>
    request<User>("/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }),
  logout: () => request<void>("/auth/logout", { method: "POST" }),
  listProjects: () => request<Project[]>("/projects"),
  createProject: (name: string) =>
    request<Project>("/projects", { method: "POST", body: JSON.stringify({ name }) }),
  getProject: (projectId: string) => request<Project>(`/projects/${projectId}`),
  listDocuments: (projectId: string) => request<ProjectDocument[]>(`/projects/${projectId}/documents`),
  uploadDocument: (projectId: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<ProjectDocument>(`/projects/${projectId}/documents`, { method: "POST", body: form });
  },
  uploadCodebase: (projectId: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<ProjectDocument>(`/projects/${projectId}/codebases`, { method: "POST", body: form });
  },
  deleteDocument: (projectId: string, documentId: string) =>
    request<void>(`/projects/${projectId}/documents/${documentId}`, { method: "DELETE" }),
  search: (projectId: string, query: string, contentType: "requirement" | "code" | "all") =>
    request<{ results: SearchResult[] }>(`/projects/${projectId}/search`, {
      method: "POST",
      body: JSON.stringify({ query, content_type: contentType }),
    }),
  createChangeRequest: (projectId: string, requestText: string) =>
    request<ChangeRequest>(`/projects/${projectId}/requests`, {
      method: "POST",
      body: JSON.stringify({ request_text: requestText }),
    }),
  analyseRequest: (requestId: string) => request<Run>(`/requests/${requestId}/analyse`, { method: "POST" }),
  getRun: (runId: string) => request<Run>(`/runs/${runId}`),
  answerClarification: (runId: string, answer: string) =>
    request<Run>(`/runs/${runId}/clarification`, { method: "POST", body: JSON.stringify({ answer }) }),
  submitDecision: (planId: string, decision: Decision, feedback?: string) =>
    request<Run>(`/plans/${planId}/decision`, {
      method: "POST",
      body: JSON.stringify({ decision, feedback: feedback ?? null }),
    }),
  listEvaluationCases: (projectId: string) =>
    request<EvaluationCase[]>(`/projects/${projectId}/evaluation/cases`),
  createEvaluationCase: (projectId: string, input: EvaluationCaseInput) =>
    request<EvaluationCase>(`/projects/${projectId}/evaluation/cases`, {
      method: "POST",
      body: JSON.stringify(input),
    }),
  deleteEvaluationCase: (projectId: string, caseId: string) =>
    request<void>(`/projects/${projectId}/evaluation/cases/${caseId}`, { method: "DELETE" }),
  runEvaluation: (projectId: string) =>
    request<EvaluationResult[]>(`/projects/${projectId}/evaluation/run`, { method: "POST" }),
  getEvaluationReport: (projectId: string) =>
    request<EvaluationReport>(`/projects/${projectId}/evaluation/report`),
};
