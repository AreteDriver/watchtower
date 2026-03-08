import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { HealthBanner } from "../components/HealthBanner";

vi.mock("../api", () => ({
  api: {
    health: vi.fn(),
  },
}));

import { api } from "../api";
const mockHealth = vi.mocked(api.health);

beforeEach(() => {
  mockHealth.mockReset();
});

describe("HealthBanner", () => {
  it("renders nothing when health call fails", async () => {
    mockHealth.mockRejectedValue(new Error("fail"));
    const { container } = render(<HealthBanner />);
    // Wait for the effect to fire
    await waitFor(() => {
      expect(mockHealth).toHaveBeenCalled();
    });
    expect(container.innerHTML).toBe("");
  });

  it("renders table counts when health data loads", async () => {
    mockHealth.mockResolvedValue({
      status: "ok",
      tables: { events: 1234, kills: 567 },
    });
    render(<HealthBanner />);
    await waitFor(() => {
      expect(screen.getByText("1,234")).toBeInTheDocument();
    });
    expect(screen.getByText("events")).toBeInTheDocument();
    expect(screen.getByText("567")).toBeInTheDocument();
    expect(screen.getByText("kills")).toBeInTheDocument();
  });

  it("calls health API on mount", async () => {
    mockHealth.mockResolvedValue({
      status: "ok",
      tables: { entities: 10 },
    });
    render(<HealthBanner />);
    await waitFor(() => {
      expect(mockHealth).toHaveBeenCalledTimes(1);
    });
  });
});
