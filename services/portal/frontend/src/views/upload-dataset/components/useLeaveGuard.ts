/** Ask before leaving a wizard that would lose work: in-app navigation (confirm) and closing or reloading the tab. */
import { onBeforeUnmount, onMounted } from 'vue';
import { onBeforeRouteLeave } from 'vue-router';

const MESSAGE = 'Leave this page? What you entered here is lost, and an upload in progress stops.';

export function useLeaveGuard(active: () => boolean, message = MESSAGE) {
  onBeforeRouteLeave(() => (active() ? window.confirm(message) : true));

  const onBeforeUnload = (event: BeforeUnloadEvent) => {
    if (!active()) return;
    event.preventDefault();
    event.returnValue = '';  // older browsers show their own prompt only when this is set
  };
  onMounted(() => window.addEventListener('beforeunload', onBeforeUnload));
  onBeforeUnmount(() => window.removeEventListener('beforeunload', onBeforeUnload));
}
