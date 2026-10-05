// VolView downloads `urls=` with the browser's plain fetch: no Authorization header, but same-origin
// cookies are sent. So the user's token rides in a cookie scoped to the one path that needs it,
// the assay's input-files proxy, for about a Keycloak access token's lifetime.
const NAME = "dt_assay_file_token";

const path = (assayId: string) => `/api/dashboard/assays/${encodeURIComponent(assayId)}/input-files`;

export function assayFileCookie(assayId: string, token: string, protocol = window.location.protocol): string {
  const cookie = `${NAME}=${token}; path=${path(assayId)}; max-age=300; samesite=strict${protocol === "https:" ? "; secure" : ""}`;
  document.cookie = cookie;
  return cookie;
}

export function clearAssayFileCookie(assayId: string): string {
  const cookie = `${NAME}=; path=${path(assayId)}; max-age=0; samesite=strict`;
  document.cookie = cookie;
  return cookie;
}
