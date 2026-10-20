import type {
  AgentRunRequest,
  AgentRunResponse,
  BackendInfo,
  HealthResponse,
  MetadataResponse,
  DatasetFormat,
  DatasetMetadata,
  DatasetPreview,
  EtlResult,
  SqlAnalystRequest,
  SqlAnalystResponse,
  RunRecord,
} from "../types";

const configuredBaseUrl = import.meta.env.VITE_API_BASE_URL?.trim();
export const API_BASE_URL = (
  configuredBaseUrl || "http://127.0.0.1:8000"
).replace(/\/+$/, "");

const REQUEST_TIMEOUT_MS = 10_000;
const LIVE_AGENT_REQUEST_TIMEOUT_MS = 120_000;

async function requestJson(
  path: string,
  init?: RequestInit,
  timeoutMs = REQUEST_TIMEOUT_MS,
  timeoutMessage?: string,
): Promise<unknown> {
  const controller = new AbortController();
  const timeout = window.setTimeout(
    () => controller.abort(),
    timeoutMs,
  );

  try {
    const headers = new Headers(init?.headers);
    headers.set("Accept", "application/json");
    const response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      signal: controller.signal,
      headers,
    });
    const body: unknown = await response.json().catch(() => null);

    if (!response.ok) {
      throw new ApiError(
        response.status,
        readErrorMessage(body, response.status),
      );
    }

    return body;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new Error(timeoutMessage ?? "The backend request timed out. Please try again.");
    }
    throw new Error(
      "Could not reach the FastAPI server. Check that it is running and try again.",
    );
  } finally {
    window.clearTimeout(timeout);
  }
}

class ApiError extends Error {
  constructor(
    readonly statusCode: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function readErrorMessage(body: unknown, statusCode: number): string {
  if (statusCode === 403) {
    return "Live execution is disabled on this server. Ask the developer to explicitly set ENABLE_LIVE_AGENTS=true.";
  }
  if (statusCode === 502) {
    return "The live agent did not return a usable answer.";
  }
  if (isRecord(body) && typeof body.detail === "string") {
    if (statusCode === 422 && body.detail === "Invalid request payload.") {
      return "Please check your request and try again.";
    }
    if (statusCode >= 500) return "The backend could not complete this request.";
    return body.detail;
  }
  if (statusCode === 422) return "Please check your request and try again.";
  if (statusCode >= 500) return "The backend could not complete this request.";
  return `The backend returned an unexpected response (${statusCode}).`;
}

function isHealthResponse(value: unknown): value is HealthResponse {
  return (
    isRecord(value) &&
    value.status === "ok" &&
    typeof value.service === "string" &&
    value.mode === "mock"
  );
}

function isMetadataResponse(value: unknown): value is MetadataResponse {
  return (
    isRecord(value) &&
    typeof value.service === "string" &&
    typeof value.version === "string" &&
    typeof value.agent_execution_enabled === "boolean" &&
    Array.isArray(value.available_endpoints) &&
    value.available_endpoints.every((item) => typeof item === "string")
  );
}

function isAgentRunResponse(value: unknown): value is AgentRunResponse {
  return (
    isRecord(value) &&
    (value.status === "ok" || value.status === "error") &&
    typeof value.answer === "string" &&
    (value.route === null || value.route === "etl" || value.route === "sql") &&
    (value.mode === "mock" || value.mode === "agent") &&
    (value.request_id === undefined ||
      value.request_id === null ||
      typeof value.request_id === "string")
  );
}

export async function getBackendInfo(): Promise<BackendInfo> {
  const [healthBody, metadataBody] = await Promise.all([
    requestJson("/api/health"),
    requestJson("/api/metadata").catch(() => null),
  ]);
  if (!isHealthResponse(healthBody)) {
    throw new Error("The backend health response had an unexpected format.");
  }

  const metadata = isMetadataResponse(metadataBody) ? metadataBody : null;
  return { health: healthBody, metadata };
}

export async function runAgent(
  request: AgentRunRequest,
): Promise<AgentRunResponse> {
  const isLive = request.execution_mode === "live";
  const timeoutMs = isLive ? LIVE_AGENT_REQUEST_TIMEOUT_MS : REQUEST_TIMEOUT_MS;
  const body = await requestJson("/api/agent/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  }, timeoutMs, isLive
    ? `The live agent request timed out after ${timeoutMs / 1000} seconds. The backend may still be processing it; check Run History before submitting again.`
    : "The mock agent request timed out. Check that the FastAPI server is responsive before retrying.");

  if (!isAgentRunResponse(body)) {
    throw new Error("The backend returned an unexpected agent response.");
  }
  return body;
}

function isSqlAnalystResponse(value: unknown): value is SqlAnalystResponse {
  return isRecord(value) &&
    (value.status === "ok" || value.status === "rejected" || value.status === "error") &&
    typeof value.answer === "string" &&
    (value.generated_sql === undefined || value.generated_sql === null || typeof value.generated_sql === "string") &&
    (value.safety_status === "not_run" || value.safety_status === "safe" || value.safety_status === "rejected") &&
    (value.rejection_reason === undefined || value.rejection_reason === null || typeof value.rejection_reason === "string") &&
    Array.isArray(value.rows) && value.rows.every(isRecord) &&
    typeof value.row_count === "number" && value.row_count === value.rows.length &&
    (value.mode === "mock" || value.mode === "agent") &&
    (value.request_id === undefined || value.request_id === null || typeof value.request_id === "string");
}

export async function runSqlAnalyst(
  request: SqlAnalystRequest,
): Promise<SqlAnalystResponse> {
  const body = await requestJson("/api/sql/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  if (!isSqlAnalystResponse(body)) {
    throw new Error("The backend returned an unexpected SQL analyst response.");
  }
  return body;
}

function isRunRecord(value: unknown): value is RunRecord {
  return isRecord(value) && typeof value.run_id === "string" &&
    typeof value.task_description === "string" &&
    ["workspace", "etl", "etl_extract", "etl_transform", "sql"].includes(String(value.workflow)) &&
    typeof value.execution_mode === "string" &&
    ["success", "failed", "rejected"].includes(String(value.status)) &&
    typeof value.started_at === "string" && typeof value.completed_at === "string" &&
    typeof value.result_summary === "string" && Array.isArray(value.dataset_ids) &&
    value.dataset_ids.every((id) => typeof id === "string");
}

export async function listRuns(): Promise<RunRecord[]> {
  const body = await requestJson("/api/runs?limit=50");
  if (!Array.isArray(body) || !body.every(isRunRecord)) {
    throw new Error("The backend returned an unexpected run history.");
  }
  return body;
}

export async function getRun(runId: string): Promise<RunRecord> {
  const body = await requestJson(`/api/runs/${encodeURIComponent(runId)}`);
  if (!isRunRecord(body)) throw new Error("The backend returned an unexpected run record.");
  return body;
}

function isDatasetMetadata(value: unknown): value is DatasetMetadata {
  return isRecord(value) && typeof value.file_id === "string" &&
    (value.format === "csv" || value.format === "json" || value.format === "parquet") &&
    typeof value.records === "number" && Array.isArray(value.columns) &&
    (value.kind === "extract" || value.kind === "transform") &&
    Array.isArray(value.operations) && typeof value.created_at === "string";
}

function isEtlResult(value: unknown): value is EtlResult {
  return isRecord(value) && value.status === "success" &&
    typeof value.message === "string" && isDatasetMetadata(value);
}

export async function extractDataset(url: string, format: DatasetFormat): Promise<EtlResult> {
  const body = await requestJson("/api/etl/extract", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url, format }),
  });
  if (!isEtlResult(body)) throw new Error("The backend returned unexpected extraction metadata.");
  return body;
}

export async function transformDataset(inputFileId: string, outputFormat: DatasetFormat,
                                       instruction: string, executionMode: "mock" | "live") {
  const body = await requestJson("/api/etl/transform", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ input_file_id: inputFileId, output_format: outputFormat,
      instruction, execution_mode: executionMode }),
  });
  if (!isEtlResult(body)) throw new Error("The backend returned unexpected transformation metadata.");
  return body;
}

export async function listDatasets(): Promise<DatasetMetadata[]> {
  const body = await requestJson("/api/files");
  if (!Array.isArray(body) || !body.every(isDatasetMetadata)) {
    throw new Error("The backend returned an unexpected dataset list.");
  }
  return body;
}

export async function getDatasetPreview(fileId: string, page: number, pageSize = 20): Promise<DatasetPreview> {
  const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
  const body = await requestJson(`/api/files/${encodeURIComponent(fileId)}/preview?${params}`);
  if (!isRecord(body) || typeof body.file_id !== "string" || !Array.isArray(body.columns) ||
      !Array.isArray(body.rows) || typeof body.page !== "number" ||
      typeof body.page_size !== "number" || typeof body.total_records !== "number" ||
      typeof body.total_pages !== "number") {
    throw new Error("The backend returned an unexpected dataset preview.");
  }
  return body as unknown as DatasetPreview;
}

export function getDatasetDownloadUrl(fileId: string): string {
  return `${API_BASE_URL}/api/files/${encodeURIComponent(fileId)}/download`;
}
