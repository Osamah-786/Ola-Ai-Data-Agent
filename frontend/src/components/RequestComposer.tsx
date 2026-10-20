import { useRef } from "react";
import type { FormEvent } from "react";
import { Icon } from "./Icon";

export const MAX_MESSAGE_LENGTH = 4000;

export const examplePrompts = [
  "Extract Pokémon data from a public API and save it as CSV.",
  "Remove duplicate rows from a dataset.",
  "Find the average fare for completed rides.",
];

interface RequestComposerProps {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  isPending: boolean;
  executionMode: "mock" | "live";
  onExecutionModeChange: (mode: "mock" | "live") => void;
}

export function RequestComposer({
  value,
  onChange,
  onSubmit,
  isPending,
  executionMode,
  onExecutionModeChange,
}: RequestComposerProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const isBlank = value.trim().length === 0;
  const isOverLimit = value.length > MAX_MESSAGE_LENGTH;

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!isBlank && !isOverLimit && !isPending) onSubmit();
  }

  function useExample(prompt: string) {
    onChange(prompt);
    textareaRef.current?.focus();
  }

  return (
    <section className="composer-card" aria-labelledby="composer-title">
      <div className="section-heading">
        <div className="section-heading__icon"><Icon name="spark" /></div>
        <div>
          <h2 id="composer-title">What would you like to work on?</h2>
          <p>Describe a data task in plain language to get started.</p>
        </div>
      </div>

      <form onSubmit={handleSubmit}>
        <fieldset className="execution-mode" disabled={isPending}>
          <legend>Execution mode</legend>
          <label>
            <input
              type="radio"
              name="execution-mode"
              value="mock"
              checked={executionMode === "mock"}
              onChange={() => onExecutionModeChange("mock")}
            />
            <span><strong>Mock mode</strong> — deterministic response; no real agent calls.</span>
          </label>
          <label>
            <input
              type="radio"
              name="execution-mode"
              value="live"
              checked={executionMode === "live"}
              onChange={() => onExecutionModeChange("live")}
            />
            <span><strong>Live agent mode</strong> — asks the server to run the existing router.</span>
          </label>
          {executionMode === "live" && (
            <p role="note">
              Live mode can consume Groq API quota. ETL requests may access external APIs, and SQL requests may access the configured PostgreSQL database. The server must also explicitly enable live execution.
            </p>
          )}
        </fieldset>
        <label className="sr-only" htmlFor="agent-message">Describe your data task</label>
        <textarea
          ref={textareaRef}
          id="agent-message"
          className="request-input"
          value={value}
          onChange={(event) => onChange(event.target.value)}
          placeholder="Describe what you want to do with your data..."
          maxLength={MAX_MESSAGE_LENGTH}
          rows={5}
          aria-describedby="request-guidance request-count"
          disabled={isPending}
        />
        <div className="composer-card__controls">
          <span
            id="request-count"
            className={`character-count ${isOverLimit ? "character-count--error" : ""}`}
            aria-live="polite"
          >
            {value.length.toLocaleString()} / {MAX_MESSAGE_LENGTH.toLocaleString()}
          </span>
          <button
            type="submit"
            className="button button--primary"
            disabled={isBlank || isOverLimit || isPending}
          >
            {isPending ? (
              <><span className="button-spinner" aria-hidden="true" /> Sending…</>
            ) : (
              <>Run Agent <Icon name="arrow" /></>
            )}
          </button>
        </div>
      </form>
      <p className="input-guidance" id="request-guidance">
        Requests are limited to 4,000 characters. Mock mode is the default; live mode also requires server approval.
      </p>

      <div className="examples">
        <div className="examples__label">TRY AN EXAMPLE</div>
        <div className="examples__list">
          {examplePrompts.map((prompt) => (
            <button
              className="example-prompt"
              key={prompt}
              type="button"
              onClick={() => useExample(prompt)}
              disabled={isPending}
            >
              <span>{prompt}</span>
              <Icon name="arrow" />
            </button>
          ))}
        </div>
      </div>
    </section>
  );
}
