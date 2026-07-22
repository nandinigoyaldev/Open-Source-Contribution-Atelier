import { render, screen } from "@testing-library/react";
import DXDashboard from "../DXDashboard";
import { expect, test, vi } from "vitest";

// Mock fetch API globally for this test file
global.fetch = vi.fn(() =>
  Promise.resolve({
    json: () => Promise.resolve([]),
  }),
) as any;

test("DXDashboard renders loading state initially", () => {
  render(<DXDashboard />);
  expect(screen.getByText(/Loading DX Metrics/i)).toBeInTheDocument();
});
