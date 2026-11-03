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

SheetJS stopped publishing to npm after 0.18.5 (March 2022). Its fixed releases are on its own CDN,
`cdn.sheetjs.com`, so no version range on the npm package can reach a fix. Both bugs need a crafted
file, and the parse runs in the browser of the person dropping the folder. Datasets often come from
collaborators, though, so the person dropping the folder didn't necessarily create that file.

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

### Option C: Replace SheetJS with another library (for example `read-excel-file` or `exceljs`)
- Pros: stays on the npm registry, so Dependabot keeps tracking it.
- Cons: a code change and a new dependency tree to review, for a best-effort helper of about 30
  lines. Header and blank-row handling would need to be re-checked against real SPARC files.

### Option D: Commit the 0.20.3 tarball into the repo (`file:` dependency)
- Pros: no build-time dependency on the SheetJS CDN.
- Cons: about 2.4 MB of binary in git, for every later update too. CI and the image build already
  need the npm registry, so it removes only one of several network dependencies.

## Decision

Option A. `services/portal/frontend/package.json` has
`"xlsx": "https://cdn.sheetjs.com/xlsx-0.20.3/xlsx-0.20.3.tgz"`, and `yarn.lock` pins that URL and the
tarball's hash (Yarn 1 writes no separate `integrity` line for a URL dependency). `sampleTypes.spec.ts` writes a real `.xlsx` and reads it back through
`readSampleTypesFromFiles`, so a SheetJS update that changes the read path fails `make test-frontend`.

## Consequences

- Any host that builds the portal image, and CI's `make frontend-deps`, must be able to reach
  `cdn.sheetjs.com`. Airgapped deployments aren't affected: they load images frozen on a connected
  host and don't build (see [util/INSTALL-BUNDLE.md](../../util/INSTALL-BUNDLE.md)).
- Dependabot won't propose updates for `xlsx`. When you work on the portal's dependencies, check the
  SheetJS release notes (https://docs.sheetjs.com/docs/getting-started/) for a newer version or
  advisory, and update the URL in `package.json`.
- If SheetJS publishes fixed versions to npm again, switch back to a normal version range.
