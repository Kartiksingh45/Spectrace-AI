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

/** Same contract as request(), but for a large FormData body where the caller wants live upload
 * progress - plain fetch() has no upload-progress event, so this uses XMLHttpRequest instead. */
function requestWithProgress<T>(
  path: string,
  body: FormData,
  onProgress?: (percent: number) => void
): Promise<T> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_URL}${path}`);
    xhr.withCredentials = true;
    xhr.upload.onprogress = (e) => {
      if (onProgress && e.lengthComputable) {
        onProgress(Math.round((e.loaded / e.total) * 100));
      }
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(xhr.status === 204 ? (undefined as T) : (JSON.parse(xhr.responseText) as T));
        return;
      }
      let detail = xhr.statusText;
      try {
        detail = JSON.parse(xhr.responseText).detail ?? detail;
      } catch {
        // response wasn't JSON - fall back to statusText
      }
      reject(new ApiError(xhr.status, detail || "Request failed"));
    };
    xhr.onerror = () => reject(new ApiError(0, "Network error"));
    xhr.send(body);
  });
}

export type User = {
  id: string;
  email: string;
  role: "contributor" | "reviewer" | "administrator";
  created_at: string;
};

export type ProjectStatus = "draft" | "in_progress" | "complete";

export type Project = {
  id: string;
  name: string;
  owner_id: string;
  created_at: string;
  updated_at: string;
  status: ProjectStatus;
  requirement_count: number | null;
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
  chunks_total: number | null;
  chunks_embedded: number | null;
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

export type BrdInput = {
  project_name: string;
  background: string;
  objectives: string;
  target_users: string;
  key_features: string;
  constraints?: string | null;
};

export type BrdRequirement = {
  description: string;
  priority: "must_have" | "should_have" | "could_have" | "wont_have";
};

export type GeneratedBrd = {
  executive_summary: string;
  business_objectives: string[];
  in_scope: string[];
  out_of_scope: string[];
  stakeholders: string[];
  functional_requirements: BrdRequirement[];
  non_functional_requirements: BrdRequirement[];
  assumptions: string[];
  constraints: string[];
  risks: string[];
  success_criteria: string[];
};

export type BrdDocument = {
  id: string;
  project_id: string;
  inputs: BrdInput;
  content: GeneratedBrd;
  created_at: string;
};

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
  deleteProject: (projectId: string) => request<void>(`/projects/${projectId}`, { method: "DELETE" }),
  listDocuments: (projectId: string) => request<ProjectDocument[]>(`/projects/${projectId}/documents`),
  uploadDocument: (projectId: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<ProjectDocument>(`/projects/${projectId}/documents`, { method: "POST", body: form });
  },
  uploadCodebase: (projectId: string, file: File, onProgress?: (percent: number) => void) => {
    const form = new FormData();
    form.append("file", file);
    return requestWithProgress<ProjectDocument>(`/projects/${projectId}/codebases`, form, onProgress);
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
  generateBrd: (projectId: string, payload: BrdInput) =>
    request<BrdDocument>(`/projects/${projectId}/brd`, { method: "POST", body: JSON.stringify(payload) }),
  listBrdDocuments: (projectId: string) => request<BrdDocument[]>(`/projects/${projectId}/brd`),
  deleteBrdDocument: (projectId: string, brdId: string) =>
    request<void>(`/projects/${projectId}/brd/${brdId}`, { method: "DELETE" }),
};
