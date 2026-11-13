<template>
  <div class="slice" role="img" :aria-label="`${caseId}, slice ${middle} of ${slices}, with the annotation outlined`" data-test="slice-preview">
    <!-- An illustration, not the case's scan: the prototype has no images. -->
    <svg viewBox="0 0 320 220" aria-hidden="true">
      <defs>
        <radialGradient id="slice-tissue" :cx="`${scan.glowX}%`" :cy="`${scan.glowY}%`" r="62%">
          <stop offset="0" :stop-color="scan.glow" />
          <stop offset="0.55" stop-color="#5d6a71" />
          <stop offset="1" stop-color="#1f292e" />
        </radialGradient>
      </defs>
      <path :d="scan.tissue" fill="url(#slice-tissue)" data-test="tissue" />
      <g fill="none" stroke="rgba(225, 235, 240, 0.35)" stroke-width="1.2">
        <path v-for="(d, i) in scan.strands" :key="i" :d="d" />
      </g>
      <polygon
        :points="outline" data-test="annotation-outline"
        fill="rgba(95, 214, 232, 0.16)" stroke="#5fd6e8" stroke-width="1.6" stroke-linejoin="round"
      />
    </svg>
    <span class="slice__label" aria-hidden="true">Slice {{ middle }} / {{ slices }}</span>
  </div>
</template>

<script setup lang="ts">
// A stand-in slice image for the case under review, with its annotation outlined (frontend-only prototype).
import { computed } from "vue";

const props = defineProps<{ caseId: string; slices: number }>();
const middle = computed(() => Math.ceil(props.slices / 2));

const seed = computed(() => Number(props.caseId.replace(/\D/g, "")) || 1);

/** The slice drawing: its outline, bright patch and tissue strands follow the case number, so each case looks
 *  different. Kept wide enough to hold the annotation outline. */
const scan = computed(() => {
  const s = seed.value;
  const left = 40 + (s * 7) % 21, right = 280 - (s * 11) % 21, bottom = 180 + (s * 5) % 17;
  const mid = (left + right) / 2, bend = (s * 3) % 13;
  const shift = (k: number) => ((s * k) % 25) - 12;
  return {
    tissue: `M${left} 30 H${right} C${right + 4} ${110 + bend} ${right - 36} ${bottom - 6} ${mid} ${bottom}` +
      ` C${left + 36} ${bottom - 6} ${left - 4} ${110 + bend} ${left} 30 Z`,
    glowX: 42 + (s * 7) % 17,
    glowY: 34 + (s * 5) % 17,
    glow: ["#a9b4ba", "#b8c2c7", "#9aa6ad", "#c3ccd0"][s % 4],
    strands: [
      `M${left + 38 + shift(3)} 62 C${left + 60 + shift(5)} 82 ${left + 64} 118 ${left + 84 + shift(7)} 150`,
      `M${right - 40 + shift(11)} 58 C${right - 58} 86 ${right - 58 + shift(13)} 124 ${right - 76} 160`,
      `M${mid + shift(17)} 40 C${mid - 10} 56 ${mid - 6 + shift(19)} 72 ${mid - 14} 84`,
    ],
  };
});

/** A ten-point outline whose place, size and shape follow the case number, so each case looks different. */
const outline = computed(() => {
  const s = seed.value;
  const cx = 125 + (s * 23) % 70, cy = 75 + (s * 13) % 40, r = 14 + (s % 5) * 3;
  return Array.from({ length: 10 }, (_, k) => {
    const a = (k / 10) * Math.PI * 2, rr = r * (0.75 + ((s * (k + 3)) % 7) / 14);
    return `${(cx + Math.cos(a) * rr).toFixed(1)},${(cy + Math.sin(a) * rr).toFixed(1)}`;
  }).join(" ");
});
</script>

<style scoped>
.slice { position: relative; overflow: hidden; border-radius: 8px; background: #03080b; }
svg { display: block; width: 100%; height: auto; }
.slice__label {
  position: absolute; left: 10px; bottom: 8px; font-size: 0.75rem;
  font-variant-numeric: tabular-nums; color: var(--text-dim);
}
</style>
