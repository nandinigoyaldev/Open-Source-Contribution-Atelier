import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { ResponsiveTable } from "../components/ui/ResponsiveTable";

// Return a deterministic visible row instead of relying on browser layout.
vi.mock("@tanstack/react-virtual", () => ({
  useVirtualizer: (options: {
    count: number;
    getItemKey: (index: number) => string | number;
  }) => ({
    getVirtualItems: () =>
      options.count > 0
        ? [
            {
              index: 0,
              key: options.getItemKey(0),
              start: 0,
              end: 50,
              size: 50,
              lane: 0,
            },
          ]
        : [],
    getTotalSize: () => options.count * 50,
    measureElement: () => undefined,
  }),
}));

describe("ResponsiveTable Component", () => {
  const columns = [
    { header: "ID", accessor: "id" as const, label: "Identifier" },
    { header: "Name", accessor: "name" as const },
    {
      header: "Role",
      accessor: (item: { id: number; name: string; role: string }) => (
        <span data-testid="role">{item.role}</span>
      ),
    },
  ];

  const data = [
    { id: 1, name: "Alice", role: "Admin" },
    { id: 2, name: "Bob", role: "User" },
  ];

  it("renders both desktop table and mobile card layouts", () => {
    const { container } = render(
      <ResponsiveTable
        columns={columns}
        data={data}
        keyExtractor={(item) => item.id.toString()}
      />,
    );

    const table = container.querySelector("table");
    expect(table).toBeInTheDocument();

    expect(screen.getAllByText("ID").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Name").length).toBeGreaterThan(0);

    expect(screen.getAllByText("Identifier").length).toBe(2);
    expect(screen.getAllByTestId("role").length).toBe(4);
  });

  it("renders empty message when no data is provided", () => {
    render(
      <ResponsiveTable
        columns={columns}
        data={[]}
        keyExtractor={(item) => item.id.toString()}
        emptyMessage="No records found"
      />,
    );

    expect(screen.getAllByText("No records found").length).toBe(2);
  });

  it("preserves accessible table semantics and keyboard-accessible links when virtualized", () => {
    const testData = [{ id: "alice", name: "Alice", role: "Maintainer" }];

    const { container } = render(
      <ResponsiveTable
        columns={[
          {
            header: "Contributor",
            accessor: (item) => (
              <a href={`/contributors/${item.id}`}>{item.name}</a>
            ),
          },
        ]}
        data={testData}
        keyExtractor={(item) => item.id}
        virtualized={true}
        containerHeight="300px"
      />,
    );

    const table = container.querySelector("table");

    expect(table).toBeInTheDocument();
    expect(table?.querySelector("thead th")?.textContent).toBe("Contributor");

    const link = table?.querySelector('tbody a[href="/contributors/alice"]');

    expect(link).toBeInTheDocument();
    expect(link).toHaveProperty("tabIndex", 0);
    expect(link?.closest("tr")).toBeInTheDocument();
    expect(link?.closest("tr")).not.toHaveAttribute("aria-hidden");
  });
});
