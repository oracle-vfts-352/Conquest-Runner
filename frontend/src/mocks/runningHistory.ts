
import type { RunRecord } from "../components/RunningHistory";

export const mockRunningHistory: RunRecord[] = [
  {
    id: "run-1",
    title: "Morning Run",
    date: "2026-11-08",
    distanceKm: 4.2,
    durationSeconds: 1710,
  },
  {
    id: "run-2",
    title: "Evening Run",
    date: "2026-11-05",
    distanceKm: 3.1,
    durationSeconds: 1335,
  },
  {
    id: "run-3",
    title: "Weekend Run",
    date: "2026-11-02",
    distanceKm: 5.6,
    durationSeconds: 2360,
  },
];
