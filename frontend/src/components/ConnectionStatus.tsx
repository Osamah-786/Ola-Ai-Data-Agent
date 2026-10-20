import type { ConnectionState } from "../types";

interface ConnectionStatusProps {
  state: ConnectionState;
  onRetry: () => void;
  compact?: boolean;
}

export function ConnectionStatus({
  state,
  onRetry,
  compact = false,
}: ConnectionStatusProps) {
  const label =
    state.kind === "checking"
      ? "Checking connection"
      : state.kind === "connected"
        ? "Backend connected"
        : "Backend unavailable";
  const executionEnabled =
    state.kind === "connected"
      ? state.info.metadata?.agent_execution_enabled
      : undefined;

  return (
    <div className={`connection-status ${compact ? "connection-status--compact" : ""}`}>
      <span className={`status-dot status-dot--${state.kind}`} aria-hidden="true" />
      <span className="connection-status__text">
        <span className="connection-status__label">{label}</span>
        {!compact && state.kind === "connected" && (
          <span className="connection-status__detail">
            {executionEnabled === false ? "Mock execution" : "Health check passed"}
          </span>
        )}
        {!compact && state.kind === "unavailable" && (
          <span className="connection-status__detail">Start the FastAPI server to connect.</span>
        )}
      </span>
      {state.kind === "unavailable" && (
        <button className="connection-status__retry" onClick={onRetry} type="button">
          Retry
        </button>
      )}
      {state.kind === "checking" && <span className="sr-only" role="status">Checking backend connection</span>}
    </div>
  );
}
