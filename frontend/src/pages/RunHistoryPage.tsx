import { useEffect, useState } from "react";
import { getDatasetDownloadUrl, getRun, listRuns } from "../api/client";
import type { RunRecord } from "../types";

function formatDate(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

function workflowLabel(workflow: RunRecord["workflow"]): string {
  return ({
    workspace: "Workspace",
    etl: "ETL",
    etl_extract: "ETL extraction",
    etl_transform: "ETL transformation",
    sql: "SQL Analyst",
  })[workflow];
}

export function RunHistoryPage() {
  const [runs, setRuns] = useState<RunRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<RunRecord | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    listRuns().then((items) => {
      if (active) setRuns(items);
    }).catch((requestError: unknown) => {
      if (active) setError(requestError instanceof Error ? requestError.message : "Run history could not be loaded.");
    }).finally(() => {
      if (active) setLoading(false);
    });
    return () => { active = false; };
  }, []);

  async function openRun(runId: string) {
    setDetailLoading(true);
    setDetailError(null);
    setSelected(null);
    try {
      setSelected(await getRun(runId));
    } catch (requestError: unknown) {
      setDetailError(requestError instanceof Error ? requestError.message : "Run details could not be loaded.");
    } finally {
      setDetailLoading(false);
    }
  }

  return (
    <div className="history-page">
      <section className="sql-intro">
        <div>
          <span className="welcome-panel__eyebrow">RECENT ACTIVITY</span>
          <h2>Run History</h2>
          <p>Review recent Workspace, ETL, and SQL requests. Sensitive prompts and result contents are not stored.</p>
        </div>
        <span className="etl-safety-badge">Latest runs</span>
      </section>

      {loading && <section className="loading-card" role="status"><span className="loading-spinner" aria-hidden="true" /><div><h2>Loading run history</h2><p>Checking for recorded runs.</p></div></section>}
      {error && <section className="error-card" role="alert"><span className="error-card__icon" aria-hidden="true">!</span><div><h2>Run history unavailable</h2><p>{error}</p></div></section>}
      {!loading && !error && runs.length === 0 && <section className="history-empty"><h2>No runs yet</h2><p>Completed or failed requests will appear here.</p></section>}

      {!loading && !error && runs.length > 0 && <section className="history-list" aria-label="Recent runs">
        {runs.map((run) => <article className="history-item" key={run.run_id}>
          <div className="history-item__main">
            <div className="history-item__title"><h2>{run.task_description}</h2><span className={`history-status history-status--${run.status}`}>{run.status}</span></div>
            <div className="history-item__meta"><span>{workflowLabel(run.workflow)}</span><span>{run.execution_mode}</span><time dateTime={run.started_at}>{formatDate(run.started_at)}</time></div>
            <p>{run.result_summary}</p>
          </div>
          <button className="button button--secondary" type="button" onClick={() => void openRun(run.run_id)}>View details</button>
        </article>)}
      </section>}

      {detailLoading && <section className="loading-card" role="status"><span className="loading-spinner" aria-hidden="true" /><div><h2>Loading run details</h2></div></section>}
      {detailError && <section className="error-card" role="alert"><span className="error-card__icon" aria-hidden="true">!</span><div><h2>Could not load run details</h2><p>{detailError}</p></div></section>}
      {selected && <section className="history-detail" aria-labelledby="history-detail-title">
        <div className="history-detail__heading"><div><span className="response-card__eyebrow">RUN DETAILS</span><h2 id="history-detail-title">{selected.task_description}</h2></div><button className="text-button" type="button" onClick={() => setSelected(null)}>Close</button></div>
        <dl className="history-detail__grid">
          <div><dt>Workflow</dt><dd>{workflowLabel(selected.workflow)}</dd></div>
          <div><dt>Status</dt><dd>{selected.status}</dd></div>
          <div><dt>Execution mode</dt><dd>{selected.execution_mode}</dd></div>
          <div><dt>Started</dt><dd>{formatDate(selected.started_at)}</dd></div>
          <div><dt>Completed</dt><dd>{formatDate(selected.completed_at)}</dd></div>
          <div><dt>Run ID</dt><dd><code>{selected.run_id}</code></dd></div>
        </dl>
        <p className="history-detail__summary">{selected.result_summary}</p>
        {selected.dataset_ids.length > 0 && <div className="history-datasets"><h3>Dataset links</h3>{selected.dataset_ids.map((id) => <a key={id} href={getDatasetDownloadUrl(id)}>Download dataset {id.slice(0, 8)}</a>)}</div>}
      </section>}
    </div>
  );
}
