import { describe, it, expect } from "vitest";
import { validateCvFile, MAX_CV_BYTES } from "./cv-file";

function fakeFile(name: string, type: string, size: number): File {
  const f = new File(["x"], name, { type });
  Object.defineProperty(f, "size", { value: size });
  return f;
}

describe("validateCvFile", () => {
  it("accepts a normal PDF by mime type", () => {
    expect(validateCvFile(fakeFile("cv.pdf", "application/pdf", 1000))).toEqual({
      ok: true,
    });
  });

  it("accepts a PDF by extension when mime type is missing", () => {
    expect(validateCvFile(fakeFile("Lebenslauf.PDF", "", 1000)).ok).toBe(true);
  });

  it("rejects a non-PDF file", () => {
    const r = validateCvFile(fakeFile("photo.png", "image/png", 1000));
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.error).toMatch(/pdf/i);
  });

  it("rejects an empty file", () => {
    const r = validateCvFile(fakeFile("cv.pdf", "application/pdf", 0));
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.error).toMatch(/empty/i);
  });

  it("rejects a file larger than the size cap", () => {
    const r = validateCvFile(
      fakeFile("cv.pdf", "application/pdf", MAX_CV_BYTES + 1),
    );
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.error).toMatch(/large/i);
  });
});
