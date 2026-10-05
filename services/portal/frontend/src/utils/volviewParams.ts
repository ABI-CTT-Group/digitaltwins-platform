import type { AssayGuiContext } from "@/models/types";

// VolView reads `urls` and `names` from the page query at mount, as bracketed, comma-separated
// lists. (Its `token` param only feeds its legacy fetch and DICOMweb client, not the `urls=`
// stream download, so the bearer goes in a cookie instead: see assayFileCookie.ts.)
// vtk.js percent-decodes each value once before VolView splits on ",", so each value is encoded
// exactly once here, and a file whose name or URL would still hold "," "[" or "]" after that
// decode cannot be passed and is skipped.
const UNSAFE = /[,[\]]/;

const decoded = (url: string) => {
  try {
    return decodeURIComponent(url);
  } catch {
    return url;
  }
};

export function buildVolViewQuery(ctx: AssayGuiContext): string {
  const files = ctx.inputs.flatMap((input) => input.files).filter((file) => {
    const safe = !UNSAFE.test(file.name) && !UNSAFE.test(decoded(file.url));
    if (!safe) console.warn(`Skipping ${file.name}: VolView cannot load a file whose name contains "," "[" or "]"`);
    return safe;
  });
  const parts = [
    `assay=${encodeURIComponent(ctx.assayId)}`,
    `urls=${encodeURIComponent(`[${files.map((f) => f.url).join(",")}]`)}`,
    `names=${encodeURIComponent(`[${files.map((f) => f.name).join(",")}]`)}`,
  ];
  return `?${parts.join("&")}`;
}
