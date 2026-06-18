import { ref } from "vue";

// Module-level singleton: the View.vue scroller writes it, AuthNavBar reads it.
// `scrolled` is true once the single .page-scroll container has scrolled past a
// small threshold — used to fade in the nav's frosted backdrop.
const scrolled = ref(false);

export function useScrollState() {
  const setScrolled = (value: boolean) => {
    if (scrolled.value !== value) scrolled.value = value;
  };
  return { scrolled, setScrolled };
}
