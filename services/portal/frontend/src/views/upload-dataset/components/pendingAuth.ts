/**
 * The git token step 1 of a tool or workflow wizard was given, kept in this tab's memory (never stored or
 * sent anywhere but the builder) so the same registration's annotation and first build can use it after
 * the wizard moves to the item's own URL. A registration continued later asks for it again.
 */
import type { TransientAuth } from '@/models/types';

const remembered = new Map<string, TransientAuth | undefined>();

export const rememberAuth = (id: string, auth: TransientAuth | undefined) => { remembered.set(id, auth); };
/** Whether step 1 of this registration ran in this tab, and with which token (undefined for none). */
export const recallAuth = (id: string): { known: boolean; auth?: TransientAuth } =>
  ({ known: remembered.has(id), auth: remembered.get(id) });
export const forgetAuth = (id: string) => { remembered.delete(id); };
