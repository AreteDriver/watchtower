import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SearchBar } from "../components/SearchBar";

// Mock the api module
vi.mock("../api", () => ({
  api: {
    search: vi.fn(),
  },
}));

import { api } from "../api";
const mockSearch = vi.mocked(api.search);

beforeEach(() => {
  mockSearch.mockReset();
});

describe("SearchBar", () => {
  it("renders the search input", () => {
    render(<SearchBar onSelect={vi.fn()} />);
    expect(
      screen.getByPlaceholderText("Search entities...")
    ).toBeInTheDocument();
  });

  it("does not search for queries shorter than 2 characters", async () => {
    const user = userEvent.setup();
    render(<SearchBar onSelect={vi.fn()} />);
    await user.type(screen.getByPlaceholderText("Search entities..."), "a");
    expect(mockSearch).not.toHaveBeenCalled();
  });

  it("calls api.search when typing 2+ characters", async () => {
    mockSearch.mockResolvedValue({ results: [] });
    const user = userEvent.setup();
    render(<SearchBar onSelect={vi.fn()} />);
    await user.type(screen.getByPlaceholderText("Search entities..."), "te");
    await waitFor(() => {
      expect(mockSearch).toHaveBeenCalled();
    });
  });

  it("displays search results as buttons", async () => {
    mockSearch.mockResolvedValue({
      results: [
        {
          entity_id: "ent-1",
          entity_type: "character",
          display_name: "TestPilot",
          event_count: 42,
        },
      ],
    });
    const user = userEvent.setup();
    render(<SearchBar onSelect={vi.fn()} />);
    await user.type(screen.getByPlaceholderText("Search entities..."), "Test");
    await waitFor(() => {
      expect(screen.getByText("TestPilot")).toBeInTheDocument();
    });
    expect(screen.getByText("42 events")).toBeInTheDocument();
    expect(screen.getByText("CHARACTER")).toBeInTheDocument();
  });

  it("calls onSelect when a result is clicked", async () => {
    mockSearch.mockResolvedValue({
      results: [
        {
          entity_id: "ent-1",
          entity_type: "character",
          display_name: "TestPilot",
          event_count: 10,
        },
      ],
    });
    const onSelect = vi.fn();
    const user = userEvent.setup();
    render(<SearchBar onSelect={onSelect} />);
    await user.type(screen.getByPlaceholderText("Search entities..."), "Test");
    await waitFor(() => {
      expect(screen.getByText("TestPilot")).toBeInTheDocument();
    });
    await user.click(screen.getByText("TestPilot"));
    expect(onSelect).toHaveBeenCalledWith("ent-1");
  });
});
