import { describe, it, expect } from "vitest";
import { fitBand, fitColor } from "./graph-bands";

describe("fitBand", () => {
  it("bands at the shared 70/50 thresholds", () => {
    expect(fitBand(0)).toBe("weak");
    expect(fitBand(49)).toBe("weak");
    expect(fitBand(50)).toBe("good");
    expect(fitBand(69)).toBe("good");
    expect(fitBand(70)).toBe("strong");
    expect(fitBand(100)).toBe("strong");
  });
});

describe("fitColor", () => {
  it("maps each band to its token color", () => {
    expect(fitColor(80)).toBe("hsl(var(--status-offer))");
    expect(fitColor(60)).toBe("#eab308");
    expect(fitColor(10)).toBe("hsl(var(--status-rejected))");
  });
});
