import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiDocsPage } from "./ApiDocsPage";
import { useOpenApiSchema } from "../hooks/useOpenApiSchema";

vi.mock("../hooks/useOpenApiSchema", () => ({
  useOpenApiSchema: vi.fn(),
}));

afterEach(cleanup);

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
  it("groups schema endpoints by tag and filters them by search", () => {
    vi.mocked(useOpenApiSchema).mockReturnValue({
      data: schema,
      isLoading: false,
      isError: false,
    } as any);

        render(
      <MemoryRouter>
        <ApiDocsPage />
      </MemoryRouter>,
    );

    expect(screen.getByRole("heading", { name: "auth" })).toBeInTheDocument();
    expect(screen.getByText("Current user")).toBeInTheDocument();
    expect(screen.getByText("List lessons")).toBeInTheDocument();

    fireEvent.change(
      screen.getByRole("textbox", { name: "Search API endpoints" }),
      { target: { value: "lessons" } },
    );

    expect(screen.queryByText("Current user")).not.toBeInTheDocument();
    expect(screen.getByText("List lessons")).toBeInTheDocument();
  });
});

describe("ApiDocsPage with a real-shaped schema (Issue #3075)", () => {
  const refSchema = {
    info: { title: "Atelier API", version: "1.0.0" },
    paths: {
      "/auth/register/": {
        post: {
          summary: "Register",
          tags: ["auth"],
          requestBody: {
            content: {
              "application/json": {
                schema: { $ref: "#/components/schemas/Register" },
              },
            },
          },
          responses: {
            "201": {
              description: "Created",
              content: {
                "application/json": {
                  schema: { $ref: "#/components/schemas/Profile" },
                },
              },
            },
          },
        },
      },
    },
    components: {
      schemas: {
        Register: {
          type: "object",
          required: ["email"],
          properties: {
            email: { type: "string", example: "dev@example.com" },
            password: { type: "string", example: "s3cret-pass" },
          },
        },
        Profile: {
          type: "object",
          properties: {
            id: { type: "integer" },
            display_name: { type: "string", example: "Ada" },
          },
        },
      },
    },
  };

  const renderPage = () => {
    vi.mocked(useOpenApiSchema).mockReturnValue({
      data: refSchema,
      isLoading: false,
      isError: false,
    } as any);
    return render(
      <MemoryRouter>
        <ApiDocsPage />
      </MemoryRouter>,
    );
  };

  it("shows the real request and response fields behind $ref, not an empty object", () => {
    renderPage();
    const bodies = screen
      .getAllByText(/\{/, { selector: "pre" })
      .map((node) => node.textContent ?? "");
    const request = bodies.find((text) => text.includes("dev@example.com"));
    const response = bodies.find((text) => text.includes("display_name"));
    expect(request).toContain("password");
    expect(response).toContain("id");
    expect(bodies).not.toContain("{}");
  });

  it("offers the Config Generator link once, with a single icon", () => {
    renderPage();
    const link = screen.getByRole("link", { name: /Config Generator Wizard/ });
    expect(link).toHaveTextContent(/^\s*Config Generator Wizard\s*$/);
    expect(link.querySelectorAll("svg")).toHaveLength(1);
  });
});
