import { useState } from "react";
import { runAgent } from "../api/client";
import { AgentResponse } from "../components/AgentResponse";
import { RequestComposer } from "../components/RequestComposer";
import { WorkflowGuide } from "../components/WorkflowGuide";
import type { AgentRunResponse, ConnectionState } from "../types";

interface WorkspacePageProps {
  connection: ConnectionState;
  onRetryConnection: () => void;
}

export function WorkspacePage({ connection, onRetryConnection }: WorkspacePageProps) {
  const [message, setMessage] = useState("");
  const [executionMode, setExecutionMode] = useState<"mock" | "live">("mock");
  const [response, setResponse] = useState<AgentRunResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isPending, setIsPending] = useState(false);
  const serverAllowsLive =
    connection.kind === "connected" &&
    connection.info.metadata?.agent_execution_enabled === true;

  async function submitRequest() {
    const validatedMessage = message.trim();
    if (!validatedMessage || validatedMessage.length > 4000 || isPending) return;

    setIsPending(true);
    setError(null);
    setResponse(null);
    try {
      setResponse(await runAgent({
        message: validatedMessage,
        execution_mode: executionMode,
      }));
    } catch (requestError: unknown) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "The request could not be completed. Please try again.",
      );
    } finally {
      setIsPending(false);
    }
  }

  return (
    <div className="workspace-page">
      <section className="welcome-panel">
        <div className="welcome-panel__copy">
          <span className="welcome-panel__eyebrow">YOUR DATA WORKSPACE</span>
          <h2>Ola AI Data Agent</h2>
          <p className="welcome-panel__subtitle">
            Your workspace for API data extraction, transformation, and database analysis.
          </p>
          <p className="welcome-panel__description">
            Describe a task in natural language. Mock mode is selected by default. Live requests are
            sent to the existing workflow router only when the server explicitly allows execution.
          </p>
        </div>
        <div className="welcome-panel__status">
          <div className="welcome-panel__connectivity">
            <span className={`status-dot status-dot--${connection.kind}`} aria-hidden="true" />
            <span>
              {connection.kind === "checking"
                ? "Checking backend"
                : connection.kind === "connected"
                  ? "Backend available"
                  : "Backend unavailable"}
            </span>
            {connection.kind === "unavailable" && (
              <button className="text-button" type="button" onClick={onRetryConnection}>
                Retry
              </button>
            )}
          </div>
          <div className="execution-note">
            <span className="execution-note__dot" />
            <span>
              {serverAllowsLive
                ? "Live agent execution enabled on server"
                : "Live agent execution disabled on server"}
            </span>
          </div>
        </div>
      </section>

      <RequestComposer
        value={message}
        onChange={setMessage}
        onSubmit={submitRequest}
        isPending={isPending}
        executionMode={executionMode}
        onExecutionModeChange={setExecutionMode}
      />

      {isPending && (
        <section className="loading-card" role="status" aria-live="polite">
          <span className="loading-spinner" aria-hidden="true" />
          <div>
            <h2>Waiting for the backend</h2>
            <p>
              {executionMode === "mock"
                ? "Your request is being sent to the mock API service."
                : "Your request is being sent to the live agent service."}
            </p>
          </div>
        </section>
      )}

      {error && (
        <section className="error-card" role="alert">
          <span className="error-card__icon" aria-hidden="true">!</span>
          <div>
            <h2>Could not complete the request</h2>
            <p>{error}</p>
            {connection.kind === "unavailable" && (
              <p className="error-card__hint">Start the FastAPI server, then retry your request.</p>
            )}
          </div>
        </section>
      )}

      {response && <AgentResponse response={response} />}
      {!isPending && !error && !response && <WorkflowGuide />}
    </div>
  );
}
