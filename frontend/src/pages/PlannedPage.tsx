import { Icon } from "../components/Icon";

interface PlannedPageProps {
  page: "etl" | "sql";
}

const details = {
  etl: {
    label: "ETL STUDIO",
    title: "A focused space for data workflows.",
    description:
      "The ETL Studio will support API extraction, dataset transformations, previews, and managed downloads.",
    phase: "Phase 4",
    icon: "etl",
  },
  sql: {
    label: "SQL ANALYST",
    title: "Explore database questions with context.",
    description:
      "The SQL Analyst will present query safety, bounded result tables, and plain-language explanations.",
    phase: "Phase 5",
    icon: "sql",
  },
} as const;

export function PlannedPage({ page }: PlannedPageProps) {
  const item = details[page];

  return (
    <section className="planned-page">
      <div className="planned-page__card">
        <div className="planned-page__icon"><Icon name={item.icon} /></div>
        <span className="planned-page__eyebrow">{item.label} · PLANNED WORKFLOW</span>
        <h2>{item.title}</h2>
        <p>{item.description}</p>
        <div className="planned-page__phase">
          <span className="planned-page__phase-mark" />
          <span>Planned for {item.phase}</span>
        </div>
        <p className="planned-page__note">
          This page is a navigation placeholder. No extraction, transformation, or database query runs here.
        </p>
      </div>
    </section>
  );
}
