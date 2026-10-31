async function request(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const text = await response.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = { detail: text };
  }
  if (!response.ok) {
    const detail = data?.detail;
    const message = typeof detail === "string" ? detail : JSON.stringify(detail || data || response.statusText);
    const error = new Error(message);
    error.status = response.status;
    error.payload = data;
    throw error;
  }
  return data;
}

export const api = {
  health: () => request("/api/health"),
  students: () => request("/api/students"),
  student: (id) => request(`/api/students/${id}`),
  createStudent: (body) => request("/api/students", { method: "POST", body: JSON.stringify(body) }),
  predict: (id) => request(`/api/students/${id}/predict`, { method: "POST" }),
  predictions: (id) => request(`/api/students/${id}/predictions`),
  whatIf: (id, body) => request(`/api/students/${id}/what-if`, { method: "POST", body: JSON.stringify(body) }),
  progress: (id, body) => request(`/api/students/${id}/progress`, { method: "POST", body: JSON.stringify(body) }),
  progressLog: (id) => request(`/api/students/${id}/progress`),
  applications: (id) => request(`/api/students/${id}/applications`),
  addApplication: (id, body) =>
    request(`/api/students/${id}/applications`, { method: "POST", body: JSON.stringify(body) }),
  runAgent: (id, body) => request(`/api/students/${id}/agent`, { method: "POST", body: JSON.stringify(body) }),
  agentLogs: (id) => request(`/api/students/${id}/agent-logs`),
  plans: (id) => request(`/api/students/${id}/plans`),
  approve: (planId) => request(`/api/plans/${planId}/approve`, { method: "POST" }),
  reject: (planId) => request(`/api/plans/${planId}/reject`, { method: "POST" }),
  activate: (planId) => request(`/api/plans/${planId}/activate`, { method: "POST" }),
  evaluation: () => request("/api/evaluation"),
  model: () => request("/api/model"),
};
