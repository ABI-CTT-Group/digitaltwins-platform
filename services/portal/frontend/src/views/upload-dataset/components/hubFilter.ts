/** The hub filter: All · Needs you · In progress · In the platform, from each card's status group (cardStatus.ts). */
import { computed, ref } from 'vue';
import type { CardStatus } from './cardStatus';

export type HubFilter = 'all' | 'needs' | 'progress' | 'platform';

export const HUB_FILTERS: { value: HubFilter; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'needs', label: 'Needs you' },
  { value: 'progress', label: 'In progress' },
  { value: 'platform', label: 'In the platform' },
];

type StatusOf<T> = (item: T) => CardStatus;

/** RegistryView's filterFn: undefined for All. */
export function hubFilterFn<T>(filter: HubFilter, statusOf: StatusOf<T>): ((item: T) => boolean) | undefined {
  return filter === 'all' ? undefined : (item) => statusOf(item).group === filter;
}

export function filterCounts<T>(items: T[], statusOf: StatusOf<T>): Record<HubFilter, number> {
  const counts: Record<HubFilter, number> = { all: items.length, needs: 0, progress: 0, platform: 0 };
  for (const item of items) {
    const group = statusOf(item).group;
    if (group !== 'other') counts[group] += 1;
  }
  return counts;
}

/** A sort comparator: what needs you first, the rest in their order (Array.prototype.sort is stable). */
export function needsFirst<T>(statusOf: StatusOf<T>): (a: T, b: T) => number {
  const rank = (item: T) => (statusOf(item).group === 'needs' ? 0 : 1);
  return (a, b) => rank(a) - rank(b);
}

/** A hub's filter state for RegistryView: the chosen filter, counts from the last list, filterFn and sortFn. */
export function useHubFilter<T>(statusOf: StatusOf<T>) {
  const filter = ref<HubFilter>('all');
  const items = ref<T[]>([]);
  return {
    filter,
    counts: computed(() => filterCounts(items.value as T[], statusOf)),
    filterFn: computed(() => hubFilterFn(filter.value, statusOf)),
    sortFn: needsFirst(statusOf),
    /** RegistryView's @refresh. */
    onRefresh: (list: T[]) => { items.value = list; },
  };
}
