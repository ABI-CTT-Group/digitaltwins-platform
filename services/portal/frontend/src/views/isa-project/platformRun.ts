// Real runs for the sandbox (prototype). The Test Project example mirrors the platform's Test Project,
// so its assays are linked to those platform assays, and Launch and Submit run them with the platform's
// own saved configuration. Nothing here writes assay configuration.
import { useToast } from "vue-toastification";
import { useDashboardGetAssayLaunch, useDashboardSubmitAssayResults } from "@/bootstrap/dashboard_api";
import { useDashboardCacheStore } from "@/store/dashboard_cache_store";
import { getApiErrorMessage } from "@/utils/common";
import type { IsaProjectEntry } from "./sandbox";

/** A sandbox assay's platform assay, and the state of its requests, for its card. */
export interface PlatformLink { seekId: string; canMonitor: boolean; launching: boolean; downloading: boolean; submitting: boolean }

/** Example id → sandbox assay id → SEEK assay id of the platform assay it mirrors. */
const PLATFORM_ASSAYS: Record<string, Record<string, string>> = {
  "example-test-project": { "a-cohort": "41", "a-convert": "42", "a-visualise": "43", "a-breast-app": "45" },
};

/** The platform assays a project's assays are linked to; none for uploads or unlinked examples. */
export function platformAssayIds(entry: IsaProjectEntry | undefined): Record<string, string> {
  return entry?.source === "example" ? PLATFORM_ASSAYS[entry.exampleId ?? ""] ?? {} : {};
}

/** Launch a platform assay as the dashboard does. True when it started. */
export async function launchPlatformAssay(seekId: string): Promise<boolean> {
  const toast = useToast();
  try {
    const res = await useDashboardGetAssayLaunch(seekId);
    if (!res) {
      toast.warning("Launch is not available for this assay. Please check the configuration.");
      return false;
    }
    if (res.message) {
      toast.info(res.message, { timeout: 6000 });
      return false;
    }
    if (res.type === "airflow") {
      useDashboardCacheStore().setAssayExecute(seekId, "Monitor", res.data);
      toast.success("Workflow launched successfully. Click Monitor to track progress.");
    } else if (res.type === "notebook") {
      useDashboardCacheStore().setAssayExecute(seekId, "Monitor", res.data);
      window.open(res.data, "_blank");
    } else if (res.type === "gui") {
      window.open(res.data, "_blank");
    }
    return true;
  } catch (e: unknown) {
    toast.error(getApiErrorMessage(e, "Launch"));
    return false;
  }
}

/** Upload a platform assay's latest run as datasets. True when it worked. */
export async function submitPlatformAssay(seekId: string): Promise<boolean> {
  const toast = useToast();
  try {
    await useDashboardSubmitAssayResults(seekId);
    toast.success("Successfully submitted assay results.");
    return true;
  } catch (e: unknown) {
    toast.error(getApiErrorMessage(e, "Submit"));
    return false;
  }
}
