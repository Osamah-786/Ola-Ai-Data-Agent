import type { ConnectionState } from "../types";
import { ConnectionStatus } from "./ConnectionStatus";

interface PageHeaderProps {
  title: string;
  description: string;
  connection: ConnectionState;
  onRetryConnection: () => void;
}

export function PageHeader({
  title,
  description,
  connection,
  onRetryConnection,
}: PageHeaderProps) {
  return (
    <header className="page-header">
      <div>
        <div className="page-header__eyebrow">OLA DATA WORKSPACE</div>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      <ConnectionStatus
        state={connection}
        onRetry={onRetryConnection}
        compact
      />
    </header>
  );
}
