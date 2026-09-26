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
  created_at: string;
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
  duration_ms: number | null;
  version: number;
  previous_version_id: string | null;
  created_at: string;
};

export type DocumentDiff = {
  from_document_id: string;
  from_version: number;
  to_document_id: string;
  to_version: number;
  diff_lines: string[];
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

export type ChangeRequestSummary = {
  id: string;
  request_text: string;
  request_type: string | null;
  status: string;
  created_at: string;
  latest_run_id: string | null;
  plan_summary: string | null;
  confidence: string | null;
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

export const api = {
  runEventsUrl: (requestId: string) => `${API_URL}/requests/${requestId}/events`,
  register: (email: string, password: string) =>
    request<User>("/auth/register", { method: "POST", body: JSON.stringify({ email, password }) }),
  login: (email: string, password: string) =>
    request<User>("/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }),
  logout: () => request<void>("/auth/logout", { method: "POST" }),
  getCurrentUser: () => request<User>("/auth/me"),
  changePassword: (currentPassword: string, newPassword: string) =>
    request<void>("/auth/change-password", {
      method: "POST",
      body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
    }),
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
  importGithubRepo: (projectId: string, owner: string, repo: string, branch: string) =>
    request<ProjectDocument>(`/projects/${projectId}/github-import`, {
      method: "POST",
      body: JSON.stringify({ owner, repo, branch }),
    }),
  deleteDocument: (projectId: string, documentId: string) =>
    request<void>(`/projects/${projectId}/documents/${documentId}`, { method: "DELETE" }),
  diffDocumentVersions: (projectId: string, documentId: string, against: string) =>
    request<DocumentDiff>(
      `/projects/${projectId}/documents/${documentId}/diff?against=${against}`
    ),
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
  listChangeRequests: (projectId: string) =>
    request<ChangeRequestSummary[]>(`/projects/${projectId}/requests`),
  analyseRequest: (requestId: string) => request<Run>(`/requests/${requestId}/analyse`, { method: "POST" }),
  getRun: (runId: string) => request<Run>(`/runs/${runId}`),
  answerClarification: (runId: string, answer: string) =>
    request<Run>(`/runs/${runId}/clarification`, { method: "POST", body: JSON.stringify({ answer }) }),
  submitDecision: (planId: string, decision: Decision, feedback?: string, finalContent?: GeneratedPlan) =>
    request<Run>(`/plans/${planId}/decision`, {
      method: "POST",
      body: JSON.stringify({ decision, feedback: feedback ?? null, final_content: finalContent ?? null }),
    }),
};
