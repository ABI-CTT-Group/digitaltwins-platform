// Best-effort extraction of the `sample type` column from a SPARC
// `samples.xlsx` so the Information step can pre-fill the dataset description.
//
// Everything here is non-throwing: a missing file, a missing column, an
// unreadable workbook, or empty cells all resolve to "no sample types" rather
// than surfacing an error. The caller treats an empty result as "nothing to
// fill" and the upload flow is never blocked by parsing.

/** Basename we look for inside the dropped folder (case-insensitive). */
const SAMPLES_FILENAME = 'samples.xlsx';

/** Header we want, in normalized form (see `normalizeHeader`). */
const SAMPLE_TYPE_HEADER = 'sample type';

/**
 * Normalize a header cell for comparison: lower-case, collapse runs of
 * whitespace/underscores to a single space, and trim. Lets us match
 * `Sample Type`, `sample_type`, `sample  type` all against `sample type`.
 */
function normalizeHeader(value: unknown): string {
  return String(value ?? '')
    .toLowerCase()
    .replace(/[\s_]+/g, ' ')
    .trim();
}

/** Path of a File as seen in the dropzone (folder mode sets webkitRelativePath). */
function filePath(f: File): string {
  return (f as File & { webkitRelativePath?: string }).webkitRelativePath || f.name;
}

/**
 * Pick the `samples.xlsx` to read. SPARC places it at the dataset root, so when
 * several match (nested copies, results dirs) we prefer the shallowest path —
 * fewest `/` segments — which is the top-level metadata file.
 */
function findSamplesFile(files: File[]): File | undefined {
  const matches = files.filter(
    (f) => filePath(f).split('/').pop()?.toLowerCase() === SAMPLES_FILENAME,
  );
  if (matches.length === 0) return undefined;
  return matches.reduce((shallowest, f) =>
    filePath(f).split('/').length < filePath(shallowest).split('/').length ? f : shallowest,
  );
}

/**
 * Case-insensitive de-dup that preserves first-seen order and the original
 * casing of the first occurrence (`Blood` and `blood` collapse to `Blood`).
 */
function dedupePreserveOrder(values: string[]): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const v of values) {
    const trimmed = v.trim();
    if (!trimmed) continue;
    const key = trimmed.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(trimmed);
  }
  return out;
}

/**
 * Read the de-duplicated `sample type` values from the dropped folder's
 * `samples.xlsx`. Returns `[]` for any failure or absence — never throws.
 */
export async function readSampleTypesFromFiles(files: File[]): Promise<string[]> {
  const samplesFile = findSamplesFile(files);
  if (!samplesFile) return [];

  try {
    // Dynamic import keeps SheetJS (~hundreds of KB) out of the main bundle —
    // same lazy-load strategy the dropzone uses for jszip.
    const XLSX = await import('xlsx');
    const buf = await samplesFile.arrayBuffer();
    const wb = XLSX.read(buf, { type: 'array' });
    const firstSheetName = wb.SheetNames[0];
    if (!firstSheetName) return [];
    const sheet = wb.Sheets[firstSheetName];

    // header:1 → array-of-arrays; row 0 is the SPARC header row.
    const rows = XLSX.utils.sheet_to_json<unknown[]>(sheet, { header: 1, blankrows: false });
    if (rows.length < 2) return [];

    const header = rows[0] as unknown[];
    const colIndex = header.findIndex((cell) => normalizeHeader(cell) === SAMPLE_TYPE_HEADER);
    if (colIndex === -1) return [];

    const values = rows
      .slice(1)
      .map((row) => String((row as unknown[])[colIndex] ?? ''))
      .filter((v) => v.trim().length > 0);

    return dedupePreserveOrder(values);
  } catch (err) {
    console.warn('Failed to read sample types from samples.xlsx:', err);
    return [];
  }
}

/**
 * Build the one-line description from de-duplicated sample types. Returns an
 * empty string when there is nothing to describe so the caller can skip filling.
 */
export function buildSampleTypeDescription(types: string[]): string {
  if (types.length === 0) return '';
  return `This dataset contains the following sample types: ${types.join(', ')}.`;
}
