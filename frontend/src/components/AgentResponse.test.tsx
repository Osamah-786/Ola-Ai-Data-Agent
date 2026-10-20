import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { runAgent } from "../api/client";
import { WorkspacePage } from "../pages/WorkspacePage";
import type { BackendInfo } from "../types";
import { AgentResponse } from "./AgentResponse";

vi.mock("../api/client", () => ({ runAgent: vi.fn() }));

const mockedRunAgent = vi.mocked(runAgent);
const backendInfo: BackendInfo = {
  health: { status: "ok", service: "ola-ai-data-agent-api", mode: "mock" },
  metadata: null,
};
const longText = "A long response paragraph that should wrap inside the response panel. ".repeat(12).trim();

beforeEach(() => mockedRunAgent.mockReset());

describe("Workspace agent responses", () => {
  it("renders Markdown structure, a GFM table, long text, and hides server file paths", async () => {
    mockedRunAgent.mockResolvedValue({
      status: "ok",
      mode: "agent",
      route: "etl",
      request_id: "mock-request-1",
      answer: `# Pokémon extraction\n\nFetched the **first page** successfully.\n\n## Details\n\n1. **Records:** 20\n2. **Columns:** name and URL\n\n- The data is ready.\n- The response includes a [PokéAPI link](https://pokeapi.co/).\n\n\`\`\`text\nconst count = 20;\n\`\`\`\n\n| Name | URL |\n| --- | --- |\n| bulbasaur | https://pokeapi.co/api/v2/pokemon/1 |\n\nServer file: \`C:\\Users\\Osamah\\project\\output.csv\`\n\n<script>alert(1)</script>\n\n[unsafe](javascript:alert(1))\n\n![remote image](https://example.invalid/pixel.png)\n\n${longText}`,
    });

    render(<WorkspacePage connection={{ kind: "connected", info: backendInfo }} onRetryConnection={vi.fn()} />);
    fireEvent.change(screen.getByRole("textbox", { name: "Describe your data task" }), {
      target: { value: "Summarize the returned data" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Run Agent/ }));

    expect(await screen.findByRole("heading", { name: "Pokémon extraction" })).toBeInTheDocument();
    expect(screen.getByText("first page", { exact: false })).toBeInTheDocument();
    expect(screen.getAllByRole("list")).toHaveLength(2);
    expect(screen.getByRole("table")).toHaveTextContent("bulbasaur");
    expect(screen.getByRole("link", { name: "PokéAPI link" })).toHaveAttribute("href", "https://pokeapi.co/");
    expect(screen.queryByRole("link", { name: "unsafe" })).not.toBeInTheDocument();
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /download/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Data preview" })).not.toBeInTheDocument();
    expect(document.querySelector("script:not([type])")).not.toBeInTheDocument();
    expect(screen.getByText("const count = 20;")).toBeInTheDocument();
    expect(document.body.textContent).toContain("server file path hidden");
    expect(document.body.textContent).not.toContain("C:\\Users\\Osamah");
    expect(document.body.textContent).toContain(longText);
    expect(screen.getByText("Succeeded")).toBeInTheDocument();
    expect(screen.getByText("ETL")).toBeInTheDocument();
    expect(screen.getByText("mock-request-1")).toBeInTheDocument();
    expect(screen.getByText("Agent response")).toBeInTheDocument();
  });

  it("shows structured error responses in a separate warning section", () => {
    render(
      <AgentResponse
        response={{
          status: "error",
          answer: "## Request failed\n\nThe backend could not complete the request.",
          route: "sql",
          mode: "agent",
          request_id: "failed-request",
        }}
      />,
    );

    expect(screen.getByRole("alert", { name: "Warnings or errors" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Request failed" })).toBeInTheDocument();
    expect(screen.getByText("Failed")).toBeInTheDocument();
    expect(screen.getByText("SQL")).toBeInTheDocument();
  });

});
