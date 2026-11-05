/** One line saying why a call failed, for the inline error under a wizard step's buttons. */
import { getApiErrorMessage } from '@/utils/common';

export function describeApiError(err: any, action: string): string {
  // The server's own reason, when it gave one.
  const detail = err?.response?.data?.detail;
  if (typeof detail === 'string' && detail) return `${action} failed: ${detail}`;
  // An error thrown in the portal (not a failed request) says what went wrong itself.
  if (!err?.response && !err?.isAxiosError && err?.message) return `${action} failed: ${err.message}`;
  return getApiErrorMessage(err, action);
}
