import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ItineraryView } from "@/components/blocks/ItineraryView";
import { RouteSummary } from "@/components/blocks/InfoBlocks";
import type { ItineraryPlan, Place, RouteResult } from "@/lib/types";

const place = (id: string, name: string): Place => ({
  id, name, types: [], tags: ["heritage"], opening_hours: [], photos: [], data_origin: "demo", provider: "demo_dataset",
});

const plan: ItineraryPlan = {
  destination: "Jaipur",
  data_origin: "demo",
  provider: "demo_dataset",
  generated_at: "2026-10-28T00:00:00Z",
  excluded_place_ids: [],
  assumptions: ["Transfer times are rough estimates."],
  warnings: ["Demo mode: sample data."],
  unplaced: [place("p9", "Albert Hall Museum")],
  budget_estimate: null,
  days: [
    { day: 1, title: "Amber Fort", breaks: [], notes: [], stops: [
      { id: "s1", place: place("p1", "Amber Fort"), start_time: "09:00", end_time: "11:30", duration_minutes: 150,
        transfer_is_estimate: true, reason: "Matches your interest in heritage.", notes: ["Opening hours not verified — check before visiting."], hours_verified: false },
      { id: "s2", place: place("p2", "Jal Mahal"), start_time: "11:55", end_time: "12:25", duration_minutes: 30,
        transfer_minutes_before: 25, transfer_is_estimate: true, reason: "Fills the day.", notes: [], hours_verified: false },
    ] },
    { day: 2, title: "Hawa Mahal", breaks: [], notes: [], stops: [] },
  ],
};

describe("ItineraryView", () => {
  it("labels sample data, estimates and unverified hours", () => {
    render(<ItineraryView plan={plan} showMap={false} />);
    expect(screen.getByText("Sample data")).toBeInTheDocument();
    expect(screen.getByText(/~25 min transfer \(estimate\)/)).toBeInTheDocument();
    expect(screen.getByText(/Opening hours not verified/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Remove Amber Fort/ })).not.toBeInTheDocument(); // read-only
  });

  it("sends edit operations for each control", async () => {
    const apply = vi.fn().mockResolvedValue(undefined);
    render(<ItineraryView plan={plan} showMap={false} editor={{ apply, busy: false }} />);
    await userEvent.click(screen.getByRole("button", { name: "Remove Amber Fort" }));
    expect(apply).toHaveBeenLastCalledWith([{ op: "remove_stop", stop_id: "s1" }]);
    await userEvent.click(screen.getByRole("button", { name: "Move Jal Mahal earlier" }));
    expect(apply).toHaveBeenLastCalledWith([{ op: "move_stop", stop_id: "s2", to_day: 1, position: 0 }]);
    expect(screen.getByRole("button", { name: "Move Amber Fort earlier" })).toBeDisabled();
    await userEvent.click(screen.getByRole("button", { name: /Add a day/ }));
    expect(apply).toHaveBeenLastCalledWith([{ op: "add_day" }]);
    await userEvent.selectOptions(screen.getByRole("combobox", { name: "Move Amber Fort to another day" }), "2");
    expect(apply).toHaveBeenLastCalledWith([{ op: "move_stop", stop_id: "s1", to_day: 2 }]);
    await userEvent.click(screen.getByRole("button", { name: "Add" }));
    expect(apply).toHaveBeenLastCalledWith([{ op: "add_stop", day: 1, place_id: "p9" }]);
  });

  it("disables controls while saving", () => {
    render(<ItineraryView plan={plan} showMap={false} editor={{ apply: vi.fn(), busy: true }} />);
    expect(screen.getByRole("button", { name: "Remove Amber Fort" })).toBeDisabled();
  });
});

describe("RouteSummary", () => {
  it("never shows a road distance without a routing provider", () => {
    const route: RouteResult = { available: false, provider: "none", travel_mode: "DRIVE", origin: "Ahmedabad",
      destination: "Udaipur", stops: [], legs: [], warnings: [], straight_line_km: 209,
      notice: "Road distance and travel time need a routing provider." };
    render(<RouteSummary route={route} />);
    expect(screen.queryByText("Road distance")).not.toBeInTheDocument();
    expect(screen.getByText(/Straight-line \(not road\) distance: ~209 km/)).toBeInTheDocument();
  });

  it("shows provider distance and duration when available", () => {
    const route: RouteResult = { available: true, provider: "google_routes", travel_mode: "DRIVE", origin: "A",
      destination: "B", stops: [], legs: [], warnings: [], distance_meters: 233000, duration_seconds: 14400 };
    render(<RouteSummary route={route} />);
    expect(screen.getByText("233 km")).toBeInTheDocument();
    expect(screen.getByText("Source: Google Routes")).toBeInTheDocument();
  });
});
