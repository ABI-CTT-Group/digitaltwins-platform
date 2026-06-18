/**
 * Recursively delete every `_auto` UI marker from a descriptions tree to get a
 * clean fhir-cda view.
 *
 * The marker arrives on `/tree` as a per-resource hint
 * (`{ samplePath, sourceFile, modality, files, truncated }`) that drives the
 * Annotation step's "Auto-detected from sub-XXX/sam-YYY" chips and the
 * auto-classified count. The markers ARE persisted with the draft now (so a
 * reopened annotation keeps those affordances) — this helper is used only to
 * render the "Preview descriptions" panel as the clean tree that fhir.json
 * will be built from. It is intentionally NOT applied before POST anymore.
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
