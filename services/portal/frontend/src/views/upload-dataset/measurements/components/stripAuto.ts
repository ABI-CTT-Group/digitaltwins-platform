/**
 * Recursively delete every `_auto` UI marker from a descriptions tree before
 * sending it back to the backend.
 *
 * The marker arrives on `/tree` as a per-resource hint
 * (`{ samplePath, sourceFile, modality, files, truncated }`) that drives the
 * Annotation step's "Auto-detected from sub-XXX/sam-YYY" chips. It should
 * not be persisted in `MeasurementAnnotation.descriptions` or end up in
 * the saved `fhir.json`, so we strip it just before POST.
 *
 * Note on key shape: the axios response interceptor (`http.ts`) deep-camelizes
 * `_auto` to `Auto` on incoming responses (the regex eats the leading
 * underscore). We delete both spellings to be safe — code that worked
 * against either casing variant will keep working.
 */

const AUTO_KEYS = ['_auto', 'Auto'] as const;

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return (
    typeof value === 'object' &&
    value !== null &&
    !Array.isArray(value) &&
    (value as object).constructor === Object
  );
}

export function stripAuto<T>(input: T): T {
  if (Array.isArray(input)) {
    return input.map((item) => stripAuto(item)) as unknown as T;
  }
  if (isPlainObject(input)) {
    const out: Record<string, unknown> = {};
    for (const [key, value] of Object.entries(input)) {
      if ((AUTO_KEYS as readonly string[]).includes(key)) continue;
      out[key] = stripAuto(value);
    }
    return out as unknown as T;
  }
  return input;
}
