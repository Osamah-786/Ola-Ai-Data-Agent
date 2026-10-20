import type { MouseEvent } from "react";
import { Icon } from "./Icon";

interface SidebarProps {
  currentPath: string;
  onNavigate: (path: string) => void;
}

const items = [
  { path: "/", label: "Workspace", icon: "workspace" },
  { path: "/etl", label: "ETL Studio", icon: "etl" },
  { path: "/sql", label: "SQL Analyst", icon: "sql" },
  { path: "/history", label: "Run History", icon: "history" },
] as const;

export function Sidebar({ currentPath, onNavigate }: SidebarProps) {
  function handleNavigation(event: MouseEvent<HTMLAnchorElement>, path: string) {
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    onNavigate(path);
  }

  return (
    <aside className="sidebar">
      <a className="brand" href="/" onClick={(event) => handleNavigation(event, "/")}>
        <span className="brand__mark" aria-hidden="true">O</span>
        <span className="brand__copy">
          <span className="brand__name">Ola</span>
          <span className="brand__product">AI Data Agent</span>
        </span>
      </a>

      <div className="sidebar__section-label">Workspace</div>
      <nav className="sidebar__nav" aria-label="Main navigation">
        {items.map((item) => (
          <a
            className={`nav-item ${currentPath === item.path ? "nav-item--active" : ""}`}
            href={item.path}
            key={item.path}
            onClick={(event) => handleNavigation(event, item.path)}
            aria-current={currentPath === item.path ? "page" : undefined}
          >
            <Icon name={item.icon} />
            <span>{item.label}</span>
          </a>
        ))}
      </nav>

      <div className="sidebar__bottom">
        <div className="sidebar-note">
          <span className="sidebar-note__icon"><Icon name="spark" /></span>
          <p>Describe a data task. Inspect the response. Connect workflows as they become available.</p>
        </div>
        <div className="sidebar__footer">
          <span className="environment-indicator"><span /> Development environment</span>
          <span className="sidebar__version">Local workspace</span>
        </div>
      </div>
    </aside>
  );
}
