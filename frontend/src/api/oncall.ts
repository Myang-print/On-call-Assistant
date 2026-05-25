export type OnCallMode = "exact" | "semantic" | "agent";

export type OnCallTraceItem = Record<string, unknown>;

export type OnCallSource = {
  id?: string;
  title?: string;
  filename?: string;
  score?: number | string;
  snippet?: string;
};

export type OnCallQueryResponse = {
  answer: string;
  sources: OnCallSource[];
  trace: OnCallTraceItem[];
};

type BackendResponse = {
  answer?: unknown;
  sources?: unknown;
  results?: unknown;
  trace?: unknown;
  detail?: unknown;
};

export async function queryOnCall(query: string, mode: OnCallMode): Promise<OnCallQueryResponse> {
  const response = await fetch("/api/oncall/query", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ query, mode })
  });

  const payload = (await response.json().catch(() => ({}))) as BackendResponse;
  if (!response.ok) {
    throw new Error(toErrorMessage(payload.detail, response.status));
  }

  return {
    answer: typeof payload.answer === "string" ? payload.answer : "",
    sources: normalizeSources(payload.sources ?? payload.results),
    trace: Array.isArray(payload.trace) ? (payload.trace as OnCallTraceItem[]) : []
  };
}

function normalizeSources(value: unknown): OnCallSource[] {
  if (!Array.isArray(value)) {
    return [];
  }

  return value
    .filter((item): item is Record<string, unknown> => item !== null && typeof item === "object")
    .map((item) => ({
      id: toOptionalString(item.id),
      title: toOptionalString(item.title),
      filename: toOptionalString(item.filename),
      score: toOptionalString(item.score),
      snippet: toOptionalString(item.snippet)
    }));
}

function toOptionalString(value: unknown): string | undefined {
  if (value === undefined || value === null) {
    return undefined;
  }
  return String(value);
}

function toErrorMessage(detail: unknown, status: number): string {
  if (typeof detail === "string" && detail.trim()) {
    return detail;
  }
  return `Request failed with HTTP ${status}`;
}
