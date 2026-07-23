import { describe, it, expect } from "vitest";
import {
  emptySelection,
  toggleId,
  selectAll,
  clearSelection,
  enterSelectMode,
  exitSelectMode,
} from "../selection";

describe("selection", () => {
  it("starts empty and not in select mode", () => {
    const s = emptySelection();
    expect(s.mode).toBe(false);
    expect(s.ids.size).toBe(0);
  });

  it("toggles an id on and off", () => {
    let s = emptySelection();
    s = toggleId(s, "a");
    expect(s.ids.has("a")).toBe(true);
    s = toggleId(s, "a");
    expect(s.ids.has("a")).toBe(false);
  });

  it("does not mutate the input state", () => {
    const s = emptySelection();
    const next = toggleId(s, "a");
    expect(s.ids.size).toBe(0);
    expect(next.ids.size).toBe(1);
  });

  it("selectAll replaces the id set", () => {
    const s = selectAll(emptySelection(), ["a", "b", "c"]);
    expect(Array.from(s.ids).sort()).toEqual(["a", "b", "c"]);
  });

  it("clearSelection empties ids but keeps mode", () => {
    const s = clearSelection(enterSelectMode(selectAll(emptySelection(), ["a"])));
    expect(s.mode).toBe(true);
    expect(s.ids.size).toBe(0);
  });

  it("exitSelectMode resets mode and ids", () => {
    const s = exitSelectMode();
    expect(s.mode).toBe(false);
    expect(s.ids.size).toBe(0);
  });
});
