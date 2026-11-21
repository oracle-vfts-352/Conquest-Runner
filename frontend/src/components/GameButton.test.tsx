
import { describe, it, expect, vi } from "vitest";
import { createRoot } from "react-dom/client";
import { flushSync } from "react-dom";
import GameButton from "./GameButton";

describe("GameButton", () => {
  it("shows the label and responds to clicks", () => {
    const container = document.createElement("div");
    document.body.appendChild(container);

    const root = createRoot(container);
    const handleClick = vi.fn();

    try {
      flushSync(() => {
        root.render(
          <GameButton
            label="START RUN"
            onClick={handleClick}
          />
        );
      });

      const button = container.querySelector("button");

      expect(button?.textContent).toContain("START RUN");

      button?.click();

      expect(handleClick).toHaveBeenCalledTimes(1);
    } finally {
      flushSync(() => root.unmount());
      container.remove();
    }
  });
});
