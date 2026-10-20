import { useEffect, useState, type FormEvent } from "react";
import {
  extractDataset,
  getDatasetDownloadUrl,
  getDatasetPreview,
  listDatasets,
  transformDataset,
} from "../api/client";
import { DatasetTable } from "../components/DatasetTable";
import type { DatasetFormat, DatasetMetadata, DatasetPreview, EtlResult } from "../types";

const examples = [
  { label: "Pokémon list", url: "https://pokeapi.co/api/v2/pokemon?limit=20" },
  { label: "Pokémon detail", url: "https://pokeapi.co/api/v2/pokemon/1" },
  { label: "Public JSON", url: "https://jsonplaceholder.typicode.com/users" },
];
const instructions = [
  "Keep only the name and URL columns.",
  "Remove duplicate rows.",
  "Sort by name in ascending order.",
  "Keep only rows where name contains bulbasaur.",
  "Fill missing values in the name column with Unknown.",
];

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : "The ETL request could not be completed.";
}

function safeUrlMessage(value: string): string | null {
  if (!value.trim()) return "Enter an API URL to extract data.";
  try {
    const url = new URL(value);
    if (!["http:", "https:"].includes(url.protocol)) return "Use an HTTP or HTTPS URL.";
    if (url.username || url.password) return "URLs containing credentials are not allowed.";
  } catch { return "Enter a valid HTTP or HTTPS URL."; }
  return null;
}

export function ETLStudioPage() {
  const [url, setUrl] = useState("");
  const [format, setFormat] = useState<DatasetFormat>("csv");
  const [datasets, setDatasets] = useState<DatasetMetadata[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [instruction, setInstruction] = useState("");
  const [outputFormat, setOutputFormat] = useState<DatasetFormat>("csv");
  const [executionMode, setExecutionMode] = useState<"mock" | "live">("mock");
  const [result, setResult] = useState<EtlResult | null>(null);
  const [preview, setPreview] = useState<DatasetPreview | null>(null);
  const [page, setPage] = useState(1);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [busyAction, setBusyAction] = useState<"extract" | "transform" | null>(null);
  const busy = busyAction !== null;
  const [error, setError] = useState<string | null>(null);
  const [urlTouched, setUrlTouched] = useState(false);

  useEffect(() => {
    let active = true;
    listDatasets().then((items) => {
      if (active) {
        setDatasets(items);
        if (items.length) setSelectedId(items[0].file_id);
      }
    }).catch(() => { /* The empty state remains useful when the registry is unavailable. */ });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (!selectedId) { setPreview(null); return; }
    let active = true;
    setPreviewLoading(true);
    setPreviewError(null);
    getDatasetPreview(selectedId, page, 20).then((value) => {
      if (active) setPreview(value);
    }).catch((reason: unknown) => {
      if (active) setPreviewError(errorMessage(reason));
    }).finally(() => { if (active) setPreviewLoading(false); });
    return () => { active = false; };
  }, [selectedId, page]);

  async function submitExtraction(event: FormEvent) {
    event.preventDefault();
    setUrlTouched(true);
    const invalid = safeUrlMessage(url);
    if (invalid || busy) return;
    setBusyAction("extract"); setError(null); setResult(null);
    try {
      const created = await extractDataset(url.trim(), format);
      setResult(created);
      setDatasets((items) => [created, ...items.filter((item) => item.file_id !== created.file_id)]);
      setSelectedId(created.file_id); setPage(1);
    } catch (reason) { setError(errorMessage(reason)); }
    finally { setBusyAction(null); }
  }

  async function submitTransformation(event: FormEvent) {
    event.preventDefault();
    if (!selectedId || !instruction.trim() || busy) return;
    if (executionMode === "mock") {
      setError("Mock mode does not run transformation or create an output dataset. Select live mode only if the server is explicitly authorized.");
      setResult(null);
      return;
    }
    setBusyAction("transform"); setError(null); setResult(null);
    try {
      const transformed = await transformDataset(selectedId, outputFormat, instruction.trim(), executionMode);
      setResult(transformed);
      setDatasets((items) => [transformed, ...items.filter((item) => item.file_id !== transformed.file_id)]);
      setSelectedId(transformed.file_id); setPage(1);
    } catch (reason) { setError(errorMessage(reason)); }
    finally { setBusyAction(null); }
  }

  const selected = datasets.find((item) => item.file_id === selectedId);
  const urlError = urlTouched ? safeUrlMessage(url) : null;

  return (
    <div className="etl-page">
      <section className="etl-intro">
        <div><span className="page-header__eyebrow">PHASE 4 · DATA PREPARATION</span>
          <h2>Extract, inspect, and transform datasets</h2>
          <p>Extraction contacts only the URL you submit. Selecting an example fills the form without making a request.</p></div>
        <span className="etl-safety-badge">Managed files · bounded previews</span>
      </section>

      <section className="etl-card">
        <div className="etl-card__heading"><span className="etl-step">01</span><div><h2>Extract from an API</h2>
          <p>Supports JSON arrays, a single JSON object, and paginated objects with a <code>results</code> array and <code>next</code> URL.</p></div></div>
        <div className="etl-examples" aria-label="Example API URLs">{examples.map((example) =>
          <button key={example.label} className="etl-example" type="button" disabled={busy} onClick={() => { setUrl(example.url); setUrlTouched(false); }}>{example.label}</button>)}</div>
        <form onSubmit={submitExtraction} noValidate>
          <label className="etl-label" htmlFor="etl-api-url">API URL</label>
          <input id="etl-api-url" className="etl-input" type="url" value={url} maxLength={2048} onChange={(event) => setUrl(event.target.value)} onBlur={() => setUrlTouched(true)} aria-invalid={Boolean(urlError)} aria-describedby={urlError ? "etl-url-error" : "etl-url-help"} placeholder="https://api.example.com/data" disabled={busy} />
          {urlError ? <p id="etl-url-error" className="etl-field-error" role="alert">{urlError}</p> : <p id="etl-url-help" className="etl-help">Server-side checks reject private, local, and unsafe redirect destinations.</p>}
          <div className="etl-form-row"><div><label className="etl-label" htmlFor="etl-format">Output format</label><select id="etl-format" className="etl-input" value={format} onChange={(event) => setFormat(event.target.value as DatasetFormat)} disabled={busy}><option value="csv">CSV</option><option value="json">JSON Lines</option><option value="parquet">Parquet</option></select></div>
            <button className="button button--primary" type="submit" disabled={busy || Boolean(safeUrlMessage(url))}>{busyAction === "extract" ? <><span className="button-spinner" aria-hidden="true" /> Extracting…</> : "Extract Data"}</button></div>
        </form>
      </section>

      <section className="etl-card">
        <div className="etl-card__heading"><span className="etl-step">02</span><div><h2>Choose a dataset and transform</h2><p>Live planning uses the existing constrained JSON plan and applies it through pandas. No generated Python is executed.</p></div></div>
        <form onSubmit={submitTransformation}>
          <div className="etl-form-row etl-form-row--top"><div className="etl-field-grow"><label className="etl-label" htmlFor="etl-dataset">Dataset</label>
            <select id="etl-dataset" className="etl-input" value={selectedId} onChange={(event) => { setSelectedId(event.target.value); setPage(1); }} disabled={!datasets.length || busy}><option value="">{datasets.length ? "Select a managed dataset" : "No managed datasets yet"}</option>{datasets.map((item) => <option key={item.file_id} value={item.file_id}>{item.kind === "extract" ? "Extracted" : "Transformed"} · {item.records} rows · {item.format.toUpperCase()} · {item.file_id.slice(0, 8)}</option>)}</select></div>
            <div><label className="etl-label" htmlFor="etl-output-format">Output format</label><select id="etl-output-format" className="etl-input" value={outputFormat} onChange={(event) => setOutputFormat(event.target.value as DatasetFormat)} disabled={busy}><option value="csv">CSV</option><option value="json">JSON Lines</option><option value="parquet">Parquet</option></select></div></div>
          <label className="etl-label" htmlFor="etl-instruction">Transformation instruction</label>
          <textarea id="etl-instruction" className="etl-input etl-textarea" maxLength={2000} value={instruction} onChange={(event) => setInstruction(event.target.value)} placeholder="For example: Remove duplicate rows." disabled={busy} />
          <div className="etl-instruction-examples">{instructions.map((item) => <button key={item} type="button" className="etl-example" disabled={busy} onClick={() => setInstruction(item)}>{item}</button>)}</div>
          <fieldset className="etl-mode"><legend>Transformation mode</legend>
            <label><input type="radio" name="etl-mode" value="mock" checked={executionMode === "mock"} onChange={() => setExecutionMode("mock")} disabled={busy} /> <span><strong>Mock / disabled</strong> — does not plan, transform, or create a dataset.</span></label>
            <label><input type="radio" name="etl-mode" value="live" checked={executionMode === "live"} onChange={() => setExecutionMode("live")} disabled={busy} /> <span><strong>Live AI-assisted planning</strong> — requires explicit server authorization and may call Groq.</span></label>
          </fieldset>
          <div className="etl-form-row"><span className="etl-help">Input is preserved; a successful transform creates a distinct dataset.</span><button className="button button--primary" type="submit" disabled={busy || !selectedId || !instruction.trim()}>{busyAction === "transform" ? <><span className="button-spinner" aria-hidden="true" /> Transforming…</> : "Transform Data"}</button></div>
        </form>
      </section>

      {(error || result) && <section className={`etl-result ${error ? "etl-result--error" : ""}`} aria-live="polite" role={error ? "alert" : "status"}>
        <div className="etl-result__header"><div><span className="page-header__eyebrow">{error ? "REQUEST FAILED" : result?.kind === "extract" ? "EXTRACTION COMPLETE" : "TRANSFORMATION COMPLETE"}</span><h2>{error ? "The operation could not be completed" : result?.message}</h2></div>{result && <a className="button button--secondary" href={getDatasetDownloadUrl(result.file_id)} download>Download dataset</a>}</div>
        {error ? <p>{error}</p> : result && <dl className="etl-metadata"><div><dt>Records</dt><dd>{result.records}</dd></div>{result.pages_fetched !== null && result.pages_fetched !== undefined && <div><dt>Pages fetched</dt><dd>{result.pages_fetched}</dd></div>}<div><dt>Format</dt><dd>{result.format.toUpperCase()}</dd></div><div><dt>Dataset ID</dt><dd>{result.file_id}</dd></div><div><dt>Columns</dt><dd>{result.columns.length ? result.columns.join(", ") : "None"}</dd></div>{result.operations.length > 0 && <div><dt>Applied operations</dt><dd>{result.operations.join(", ")}</dd></div>}</dl>}
      </section>}

      <section className="etl-card etl-preview-card">
        <div className="etl-card__heading etl-card__heading--split"><div className="etl-heading-start"><span className="etl-step">03</span><div><h2>Dataset preview</h2><p>{selected ? `${selected.records} records · ${selected.columns.length} columns` : "Preview appears after selecting a dataset."}</p></div></div>{selected && <a className="button button--secondary" href={getDatasetDownloadUrl(selected.file_id)} download>Download selected</a>}</div>
        <DatasetTable preview={preview} loading={previewLoading} error={previewError} onPageChange={setPage} />
      </section>
    </div>
  );
}
