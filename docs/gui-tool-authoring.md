# Writing a GUI tool

A *GUI tool* is a web app that runs inside the portal. The builder builds its
frontend into a UMD bundle, and the portal mounts it at `/tool-view`. An
optional backend runs as containers behind `/plugin/<expose>/`.

This guide takes a GUI tool from your repository to an assay's Launch button:

1. **Package it** as a gui workflow in SDS layout.
2. **Make your code fit** the plugin contract.
3. **Register it** in the portal, build it and approve it.
4. **Link an assay** to it.
5. When the assay launches it, **read the launch context** to load the assay's data.

How the platform builds, deploys and routes tools internally is in
[plugin-system.md](plugin-system.md); you don't need it to write one.

## Package it

A GUI tool reaches assays as a *gui workflow*: a workflow dataset whose single
step is your tool. The portal only registers workflows as
[SDS](glossary.md) packages:

```text
workflow_my-tool/
├── dataset_description.xlsx      # SDS metadata; required at the root
├── primary/
│   ├── workflow_my-tool.cwl      # class: Workflow, exactly one step
│   └── tool_my-tool.cwl          # class: CommandLineTool, the step
└── code/                         # your repository: the tool gets all of it
    ├── config.portal.json
    ├── <frontend folder>/        # Vue 3 + Vite
    └── <backend folder>/         # with docker-compose.yml at its root
```

That is the layout of a tool with a backend. A tool without one has no folders
to name: its Vite project is `code/` itself.

The workflow CWL's inputs and outputs are what an assay is configured with:

- Each **input's name** is what an assay maps a dataset to, and what your tool
  later sees as the launch context's `inputs[].name`. Name inputs after what
  your tool loads, e.g. `contrast_pre_nrrd`.
- Each input's and output's **`doc`** names its dataset category
  (`measurements` or `models`), which the assay's config dialog shows as the
  input's category.

```yaml
inputs:
  contrast_pre_nrrd:
    type: File
    label: "contrast_pre_nrrd"
    doc: measurements
```

## What your code must provide

**The frontend** (always):

- A Vue 3 + Vite project whose `vite.config.(js|ts)` has a `build.lib` block.
  The builder rewrites its `name`, `formats` and `fileName`; the block only has
  to exist.
- A `build:plugin` script in `package.json`, or another build command, entered
  when you register.
- Every API call goes through `import.meta.env.VITE_PLUGIN_ROUTE_PREFIX`, which
  the builder sets to `/plugin/<expose>` at build time. No hard-coded hosts or
  ports.
- Vue, Vuetify, Pinia and vue-toastification come from the portal: the builder
  builds your bundle with them as externals, so you get the portal's copies.
- No global side effects at module level: the bundle runs again on every
  mount. Add listeners in `onMounted` and remove them in `onBeforeUnmount`.
- Scope your CSS (`<style scoped>`, or a prefix of your own): the bundle's CSS
  goes into the portal's page.

**The backend** (optional): a `docker-compose.yml` at the root of the backend
folder. Its service must join the platform network so the gateway can reach
it, and it can use these variables, which the builder passes:

```yaml
services:
  my-tool-backend:
    environment:
      - PLUGIN_ROUTE_PREFIX=${PLUGIN_ROUTE_PREFIX}       # /plugin/<expose>
      - MINIO_ENDPOINT=minio:9000
      - MINIO_ACCESS_KEY=${MINIO_SERVER_ACCESS_KEY}
      - MINIO_SECRET_KEY=${MINIO_SERVER_SECRET_KEY}
    networks:
      - digitaltwins
networks:
  digitaltwins:
    external: true
    name: digitaltwins-platform   # the platform's PROJECT_NAME
```

The builder runs `docker compose` with its own environment, not the platform's
`.env`, so a variable not in that list falls back to your compose file's
default.

**`config.portal.json`** at the root of `code/`. The build fails if it isn't
valid JSON; its fields aren't used, because the registration form asks for
them.

Keep the tool runnable on its own: outside the platform there is no launch
context, and it should start from its own defaults (see below).

## Register it

In the portal, go to **Catalogue → Workflows → Register a workflow**:

1. **Source**: drag in the package folder or a `.zip` of it (up to 500 MB;
   `node_modules`, `.git`, `dist` and `build` are skipped), or give a public
   Git URL. Choose the type **Web GUI** and answer **has backend?**. With a
   backend, name the **Frontend Folder** and **Backend Folder**, relative to
   `code/`. Give a **Frontend Build Command** if yours isn't
   `npm run build:plugin`.
2. **FHIR annotation**: optional; you can add it later, until the workflow is
   approved.
3. **Build**: the builder builds the bundle. You can open the build from the
   Tool Hub to try it.
4. **Approve** it from its card. The platform registers the workflow and its
   tool in SEEK, each with a new SEEK id. Approving a newer build of the same
   workflow deletes the previous version, so assays linked to the old one have
   to be linked to the new one.

The first launch of a build with a backend builds the backend's image, which
can take minutes; later launches start it in seconds.

A rebuild uses the source stored when the workflow was registered: a Git
source is cloned again, but a local folder is not re-read. To ship new code
from a local folder, register it again.

## Link an assay

1. Tag the assay in SEEK with `gui` (an assay has exactly one of `script`,
   `notebook` or `gui`).
2. In the study dashboard, **Edit** the assay: choose your workflow, pick a
   dataset and sample type for each input, and set the cohort.
3. **Launch** opens your tool at `/tool-view?assay=<id>` with the launch
   context.

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
and read them from MinIO directly, with the MinIO variables shown under
[What your code must provide](#what-your-code-must-provide).

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
