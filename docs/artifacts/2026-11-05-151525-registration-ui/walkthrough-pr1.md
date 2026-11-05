# Walkthrough: PR1, shared look, hub states, delete confirmations, Tools role

Plan: [plan.md](plan.md). Tasks: [tasks.md](tasks.md).

## What changed
- **Fonts.** Hanken Grotesk and Fraunces are self-hosted (`@fontsource-variable/*` 5.3.0, imported in `main.ts`). The six Google Fonts `@import`s are gone, and every `'Fraunces'` / `'Hanken Grotesk'` stack now reads `var(--font-title)` / `var(--font-ui)`. Nunito still comes from `bootstrap/webfontloader.ts` for other pages (follow-up).
- **Tokens.** `:root` in `styles/style.css` holds `--font-ui`, `--font-title`, `--ink`, `--text*`, `--line`, `--surface`, `--tone-needs`, `--tone-failed` and the four category accents. The catalogue landing uses them instead of its own copies.
- **One button style.** `.aurora-btn` uses the UI font, has no hover lift and gets a visible focus ring. The hubs' tonal and lowercase Vuetify buttons are gone.
- **Hub frame.** `components/HubShell.vue`: back link, left-aligned Fraunces title, one line of purpose, at the catalogue landing's width. Titles: "Tools", "Workflows", "Measurements", "Models"; wizards: "Register a tool", and so on.
- **List states.** `RegistryView.vue` shows a skeleton while loading, an error with "Try again", the hub's own empty text, "Nothing matches your search or filter." when a filter hides everything, and "Couldn't refresh. Showing the list as it was a moment ago." when a poll fails. Search is live; the separate "search" and "refresh" buttons became one "Refresh" button.
- **Cards.** Sentence-case kind label, 12px radius, no lift, the category accent as a constant top edge, failure coral on danger menu items.
- **Delete confirmations.** `ConfirmDialog.vue` + `useConfirm.ts`. Tools, workflows and measurements now confirm before deleting, and measurements and models confirm before cancelling an upload. The dialog says what is removed (the portal only, or the platform too), stays open with the reason when deleting fails, and the card no longer greys out before the user confirms.
- **Roles.** The Tools route is admin-only, matching the catalogue tile: researchers register measurements and models only.

## Verification
- `make test-frontend`: 199 passed (186 before; new `RegistryView.spec.ts`, `ConfirmDialog.spec.ts`, role and card cases).
- `make lint` and `make docs-check`: clean.
- `portal-frontend` rebuilt and restarted; the bundle carries the font files, and `/catalogue/tools` serves.
- Headless Firefox (Playwright, signed in as an admin) captured the four hubs at 1440px, the Tools hub at 390px, and a measurement's delete confirmation, which was dismissed and never confirmed. The screenshots caught two bugs, now fixed: the register button ignored the hub accent (`.aurora-btn` resets `--accent`), and the filter label was cut off.
