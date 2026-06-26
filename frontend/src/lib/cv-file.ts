/** Max CV upload size accepted by the client before we even hit the API. */
export const MAX_CV_BYTES = 10 * 1024 * 1024; // 10 MB

export type CvFileValidation = { ok: true } | { ok: false; error: string };

/** Client-side guard for CV uploads (drag-drop or picker): enforce PDF,
 * non-empty, and a sane size cap so we fail fast with a clear message. */
export function validateCvFile(file: File): CvFileValidation {
  const isPdf =
    file.type === "application/pdf" || /\.pdf$/i.test(file.name);
  if (!isPdf) {
    return { ok: false, error: "Please upload a PDF file." };
  }
  if (file.size === 0) {
    return { ok: false, error: "That file is empty." };
  }
  if (file.size > MAX_CV_BYTES) {
    return { ok: false, error: "That file is too large (max 10 MB)." };
  }
  return { ok: true };
}
