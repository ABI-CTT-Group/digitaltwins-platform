# Install SheetJS (xlsx) from the SheetJS CDN, not npm

- **Date:** 2026-11-04
- **Status:** Accepted

## Context

The portal reads `samples.xlsx` with SheetJS (the `xlsx` package) when a dataset folder is dropped
into the measurement upload form. It fills in the dataset description from the `sample type` column
(`services/portal/frontend/src/views/upload-dataset/measurements/components/sampleTypes.ts`). That's
the only place the portal uses `xlsx`, and it loads the library lazily.

The portal installed `xlsx@^0.18.5` from npm. Two high-severity advisories affect that version:

- GHSA-4r6h-8v6p-xvw6: prototype pollution when reading a crafted file. Fixed in 0.19.3.
- GHSA-5pgg-2g8v-p4x9: regular-expression denial of service (ReDoS). Fixed in 0.20.2.

SheetJS stopped publishing to npm after 0.18.5 (March 2022). In April 2022 its maintainers explained why
([SheetJS/sheetjs#2667](https://github.com/SheetJS/sheetjs/issues/2667)): npm cancelled their publishing
token and required two-factor sign-in on the account, and "due to ongoing legal matters between SheetJS
LLC and npm, Inc." they decided to stop using the public npm registry. Since then, official releases
are published only on SheetJS's own CDN, `cdn.sheetjs.com`, and SheetJS's install docs point there.
`npm install xlsx` still installs 0.18.5, so no version range on the npm package can reach a fix.

Both bugs need a crafted file, and the parse runs in the browser of the person dropping the folder.
Datasets often come from collaborators, though, so the person dropping the folder didn't necessarily
create that file.

We wanted official SheetJS releases only, with a clear path to future official versions, and no
third-party repackaging.

## Alternatives Considered

### Option A: Install the 0.20.3 tarball from the SheetJS CDN
- Pros: fixes both advisories. The `read` and `utils.sheet_to_json` API the portal calls doesn't
  change, so no code changes. It has no dependencies, which drops 8 helper packages from the
  lockfile. Same licence (Apache-2.0). `yarn.lock` records the tarball's SHA-1 in its `resolved` URL,
  and yarn checks it on every install, so a changed tarball fails the install rather than slipping in.
- Cons: building the portal image, and `make frontend-deps`, now need to reach `cdn.sheetjs.com` as
  well as the npm registry. Dependabot can't propose updates for a URL dependency.

### Option B: Keep 0.18.5 and dismiss the alerts as an accepted risk
- Pros: no change.
- Cons: leaves two known high-severity bugs in code that parses files from outside the team, with no
  way to ever get a fix through npm.

### Option C: A community copy of SheetJS on npm (`"xlsx": "npm:@e965/xlsx@0.20.3"`)
- Pros: installs from the npm registry like every other portal package. Checked on 2026-11-04: its
  code and type files are byte-identical to the official 0.20.3 tarball; only the package name,
  repository link and README differ, and it has no install scripts. Published with npm provenance
  from a public GitHub Actions job. No app or test changes.
- Cons: an individual with no link to SheetJS publishes it, so every future version depends on
  trusting that person rather than SheetJS. Advisories are filed against `xlsx`, so Dependabot likely
  wouldn't flag this name either.

### Option D: Replace SheetJS with another library (for example `read-excel-file` or `exceljs`)
- Pros: stays on the npm registry, so Dependabot keeps tracking it.
- Cons: a code change and a new dependency tree to review, for a best-effort helper of about 30
  lines. Header and blank-row handling would need to be re-checked against real SPARC files.
  `read-excel-file`, the most used, had three breaking major versions in 2026 (7, 8 and 9). Two of its
  four dependencies were first published in mid-2026 by the same single maintainer, and its browser
  build uses Web Workers. `exceljs` was last released in 2023 and brings nine dependencies.

### Option E: Commit the official 0.20.3 tarball into the repo (`file:` dependency)
- Pros: no build-time dependency on the SheetJS CDN.
- Cons: about 2.4 MB of binary in git, for every later update too. CI and the image build already
  need the npm registry, and other images already download from vendor sites at build time (the
  builder's Dockerfile fetches from `get.volta.sh` and `download.docker.com`), so it removes only one
  of several network dependencies. Updates are just as manual as with Option A.

## Decision

Option A. It's SheetJS's own distribution channel, so we get official releases and a future
official version is a one-line URL change. Option C would make an unaffiliated repackager the source
of every future version. Option D means rewriting working code onto a replacement library that's
either changing fast with a single maintainer (`read-excel-file`) or unmaintained since 2023
(`exceljs`). Option E ships the same official file but adds a binary to git
without making updates easier. Option A's one new requirement, reaching `cdn.sheetjs.com` at build
time, matches how the project already builds images.

`services/portal/frontend/package.json` has
`"xlsx": "https://cdn.sheetjs.com/xlsx-0.20.3/xlsx-0.20.3.tgz"`, and `yarn.lock` pins that URL and the
tarball's hash (Yarn 1 writes no separate `integrity` line for a URL dependency). `sampleTypes.spec.ts`
writes a real `.xlsx` and reads it back through `readSampleTypesFromFiles`, so a SheetJS update that
changes the read path fails `make test-frontend`.

## Consequences

- Any host that builds the portal image, and CI's `make frontend-deps`, must be able to reach
  `cdn.sheetjs.com`. Airgapped deployments aren't affected: they load images frozen on a connected
  host and don't build (see [util/INSTALL-BUNDLE.md](../../util/INSTALL-BUNDLE.md)).
- Dependabot won't propose updates for `xlsx`. When you work on the portal's dependencies, check the
  SheetJS release notes (https://docs.sheetjs.com/docs/getting-started/) for a newer version or
  advisory, and update the URL in `package.json`.
- If SheetJS publishes fixed versions to npm again, switch back to a normal version range.
