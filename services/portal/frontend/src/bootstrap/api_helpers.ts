/**
 * Shared API helpers for tool and workflow operations.
 *
 * These functions exist to avoid duplicating near-identical logic between
 * tool_api.ts and workflow_api.ts.
 */

import http from './http';
import { AxiosError } from 'axios';
import type {
  CheckNameResponse,
  BuildResponse,
  ToolDeployResponse,
} from '@/models/types';

// ---------------------------------------------------------------------------
// Task 5.5: Unified name-check function
// ---------------------------------------------------------------------------

/**
 * Check whether a tool or workflow name is available.
 *
 * @param scope  'tool' checks `/tools/check-name`; 'workflow' checks `/workflow/check-name`
 * @param name   The name string to validate
 */
export async function useCheckName(
  scope: 'tool' | 'workflow',
  name: string,
): Promise<CheckNameResponse> {
  const endpoint = scope === 'tool' ? '/tools/check-name' : '/workflow/check-name';
  try {
    return await http.get<CheckNameResponse>(endpoint, { name });
  } catch (err) {
    const axiosErr = err as AxiosError<{ detail: string }>;
    if (axiosErr.response?.status === 400) {
      return { available: false, message: axiosErr.response.data.detail };
    }
    return { available: false, message: 'Name cannot be used.' };
  }
}

// ---------------------------------------------------------------------------
// Task 5.4: Shared "fetch list + enrich with latest build" helper
// ---------------------------------------------------------------------------

/**
 * Fetch a list of items and enrich each with the status from its most recent build.
 *
 * @param listUrl      URL to fetch the base list (GET)
 * @param buildsUrlFn  Function that returns the builds URL for a given item id
 * @param enrichFn     Optional async function to add extra fields (e.g. deploy status) after the build lookup
 */
export async function fetchWithLatestBuild<
  T extends { id: string; description?: string },
>(
  listUrl: string,
  buildsUrlFn: (id: string) => string,
  enrichFn?: (item: T, latestBuild: BuildResponse) => Promise<Partial<T>>,
): Promise<(T & { status: string; latestBuildId?: string })[]> {
  const items = await http.get<T[]>(listUrl);

  const enriched = await Promise.all(
    items.map(async (item) => {
      let buildStatus = 'pending';
      let latestBuildId: string | undefined;
      let extra: Partial<T> = {};

      try {
        const builds = await http.get<BuildResponse[]>(buildsUrlFn(item.id));
        if (builds.length > 0) {
          const latestBuild = builds.sort(
            (a, b) =>
              new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime(),
          )[0];
          buildStatus = latestBuild.status;
          latestBuildId = latestBuild.buildId;

          if (enrichFn) {
            extra = await enrichFn(item, latestBuild);
          }
        }
      } catch (err) {
        console.warn(`Failed to fetch builds for ${item.id}:`, err);
      }

      return {
        ...item,
        description: item.description === '' ? 'No description available' : item.description,
        status: buildStatus,
        latestBuildId: latestBuildId,
        ...extra,
      };
    }),
  );

  return enriched;
}
