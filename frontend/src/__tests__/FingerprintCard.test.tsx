import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { FingerprintCard } from "../components/FingerprintCard";
import type { Fingerprint } from "../api";

const mockFingerprint: Fingerprint = {
  entity_id: "0xabc123def456789012345678",
  entity_type: "character",
  event_count: 150,
  temporal: {
    peak_hour: "14:00",
    peak_hour_pct: 25,
    active_hours: 8,
    entropy: 3.2,
    predictability: "Moderately Predictable",
  },
  route: {
    top_gate: "gate-alpha",
    top_gate_pct: 40,
    unique_gates: 5,
    unique_systems: 3,
    route_entropy: 2.1,
    predictability: "Predictable",
  },
  social: {
    top_associate: "friend-1",
    top_associate_count: 20,
    unique_associates: 10,
    solo_ratio: 60,
    top_5_associates: [
      { id: "friend-1", count: 20 },
      { id: "friend-2", count: 15 },
    ],
  },
  threat: {
    kill_ratio: 0.75,
    kills_per_day: 2.5,
    deaths_per_day: 0.8,
    threat_level: "high",
    combat_zones: 4,
  },
  opsec_score: 55,
  opsec_rating: "Moderate",
};

describe("FingerprintCard", () => {
  it("renders entity type profile header", () => {
    render(<FingerprintCard fp={mockFingerprint} />);
    expect(screen.getByText("character profile")).toBeInTheDocument();
  });

  it("renders truncated entity ID", () => {
    render(<FingerprintCard fp={mockFingerprint} />);
    expect(
      screen.getByText("0xabc123def456789012345678".slice(0, 24))
    ).toBeInTheDocument();
  });

  it("renders event count", () => {
    render(<FingerprintCard fp={mockFingerprint} />);
    expect(screen.getByText("150 events analyzed")).toBeInTheDocument();
  });

  it("renders threat level badge", () => {
    render(<FingerprintCard fp={mockFingerprint} />);
    expect(screen.getByText("high")).toBeInTheDocument();
  });

  it("renders opsec score and rating", () => {
    render(<FingerprintCard fp={mockFingerprint} />);
    expect(screen.getByText("55")).toBeInTheDocument();
    expect(screen.getByText("Moderate")).toBeInTheDocument();
    expect(screen.getByText("OPSEC")).toBeInTheDocument();
  });

  it("renders peak hour info", () => {
    render(<FingerprintCard fp={mockFingerprint} />);
    expect(screen.getByText("14:00")).toBeInTheDocument();
  });

  it("renders kill ratio", () => {
    render(<FingerprintCard fp={mockFingerprint} />);
    expect(screen.getByText("0.75")).toBeInTheDocument();
  });

  it("renders combat zones count", () => {
    render(<FingerprintCard fp={mockFingerprint} />);
    expect(screen.getByText("4")).toBeInTheDocument();
  });

  it("renders top associates for character type", () => {
    render(<FingerprintCard fp={mockFingerprint} />);
    expect(screen.getByText("Top associates:")).toBeInTheDocument();
    expect(screen.getByText("friend-1")).toBeInTheDocument();
  });

  it("renders section headers", () => {
    render(<FingerprintCard fp={mockFingerprint} />);
    expect(screen.getByText("Activity Pattern")).toBeInTheDocument();
    expect(screen.getByText("Movement")).toBeInTheDocument();
    expect(screen.getByText("Intel")).toBeInTheDocument();
  });
});
