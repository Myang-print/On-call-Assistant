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
  query: string;
  answer: string;
  sources: OnCallSource[];
  trace: OnCallTraceItem[];
  raw: BackendResponse;
};

export type DocumentUploadResponse = {
  id: string;
  title: string;
};

type BackendResponse = {
  query?: unknown;
  answer?: unknown;
  sources?: unknown;
  results?: unknown;
  trace?: unknown;
  detail?: unknown;
};

export async function queryOnCall(query: string, mode: OnCallMode): Promise<OnCallQueryResponse> {
  if (mode === "exact") {
    return querySearchEndpoint(`/v1/search?q=${encodeURIComponent(query)}`, query, mode);
  }
  if (mode === "semantic") {
    return querySearchEndpoint(`/v2/search?q=${encodeURIComponent(query)}`, query, mode);
  }
  return queryAgentEndpoint(query, mode);
}

export async function uploadHtmlDocument(file: File): Promise<DocumentUploadResponse> {
  if (!file.name.toLowerCase().endsWith(".html")) {
    throw new Error("Only .html files are supported.");
  }

  const id = file.name.replace(/\.html$/i, "").trim();
  if (!/^[A-Za-z0-9_-]+$/.test(id)) {
    throw new Error("HTML filename must use letters, numbers, hyphen, or underscore only.");
  }

  const html = (await file.text()).trim();
  if (!html || !html.toLowerCase().includes("<html") || !html.toLowerCase().includes("</html>")) {
    throw new Error("Selected file is not a valid HTML document.");
  }

  const payload = await postJson("/v1/documents", { id, html });
  return {
    id: String(payload.id || id),
    title: String(payload.title || id)
  };
}


async function queryAgentEndpoint(query: string, mode: OnCallMode): Promise<OnCallQueryResponse> {
  const payload = await postJson("/api/oncall/query", { query, mode });

  return normalizeResponsePayload(payload, query);
}

async function querySearchEndpoint(url: string, query: string, mode: OnCallMode): Promise<OnCallQueryResponse> {
  const payload = await getJson(url);
  const sources = normalizeSources(payload.results);

  return {
    query: typeof payload.query === "string" ? payload.query : query,
    answer: toSearchAnswer(mode, query, sources),
    sources,
    trace: [
      {
        step: 0,
        event: mode === "exact" ? "v1_search" : "v2_search",
        detail: `${sources.length} result(s) returned`
      }
    ],
    raw: payload
  };
}

function normalizeResponsePayload(payload: BackendResponse, query: string): OnCallQueryResponse {
  const answer = normalizeAnswer(payload.answer);
  console.log("[api] answer type", typeof payload.answer, payload.answer === null ? "null" : "");
  return {
    query: typeof payload.query === "string" ? payload.query : query,
    answer,
    sources: normalizeSources(payload.sources ?? payload.results),
    trace: Array.isArray(payload.trace) ? (payload.trace as OnCallTraceItem[]) : [],
    raw: payload
  };
}

async function getJson(url: string): Promise<BackendResponse> {
  console.log("[api] request", { method: "GET", url });
  const response = await fetch(url);
  console.log("[api] status", response.status);
  const raw = await response.text();
  console.log("[api] raw response", raw);
  const payload = parseJson(raw);
  console.log("[api] parsed response", payload);
  if (!response.ok) {
    throw new Error(toErrorMessage(payload.detail, response.status));
  }
  return payload;
}

async function postJson(url: string, body: Record<string, unknown>): Promise<BackendResponse> {
  console.log("[api] request", { method: "POST", url, body });
  const response = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(body)
  });

  console.log("[api] status", response.status);
  const raw = await response.text();
  console.log("[api] raw response", raw);
  const payload = parseJson(raw);
  console.log("[api] parsed response", payload);
  if (!response.ok) {
    throw new Error(toErrorMessage(payload.detail, response.status));
  }
  return payload;
}

function parseJson(raw: string): BackendResponse {
  if (!raw.trim()) {
    return {};
  }
  try {
    return JSON.parse(raw) as BackendResponse;
  } catch (error) {
    console.log("[api] parse error", error);
    throw new Error("Backend returned non-JSON response.");
  }
}

function normalizeAnswer(value: unknown): string {
  if (typeof value === "string") {
    return value;
  }
  if (value === undefined || value === null) {
    return "";
  }
  return JSON.stringify(value, null, 2);
}

function toSearchAnswer(mode: OnCallMode, query: string, sources: OnCallSource[]): string {
  const label = mode === "exact" ? "V1 精确检索" : "V2 语义检索";
  if (!sources.length) {
    return [
      "1. 检索结果",
      `${label} 未找到与「${query}」匹配的 SOP 文档。`,
      "",
      "2. 建议",
      "请补充更具体的故障关键词、系统名称、错误码或告警信息后重试。"
    ].join("\n");
  }

  const top = sources
    .slice(0, 3)
    .map((source) => source.id || source.title || source.filename || "source")
    .join("、");
  return [
    "1. 检索结果",
    `${label} 找到 ${sources.length} 个相关 SOP 文档。`,
    "",
    "2. 优先查看",
    top,
    "",
    "3. 说明",
    "请结合下方 Sources 中的 title、snippet 和 score 判断具体处理顺序。"
  ].join("\n");
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
