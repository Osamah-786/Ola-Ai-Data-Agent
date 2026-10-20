import type { DatasetPreview } from "../types";

interface DatasetTableProps {
  preview: DatasetPreview | null;
  loading: boolean;
  error: string | null;
  onPageChange: (page: number) => void;
}

function displayValue(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  try { return JSON.stringify(value); } catch { return String(value); }
}

export function DatasetTable({ preview, loading, error, onPageChange }: DatasetTableProps) {
  if (loading) return <div className="etl-state" role="status">Loading dataset preview…</div>;
  if (error) return <div className="etl-state etl-state--error" role="alert">{error}</div>;
  if (!preview) return <div className="etl-state">Select or extract a dataset to preview its first 20 rows.</div>;
  if (!preview.columns.length) return <div className="etl-state">This dataset has no columns.</div>;
  if (!preview.total_records) return <div className="etl-state">This dataset contains no records.</div>;
  return (
    <section aria-label="Dataset preview">
      <div className="etl-table-wrap" tabIndex={0} aria-label="Scrollable dataset table">
        <table className="etl-table">
          <thead><tr>{preview.columns.map((column) => <th key={column} scope="col">{column}</th>)}</tr></thead>
          <tbody>{preview.rows.map((row, index) => <tr key={`${preview.page}-${index}`}>
            {preview.columns.map((column) => <td key={column} title={displayValue(row[column])}>{displayValue(row[column])}</td>)}
          </tr>)}</tbody>
        </table>
      </div>
      <div className="etl-pagination">
        <span>{preview.total_records.toLocaleString()} records · Page {preview.page} of {preview.total_pages}</span>
        <div>
          <button className="button button--secondary" type="button" disabled={preview.page <= 1} onClick={() => onPageChange(preview.page - 1)}>Previous</button>
          <button className="button button--secondary" type="button" disabled={preview.page >= preview.total_pages} onClick={() => onPageChange(preview.page + 1)}>Next</button>
        </div>
      </div>
    </section>
  );
}
