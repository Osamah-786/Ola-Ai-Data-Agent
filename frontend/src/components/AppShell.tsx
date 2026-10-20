import type { ReactNode } from "react";
import type { ConnectionState } from "../types";
import { PageHeader } from "./PageHeader";
import { Sidebar } from "./Sidebar";

interface AppShellProps {
  currentPath: string;
  onNavigate: (path: string) => void;
  title: string;
  description: string;
  connection: ConnectionState;
  onRetryConnection: () => void;
  children: ReactNode;
}

export function AppShell({
  currentPath,
  onNavigate,
  title,
  description,
  connection,
  onRetryConnection,
  children,
}: AppShellProps) {
  return (
    <div className="app-shell">
      <Sidebar currentPath={currentPath} onNavigate={onNavigate} />
      <div className="app-shell__main">
        <PageHeader
          title={title}
          description={description}
          connection={connection}
          onRetryConnection={onRetryConnection}
        />
        <main className="main-content">{children}</main>
        <footer className="main-footer">
          <span>Ola AI Data Agent</span>
          <span>Live agent execution requires explicit server authorization.</span>
        </footer>
      </div>
    </div>
  );
}
