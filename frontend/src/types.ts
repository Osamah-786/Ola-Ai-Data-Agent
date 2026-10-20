export type AgentRoute = "etl" | "sql" | null;
export type ExecutionMode = "mock" | "agent";

export interface AgentRunRequest {
  message: string;
  execution_mode: "mock" | "live";
}

export interface AgentRunResponse {
  status: "ok" | "error";
  answer: string;
  route: AgentRoute;
  mode: ExecutionMode;
  request_id?: string | null;
}

export interface SqlAnalystRequest {
  question: string;
  execution_mode: "mock" | "live";
}

export interface SqlAnalystResponse {
  status: "ok" | "rejected" | "error";
  answer: string;
  generated_sql?: string | null;
  safety_status: "not_run" | "safe" | "rejected";
  rejection_reason?: string | null;
  rows: Record<string, unknown>[];
  row_count: number;
  mode: "mock" | "agent";
  request_id?: string | null;
}

export interface RunRecord {
  run_id: string;
  task_description: string;
  workflow: "workspace" | "etl" | "etl_extract" | "etl_transform" | "sql";
  execution_mode: string;
  status: "success" | "failed" | "rejected";
  started_at: string;
  completed_at: string;
  result_summary: string;
  dataset_ids: string[];
}

export interface HealthResponse {
  status: "ok";
  service: string;
  mode: "mock";
}

export interface MetadataResponse {
  service: string;
  version: string;
  agent_execution_enabled: boolean;
  available_endpoints: string[];
}

export interface BackendInfo {
  health: HealthResponse;
  metadata: MetadataResponse | null;
}

export type DatasetFormat = "csv" | "json" | "parquet";

export interface DatasetMetadata {
  file_id: string;
  format: DatasetFormat;
  records: number;
  columns: string[];
  kind: "extract" | "transform";
  source_file_id?: string | null;
  operations: string[];
  created_at: string;
}

export interface EtlResult extends DatasetMetadata {
  status: "success";
  message: string;
  pages_fetched?: number | null;
}

export interface DatasetPreview {
  file_id: string;
  columns: string[];
  page: number;
  page_size: number;
  total_records: number;
  total_pages: number;
  rows: Record<string, unknown>[];
}

export type ConnectionState =
  | { kind: "checking" }
  | { kind: "connected"; info: BackendInfo }
  | { kind: "unavailable"; message: string };
