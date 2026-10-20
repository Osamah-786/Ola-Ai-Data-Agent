import { useState } from "react";
import type { FormEvent } from "react";
import { runSqlAnalyst } from "../api/client";
import type { ConnectionState, SqlAnalystResponse } from "../types";

interface SqlAnalystPageProps {
  connection: ConnectionState;
}

const examples = [
  "What are the different payment methods in the database?",
  "How many completed rides are there?",
  "Find the average fare for completed rides.",
];

function displayValue(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

export function SqlAnalystPage({ connection }: SqlAnalystPageProps) {
  const [question, setQuestion] = useState("");
  const [mode, setMode] = useState<"mock" | "live">("mock");
  const [result, setResult] = useState<SqlAnalystResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const liveEnabled = connection.kind === "connected" &&
    connection.info.metadata?.agent_execution_enabled === true;

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const value = question.trim();
    if (!value || value.length > 4000 || pending) return;
    setPending(true);
    setResult(null);
    setError(null);
    try {
      setResult(await runSqlAnalyst({ question: value, execution_mode: mode }));
    } catch (requestError: unknown) {
      setError(requestError instanceof Error ? requestError.message : "The SQL request could not be completed.");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="sql-page">
      <section className="sql-intro">
        <div>
          <span className="welcome-panel__eyebrow">READ-ONLY DATABASE ANALYSIS</span>
          <h2>Ask a question about your data.</h2>
          <p>Review the generated query and safety outcome alongside a bounded result table and explanation.</p>
        </div>
        <span className="etl-safety-badge">Read-only safeguards</span>
      </section>

      <section className="etl-card" aria-labelledby="sql-question-title">
        <div className="etl-card__heading">
          <span className="etl-step">SQL</span>
          <div><h2 id="sql-question-title">Ask the SQL Analyst</h2><p>Mock mode is selected by default. Mock requests do not generate or execute SQL.</p></div>
        </div>
        <div className="etl-examples" aria-label="Example questions">
          {examples.map((example) => <button className="etl-example" type="button" key={example} disabled={pending} onClick={() => setQuestion(example)}>{example}</button>)}
        </div>
        <form onSubmit={submit}>
          <label className="etl-label" htmlFor="sql-question">Natural-language question</label>
          <textarea id="sql-question" className="etl-input etl-textarea" maxLength={4000} value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="For example: How many completed rides are there?" disabled={pending} />
          <div className="sql-mode">
            <label><input type="radio" name="sql-mode" checked={mode === "mock"} onChange={() => setMode("mock")} disabled={pending} /> Mock mode</label>
            <label><input type="radio" name="sql-mode" checked={mode === "live"} onChange={() => setMode("live")} disabled={pending} /> Request live SQL analysis</label>
            {mode === "live" && <p role="note">Live mode can call the configured LLM and PostgreSQL workflow. It runs only if the server also enables <code>ENABLE_LIVE_AGENTS=true</code>.</p>}
            {!liveEnabled && <span className="sql-server-gate">Server live-agent gate is not enabled or unavailable.</span>}
          </div>
          <div className="etl-form-row">
            <span className="character-count">{question.length.toLocaleString()} / 4,000</span>
            <button className="button button--primary" type="submit" disabled={!question.trim() || question.length > 4000 || pending}>{pending ? <><span className="button-spinner" aria-hidden="true" /> Running…</> : "Run Query"}</button>
          </div>
        </form>
      </section>

      {pending && <section className="loading-card" role="status"><span className="loading-spinner" aria-hidden="true" /><div><h2>Processing SQL request</h2><p>{mode === "mock" ? "Waiting for the mock API response." : "Waiting for the gated SQL workflow."}</p></div></section>}
      {error && <section className="error-card" role="alert"><span className="error-card__icon" aria-hidden="true">!</span><div><h2>Could not complete the SQL request</h2><p>{error}</p></div></section>}

      {result && <section className={`sql-result ${result.status === "error" ? "sql-result--error" : ""}`} aria-live="polite">
        <div className="sql-result__heading"><div><span className="response-card__eyebrow">SQL ANALYST RESULT</span><h2>{result.status === "rejected" ? "Query rejected" : result.status === "error" ? "Query failed" : "Analysis complete"}</h2></div><span className={`mode-badge ${result.mode === "mock" ? "mode-badge--mock" : "mode-badge--agent"}`}><span />{result.mode === "mock" ? "Mock response" : "Live agent response"}</span></div>
        {result.mode === "mock" && <p className="mock-note" role="note">Mock mode only: no SQL was generated and no database query was executed.</p>}
        <div className="sql-safety"><strong>Safety status:</strong> {result.safety_status === "safe" ? "Passed" : result.safety_status === "rejected" ? "Rejected" : "Not run (mock mode)"}</div>
        {result.rejection_reason && <p className="sql-rejection"><strong>Rejection reason:</strong> {result.rejection_reason}</p>}
        {result.generated_sql && <div className="sql-query"><h3>Generated SQL</h3><pre><code>{result.generated_sql}</code></pre></div>}
        <div className="sql-answer"><h3>Answer</h3><p>{result.answer}</p></div>
        <div className="sql-row-count">{result.row_count} {result.row_count === 1 ? "row" : "rows"}</div>
        {result.rows.length > 0 ? <div className="etl-table-wrap"><table className="etl-table"><thead><tr>{Object.keys(result.rows[0]).map((column) => <th key={column}>{column}</th>)}</tr></thead><tbody>{result.rows.map((row, index) => <tr key={index}>{Object.keys(result.rows[0]).map((column) => <td key={column}>{displayValue(row[column])}</td>)}</tr>)}</tbody></table></div> : <p className="sql-empty">{result.mode === "mock" ? "No database rows are included in a mock response." : "No matching records were returned."}</p>}
      </section>}
    </div>
  );
}
