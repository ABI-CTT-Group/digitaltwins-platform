export function capitalize(str:string): string {
  if (!str) return '';
  return str.charAt(0).toUpperCase() + str.slice(1);
}

export function getApiErrorMessage(e: any, action: string): string {
  const status = e?.response?.status;
  if (status === 401) return `${action} failed: session expired, please log in again.`;
  if (status === 403) return `${action} failed: you don't have permission.`;
  if (status === 404) return `${action} failed: resource not found.`;
  if (status === 422) return `${action} failed: invalid data submitted.`;
  if (status && status >= 500) return `${action} failed: server error, please try again later.`;
  if (!e?.response) return `${action} failed: network error, please check your connection.`;
  return `${action} failed, please try again.`;
}