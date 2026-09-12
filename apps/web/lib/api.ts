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
};
