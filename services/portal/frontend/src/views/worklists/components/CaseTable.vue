<template>
  <section aria-label="Cases">
    <div class="toolbar">
      <div class="tabs" role="tablist">
        <button
          v-for="t in TABS"
          :key="t.key"
          type="button"
          role="tab"
          class="tab"
          :aria-selected="tab === t.key"
          :data-test="`tab-${t.key}`"
          @click="$emit('update:tab', t.key)"
        >{{ t.label }}<span class="tab__n">{{ t.key === "all" ? n.total : n[t.key] }}</span></button>
      </div>
      <input
        id="case-search"
        class="search"
        type="search"
        placeholder="Find a case, e.g. sub-012"
        aria-label="Find a case"
        :value="query"
        @input="$emit('update:query', ($event.target as HTMLInputElement).value)"
      >
    </div>

    <div class="table-wrap">
      <table>
        <thead>
          <tr><th>Case</th><th>Scan</th><th>Annotated by</th><th>Updated</th><th>Status</th></tr>
        </thead>
        <tbody>
          <tr
            v-for="c in rows"
            :key="c.id"
            tabindex="0"
            :aria-selected="c.id === selectedId"
            data-test="case-row"
            @click="$emit('select', c.id)"
            @keydown.enter.prevent="$emit('select', c.id)"
            @keydown.space.prevent="$emit('select', c.id)"
          >
            <td class="case-id">{{ c.id }}</td>
            <td class="dim">{{ c.scan }}</td>
            <td>{{ c.annotatedBy }}</td>
            <td class="dim num">{{ formatDate(c.updated) }}</td>
            <td><StatusPill :status="c.status" /></td>
          </tr>
        </tbody>
      </table>
      <p v-if="!rows.length" class="empty">{{ emptyText }}</p>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { counts, filterCases, STATUS_LABEL, type Case, type Tab } from "../model/worklist";
import StatusPill from "./StatusPill.vue";

const props = defineProps<{ cases: Case[]; tab: Tab; query: string; selectedId: string | null }>();
defineEmits<{ "update:tab": [Tab]; "update:query": [string]; select: [string] }>();

const TABS: { key: Tab; label: string }[] = [
  { key: "review", label: "To review" },
  { key: "needs", label: "Needs correction" },
  { key: "confirmed", label: "Confirmed" },
  { key: "all", label: "All" },
];

const n = computed(() => counts(props.cases));
const rows = computed(() => filterCases(props.cases, props.tab, props.query));
const emptyText = computed(() =>
  props.query.trim() ? `No case matches “${props.query.trim()}”.`
  : props.tab === "review" ? "Nothing left to review. Every case has a decision."
  : props.tab === "all" ? "This project has no cases yet."
  : `No cases are marked “${STATUS_LABEL[props.tab]}” yet.`);

const formatDate = (iso: string) =>
  new Date(`${iso}T00:00:00`).toLocaleDateString("en-NZ", { day: "numeric", month: "short" });
</script>

<style scoped>
.toolbar { display: flex; justify-content: space-between; gap: 12px; flex-wrap: wrap; margin-bottom: 12px; }
.tabs {
  display: flex; flex-wrap: wrap; gap: 4px; padding: 3px;
  background: var(--surface); border: 1px solid var(--line); border-radius: 9px;
}
.tab {
  border: 0; background: none; padding: 6px 12px; border-radius: 6px; cursor: pointer;
  color: var(--text-dim); font-weight: 500; font-size: 0.875rem;
}
.tab[aria-selected="true"] { background: rgba(95, 214, 232, 0.12); color: var(--text); }
.tab__n { margin-left: 6px; color: var(--text-faint); font-variant-numeric: tabular-nums; }
.search {
  width: 220px; min-width: 0; padding: 7px 12px; border-radius: 8px; font-size: 0.875rem;
  background: var(--surface); border: 1px solid var(--line); color: var(--text);
}
.search::placeholder { color: var(--text-faint); }

.table-wrap { overflow-x: auto; border: 1px solid var(--line); border-radius: 10px; }
table { width: 100%; min-width: 560px; border-collapse: collapse; font-size: 0.9rem; }
th {
  text-align: left; font-weight: 500; font-size: 0.8125rem; color: var(--text-faint);
  padding: 10px 14px; border-bottom: 1px solid var(--line);
}
td { padding: 11px 14px; border-bottom: 1px solid var(--line); vertical-align: middle; }
tbody tr { cursor: pointer; }
tbody tr:last-child td { border-bottom: 0; }
tbody tr:hover { background: var(--surface); }
tbody tr[aria-selected="true"] { background: rgba(95, 214, 232, 0.07); box-shadow: inset 3px 0 0 var(--accent-tools); }
tbody tr:focus-visible { outline: 2px solid var(--accent-tools); outline-offset: -2px; }
.case-id { font-weight: 600; font-variant-numeric: tabular-nums; }
.dim { color: var(--text-dim); }
.num { font-variant-numeric: tabular-nums; }
.empty { margin: 0; padding: 36px 16px; text-align: center; color: var(--text-dim); }

@media (max-width: 480px) { .search { width: 100%; } }
</style>
