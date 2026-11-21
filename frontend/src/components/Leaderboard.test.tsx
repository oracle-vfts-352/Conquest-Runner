
import { describe, it, expect } from "vitest";
import { createRoot } from "react-dom/client";
import { flushSync } from "react-dom";
import Leaderboard from "./Leaderboard";

describe("Leaderboard", () => {
  it("displays player information", () => {
    const container = document.createElement("div");
    document.body.appendChild(container);
    const root = createRoot(container);

    try {
      flushSync(() => {
        root.render(
          <Leaderboard
            players={[
              {
                id: "1",
                name: "Player One",
                score: 2500,
                territories: 12,
              },
            ]}
          />
        );
      });

      expect(container.textContent).toContain("Player One");
      expect(container.textContent).toContain("2,500");
      expect(container.textContent).toContain("12 territories");
    } finally {
      flushSync(() => root.unmount());
      container.remove();
    }
  });

  it("shows a message when there are no players", () => {
    const container = document.createElement("div");
    document.body.appendChild(container);
    const root = createRoot(container);

    try {
      flushSync(() => {
        root.render(<Leaderboard players={[]} />);
      });

      expect(container.textContent).toContain(
        "No players found."
      );
    } finally {
      flushSync(() => root.unmount());
      container.remove();
    }
  });
});
