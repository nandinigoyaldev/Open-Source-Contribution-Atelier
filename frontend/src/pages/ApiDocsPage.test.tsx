import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ApiDocsPage } from "./ApiDocsPage";
import { useOpenApiSchema } from "../hooks/useOpenApiSchema";

vi.mock("../hooks/useOpenApiSchema", () => ({
  useOpenApiSchema: vi.fn(),
}));

const schema = {
  info: { title: "Atelier API", version: "1.0.0" },
  paths: {
    "/auth/me/": {
      get: {
        summary: "Current user",
        tags: ["auth"],
        responses: { "200": { description: "OK" } },
      },
    },
    "/content/lessons/": {
      get: {
        summary: "List lessons",
        tags: ["lessons"],
        responses: { "200": { description: "OK" } },
      },
    },
  },
};

describe("ApiDocsPage", () => {
  it("groups schema endpoints by tag and filters them by search", async () => {
    vi.mocked(useOpenApiSchema).mockReturnValue({
      data: schema,
      isLoading: false,
      isError: false,
    } as ReturnType<typeof useOpenApiSchema>);

    const user = userEvent.setup();
    render(<ApiDocsPage />);

    expect(screen.getByRole("heading", { name: "auth" })).toBeInTheDocument();
    expect(screen.getByText("Current user")).toBeInTheDocument();
    expect(screen.getByText("List lessons")).toBeInTheDocument();

    await user.type(
      screen.getByRole("textbox", { name: "Search API endpoints" }),
      "lessons",
    );

    expect(screen.queryByText("Current user")).not.toBeInTheDocument();
    expect(screen.getByText("List lessons")).toBeInTheDocument();
  });
});
