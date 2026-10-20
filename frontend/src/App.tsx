import { useEffect, useState } from "react";
import { getBackendInfo } from "./api/client";
import { AppShell } from "./components/AppShell";
import { WorkspacePage } from "./pages/WorkspacePage";
import { ETLStudioPage } from "./pages/ETLStudioPage";
import { SqlAnalystPage } from "./pages/SqlAnalystPage";
import { RunHistoryPage } from "./pages/RunHistoryPage";
import type { ConnectionState } from "./types";

const pageDetails: Record<string, { title: string; description: string }> = {
  "/": {
    title: "Workspace",
    description: "Describe a task and inspect the backend response.",
  },
  "/etl": {
    title: "ETL Studio",
    description: "Extract API data, prepare datasets, and inspect managed results.",
  },
  "/sql": {
    title: "SQL Analyst",
    description: "Ask database questions and inspect read-only SQL results.",
  },
  "/history": {
    title: "Run History",
    description: "Review recent workspace, ETL, and SQL activity.",
  },
};

export default function App() {
  const [path, setPath] = useState(window.location.pathname);
  const [connection, setConnection] = useState<ConnectionState>({
    kind: "checking",
  });
  const [connectionAttempt, setConnectionAttempt] = useState(0);
  const page = pageDetails[path] ? path : "/";

  useEffect(() => {
    const handlePopState = () => setPath(window.location.pathname);
    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, []);

  useEffect(() => {
    let active = true;
    setConnection({ kind: "checking" });

    getBackendInfo()
      .then((info) => {
        if (active) setConnection({ kind: "connected", info });
      })
      .catch((error: unknown) => {
        if (!active) return;
        setConnection({
          kind: "unavailable",
          message:
            error instanceof Error
              ? error.message
              : "The backend could not be reached.",
        });
      });

    return () => {
      active = false;
    };
  }, [connectionAttempt]);

  function navigate(nextPath: string) {
    if (nextPath === page) return;
    window.history.pushState({}, "", nextPath);
    setPath(nextPath);
  }

  const details = pageDetails[page];

  return (
    <AppShell
      currentPath={page}
      onNavigate={navigate}
      title={details.title}
      description={details.description}
      connection={connection}
      onRetryConnection={() => setConnectionAttempt((attempt) => attempt + 1)}
    >
      {page === "/" ? (
        <WorkspacePage
          connection={connection}
          onRetryConnection={() => setConnectionAttempt((attempt) => attempt + 1)}
        />
      ) : page === "/etl" ? <ETLStudioPage /> : page === "/sql" ? <SqlAnalystPage connection={connection} /> : <RunHistoryPage />}
    </AppShell>
  );
}
