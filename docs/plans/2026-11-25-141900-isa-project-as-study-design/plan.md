# Call each study a study design on the catalogue pages, and open it from there

Status: done

Branch: prototype

## Context

The catalogue tile and the page at `/catalogue/isa-project` call the uploaded thing an "ISA project". For the
demo audience the page should be about study designs. In the user's words, the example "Breast" holds "two
study designs": each **study** is a study design, which also matches each study's own page, headed "Study
design". The uploaded file is the project that holds them.

The page also had one "Open in study dashboard" button per project, which opens the project level, while
the studies' own links looked like plain text. Each study needs its own button that opens that study.

This changes only what the pages say and where the buttons are: the JSON format, the code identifiers, the
routes and the developer docs keep the ISA project name.

## Steps

1. Change the tests to the new wording: "Study designs" on the catalogue tile and the page, "Upload study
   design", and "study design(s)" in the upload dialog's text, the not-found message on a study's page.
   Where the text means the whole upload, it says "project": "Add project", "the Breast project", "lists
   the project under it", "the project's row", "the same project id", and the bundle reader's error.
2. Change those strings.
3. Change the hub tests: the programme count counts studies ("2 study designs"); a project card has no
   Open button; each study has an "Open in study dashboard" button that opens that study; investigation
   and study titles are no longer buttons.
4. In `IsaProjectHub.vue`, move the button from the card's actions to each study's line in the tree
   (outlined, `aurora-btn--ghost`), make the investigation and study titles plain text, and count studies.

## Approaches

- **Button on each study, project card keeps Approve and the menu (chosen).** One visible way to open a
  study; the card's actions are the ones that apply to the whole upload.
- Keep the project button and add study buttons: two kinds of Open on one card, and the project level
  isn't what anyone asked to open.
- Make the study titles look like links: no new buttons, but a link is easy to miss in a tree of titles,
  which is how the current ones were missed.

## Decisions

- Each study is a study design; the uploaded file is a project that can hold several (the user's words).
- Study buttons are outlined, not solid, so several on a card don't compete with "Upload study design".
- Opening an investigation level from this page goes away with its link (accepted with the design).
- The tree and its rails stay: they show what contains what.
- "SEEK project", "any project can use them" and the bundle layout's file names (`isa-project.json`) stay:
  they name other things.
- The researcher view of `/study-dashboard` (its "Projects" tree level, "N projects" programme counts and
  "Bundled with this project") is not one of the pages asked about and stays as it is.
