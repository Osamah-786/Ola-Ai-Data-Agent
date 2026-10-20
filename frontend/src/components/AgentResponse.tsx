import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { AgentRunResponse } from "../types";

interface AgentResponseProps {
  response: AgentRunResponse;
}

function redactServerPaths(markdown: string): string {
  return markdown
    .replace(/`([^`\r\n]*\b[A-Za-z]:\\[^`\r\n]*)`/g, "[server file path hidden]")
    .replace(/\b[A-Za-z]:\\(?:[^\\/\s:*?"<>|]+\\)*[^\\/\s:*?"<>|]+/g, "[server file path hidden]")
    .replace(/\bfile:\/\/\/?[^\s`<>)\]]+/gi, "[server file path hidden]")
    .replace(/(?<![A-Za-z0-9:])\/(?:Users|home|root|tmp|var|opt|usr|etc|srv|workspace|app|mnt)\/[^\s`<>)\]]+/g, "[server file path hidden]");
}

export function AgentResponse({ response }: AgentResponseProps) {
  const isMock = response.mode === "mock";
  const isError = response.status === "error";
  const workflow = response.route === "etl" ? "ETL" : response.route === "sql" ? "SQL" : null;

  return (
    <section
      className={`response-card ${isError ? "response-card--error" : ""}`}
      aria-labelledby="response-title"
      aria-live="polite"
    >
      <div className="response-card__header">
        <div className="response-card__title-group">
          <span className={`response-icon ${isError ? "response-icon--error" : ""}`} aria-hidden="true">
            {isError ? "!" : "✓"}
          </span>
          <div>
            <div className="response-card__eyebrow">BACKEND RESPONSE</div>
            <h2 id="response-title">{isError ? "Request returned an error" : "Request received"}</h2>
          </div>
        </div>
        <span className={`mode-badge ${isMock ? "mode-badge--mock" : "mode-badge--agent"}`}>
          <span />{isMock ? "Mock response" : "Agent response"}
        </span>
      </div>

      <section
        className={`response-content ${isError ? "response-content--error" : ""}`}
        aria-label={isError ? "Warnings or errors" : "Summary"}
        role={isError ? "alert" : undefined}
      >
        <h3>{isError ? "Warnings or errors" : "Summary"}</h3>
        <div className="response-markdown">
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            skipHtml
            components={{
              table: ({ children }) => (
                <div className="response-table-wrap" tabIndex={0} aria-label="Scrollable response table">
                  <table>{children}</table>
                </div>
              ),
              a: ({ href, children }) => {
                if (!href) return <span>{children}</span>;
                try {
                  const safeUrl = new URL(href, window.location.origin);
                  if (!["http:", "https:", "mailto:"].includes(safeUrl.protocol)) {
                    return <span>{children}</span>;
                  }
                  return <a href={href} rel="noreferrer">{children}</a>;
                } catch {
                  return <span>{children}</span>;
                }
              },
              img: ({ alt }) => <span>{alt || "[image]"}</span>,
            }}
          >
            {redactServerPaths(response.answer)}
          </ReactMarkdown>
        </div>
      </section>

      <section className="response-meta" aria-label="Execution details">
        <div>
          <span className="response-meta__label">Status</span>
          <span className={`response-meta__value ${isError ? "text-danger" : ""}`}>
            {isError ? "Failed" : "Succeeded"}
          </span>
        </div>
        {workflow && (
          <div>
            <span className="response-meta__label">Workflow</span>
            <span className="response-meta__value">{workflow}</span>
          </div>
        )}
        {response.request_id && (
          <div>
            <span className="response-meta__label">Request ID</span>
            <code className="response-meta__value response-meta__code">{response.request_id}</code>
          </div>
        )}
      </section>

      {isMock && (
        <div className="mock-note" role="note">
          This is a mock response from the connected API. No real agent workflow was invoked.
        </div>
      )}
    </section>
  );
}
