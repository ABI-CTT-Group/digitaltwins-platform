import { ref } from 'vue';

export interface ConfirmRequest {
  title: string;
  text: string;
  confirmLabel: string;
  dismissLabel?: string;
  /** Runs on confirm; a rejection keeps the dialog open with the reason. */
  action: () => Promise<unknown>;
}

/** One ConfirmDialog per hub: `ask()` opens it for a delete or cancel-upload. */
export function useConfirm() {
  const request = ref<ConfirmRequest | null>(null);
  const open = ref(false);
  const ask = (r: ConfirmRequest) => {
    request.value = r;
    open.value = true;
  };
  return { request, open, ask };
}
