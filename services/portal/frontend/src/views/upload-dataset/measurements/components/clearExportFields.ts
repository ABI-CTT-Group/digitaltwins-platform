/**
 * Recursively blank out identifying fields for the exported fhir.json:
 *  - every `uuid` and `endpointUrl` → "" (server-assigned ids / endpoint URLs)
 *  - every `url` inside an `attachments` / `attachment` subtree → ""
 *
 * Values are emptied (set to ""), not removed, so the document shape is
 * preserved. Used by the "Export annotation" download. `url` is only cleared
 * within an attachment context so unrelated URLs (code systems, etc.) survive.
 */

const ID_KEYS = ['uuid', 'endpointUrl', 'endpoint_url'] as const;
const ATTACHMENT_KEYS = ['attachments', 'attachment'] as const;

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return (
    typeof value === 'object' &&
    value !== null &&
    !Array.isArray(value) &&
    (value as object).constructor === Object
  );
}

function clear<T>(input: T, inAttachments: boolean): T {
  if (Array.isArray(input)) {
    return input.map((item) => clear(item, inAttachments)) as unknown as T;
  }
  if (isPlainObject(input)) {
    const out: Record<string, unknown> = {};
    for (const [key, value] of Object.entries(input)) {
      if ((ID_KEYS as readonly string[]).includes(key)) {
        out[key] = '';
      } else if (key === 'url' && inAttachments) {
        out[key] = '';
      } else {
        const nextInAttachments =
          inAttachments || (ATTACHMENT_KEYS as readonly string[]).includes(key);
        out[key] = clear(value, nextInAttachments);
      }
    }
    return out as unknown as T;
  }
  return input;
}

export function clearExportFields<T>(input: T): T {
  return clear(input, false);
}
