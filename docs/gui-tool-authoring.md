# Writing a GUI tool

A *GUI tool* is a web app that runs inside the portal. The builder builds its
frontend into a UMD bundle, and the portal mounts it at `/tool-view`. An
optional backend runs as containers behind `/plugin/<expose>/`.

This guide covers what your tool gets from the platform when it opens, and how
to load the assay's data with it. How the bundle and the backend are built and
routed is in the
[plugin system architecture](../services/portal/docs/plugin-system-architecture.md#7-plugin-contract-what-plugin-authors-must-provide)
(§7 lists what your repository must contain).

## The one rule: read the launch context, don't bundle the data

Your tool opens in one of two ways:

- **From a gui assay** (the study dashboard's Launch button). The portal gives
  your tool a **launch context**: which assay it is, the cohort, and every input
  file the assay was configured with.
- **From the Tool Hub.** There's no assay, so there's no launch context.

Read the launch context when it is there, and fall back to your own bundled
defaults when it isn't. Never point the tool at a dataset by name in a file
you build into the bundle: the bundle is built once and used by every assay
that runs your workflow, so bundled data settings are right for one assay at
most. With the launch context, one build serves every assay, with no rebuild.

```ts
import { inject } from "vue";
import defaults from "@/assets/defaults.json";   // your standalone/dev settings

const launch = inject<LaunchContext | null>("launchContext", null);
const settings = launch ? fromLaunchContext(launch) : defaults;
```

The portal provides it on your app with Vue's `provide`, so any component in
your tool can `inject` it. Read it once, when the tool starts.

## What the launch context holds

A filled-in example to copy is
[`launch-context.example.json`](../services/portal/frontend/src/models/launch-context.example.json).
The TypeScript type `LaunchContext` in
[`types.ts`](../services/portal/frontend/src/models/types.ts) is the definition;
copy this into your tool:

```ts
interface LaunchContext {
  schemaVersion: number;          // 1; changes only on a breaking change
  assayId: string;                // the SEEK assay id
  cohort: string[];               // subject ids to work on, e.g. ["sub-1", "sub-3"]
  inputs: {
    name: string;                 // the input's name in your workflow's CWL
    datasetUuid: string;          // the platform dataset the assay chose for it
    bucket: string | null;        // the MinIO bucket that dataset is in, e.g. "measurements"
    sampleType: string | null;    // the dataset sample type chosen for it
    files: {
      name: string;               // the file name, e.g. "contrast_pre_nrrd.nrrd"
      subjectId: string;          // "sub-1"
      sampleId: string;           // "sam-1"
      key: string;                // MinIO key: "<datasetUuid>/primary/<subjectId>/<sampleId>/<name>"
      url: string;                // the same file through the platform API, for the browser
    }[];
  }[];
  getAccessToken: () => string | undefined;   // the user's current token
}
```

- `inputs` has one entry per file input of the assay; model inputs are left
  out. `files` lists that input's files for the cohort's subjects only.
- `cohort` is already resolved to subject ids. An assay with no cohort set runs
  on every subject, and `cohort` then lists them all.
- Every input dataset is in [SDS](glossary.md) layout, so its metadata
  (`subjects.xlsx`, `samples.xlsx`, `manifest.xlsx`) sits at
  `<bucket>/<datasetUuid>/`.

## Loading the files

### In the browser: use `url`

Fetch `url` from your frontend. The request goes through the platform API,
which checks that the user may read the assay and that the file is one of its
inputs, then streams it from MinIO, which stays private.

The portal sets a cookie that authenticates these requests for **5 minutes**
after the tool opens, so a plain `fetch(url)` works at first. For anything
loaded later, send the token yourself:

```ts
const res = await fetch(file.url, { headers: { Authorization: `Bearer ${launch.getAccessToken()}` } });
```

The API only serves files under each input dataset's `primary/` folder; it
refuses the dataset's metadata files and any other dataset.

### In your backend: use `bucket` and `key`

A backend can't use the browser's cookie. If your tool has a backend that reads
the files itself, send it `bucket` and `key` (or `bucket` and `datasetUuid`),
and read them from MinIO directly. The builder runs your backend's compose file
with these variables available for interpolation:

```yaml
environment:
  - MINIO_ENDPOINT=minio:9000
  - MINIO_ACCESS_KEY=${MINIO_SERVER_ACCESS_KEY}
  - MINIO_SECRET_KEY=${MINIO_SERVER_SECRET_KEY}
  - PLUGIN_ROUTE_PREFIX=${PLUGIN_ROUTE_PREFIX}
```

These credentials can read every bucket, and nothing checks them per user, so
a backend that uses them must read only what the launch context names.

## Worked example: the Lesion Ground Truth Curator

The annotator boots from its own config object, which names datasets, sample
types, cohorts and a MinIO base URL. It used to read that object only from a
bundled `tool_config.json`. To fit any assay, it builds the same object from the
launch context and keeps the bundled file for standalone use:

```ts
import { inject } from "vue";
import bundled from "@/assets/tool_config.json";

function fromLaunchContext(launch: LaunchContext, defaults: typeof bundled) {
  // One dataset entry per input dataset, routing each input of the assay to it.
  const sampleTypes = new Map<string, string[]>();
  for (const input of launch.inputs) {
    sampleTypes.set(input.datasetUuid, [...(sampleTypes.get(input.datasetUuid) ?? []), input.name]);
  }
  return {
    ...defaults,
    assay_info: {
      ...defaults.assay_info,
      uuid: `assay-${launch.assayId}`,
      cohorts: launch.cohort,
      datasets: [...sampleTypes].map(([name, sample_type]) => ({ name, sample_type })),
    },
    // The backend reads only the bucket from this URL; it connects to MINIO_ENDPOINT itself.
    system: { ...defaults.system, minio: { base_url: `http://minio:9000/${launch.inputs[0]?.bucket}/` } },
  };
}

const launch = inject<LaunchContext | null>("launchContext", null);
const config = launch ? fromLaunchContext(launch, bundled) : bundled;
```

Two limits of this mapping come from the annotator, not the platform:

- It routes by sample type name, so each input's `name` must also be the
  `sample type` of its files in the dataset's `samples.xlsx`. A tool that reads
  `files` directly has no such limit.
- It takes one MinIO base URL, so all its input datasets must be in one bucket.

## What the launch context doesn't cover yet

- **The user.** It doesn't say who is signed in. A tool that needs a user id
  keeps its own for now.
- **Tool Hub launches.** They get no launch context.
- **Results.** There's no way yet to submit a GUI tool's outputs back as an
  assay run's results.

Why the platform hands every tool one standard object, rather than filling in
each tool's own config format, is in the
[ADR](decisions/2026-11-12-gui-tool-launch-context.md).
