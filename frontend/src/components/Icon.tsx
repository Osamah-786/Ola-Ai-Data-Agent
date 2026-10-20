import type { SVGProps } from "react";

export type IconName = "workspace" | "etl" | "sql" | "history" | "arrow" | "spark" | "database" | "menu";

interface IconProps extends SVGProps<SVGSVGElement> {
  name: IconName;
}

export function Icon({ name, ...props }: IconProps) {
  const shared = {
    width: 18,
    height: 18,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.7,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    "aria-hidden": true as const,
    ...props,
  };

  switch (name) {
    case "workspace":
      return <svg {...shared}><rect x="3.5" y="3.5" width="7" height="7" rx="1.5" /><rect x="13.5" y="3.5" width="7" height="7" rx="1.5" /><rect x="3.5" y="13.5" width="7" height="7" rx="1.5" /><rect x="13.5" y="13.5" width="7" height="7" rx="1.5" /></svg>;
    case "etl":
      return <svg {...shared}><path d="M4 6h9M4 12h16M4 18h9" /><circle cx="16" cy="6" r="2" /><circle cx="16" cy="18" r="2" /></svg>;
    case "sql":
      return <svg {...shared}><ellipse cx="12" cy="5" rx="8" ry="3" /><path d="M4 5v7c0 1.7 3.6 3 8 3 1.2 0 2.4-.1 3.4-.3M20 5v4M4 12v7c0 1.7 3.6 3 8 3 1.4 0 2.7-.2 3.8-.5" /><circle cx="18" cy="16" r="3" /><path d="m20.2 18.2 1.3 1.3" /></svg>;
    case "history":
      return <svg {...shared}><circle cx="12" cy="12" r="8.5" /><path d="M12 7v5l3.5 2M4 5v4h4" /></svg>;
    case "arrow":
      return <svg {...shared}><path d="M5 12h14M13 6l6 6-6 6" /></svg>;
    case "spark":
      return <svg {...shared}><path d="m12 3 1.9 5.8L20 11l-6.1 2.2L12 19l-1.9-5.8L4 11l6.1-2.2L12 3Z" /><path d="m19 16 .8 2.2L22 19l-2.2.8L19 22l-.8-2.2L16 19l2.2-.8L19 16Z" /></svg>;
    case "database":
      return <svg {...shared}><ellipse cx="12" cy="5" rx="8" ry="3" /><path d="M4 5v14c0 1.7 3.6 3 8 3s8-1.3 8-3V5M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3" /></svg>;
    case "menu":
      return <svg {...shared}><path d="M4 7h16M4 12h16M4 17h16" /></svg>;
  }
}
