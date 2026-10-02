import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('@/views/upload-dataset/components/utils', async (orig) => ({
  ...(await orig<typeof import('@/views/upload-dataset/components/utils')>()),
  getRepoContents: vi.fn(),
}));
vi.mock('@/bootstrap/workflow_api', () => ({ useProbeWorkflowSource: vi.fn() }));
vi.mock('@/bootstrap/tool_api', () => ({ useProbeToolSource: vi.fn() }));

import { useGitRepoInfo } from '@/composables/useGithubRepoInfo';
import { getRepoContents, sdsWorkflowCwlResult } from '@/views/upload-dataset/components/utils';
import { useProbeWorkflowSource } from '@/bootstrap/workflow_api';

const entry = (name: string, type: 'file' | 'dir') => ({ name, type });

describe('useGitRepoInfo', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ tree: [] }) }) as unknown as typeof fetch;
  });

  it('detects an SDS workflow package on public GitHub', async () => {
    vi.mocked(getRepoContents).mockImplementation((async (_url: string, path = '') => {
      if (path === 'primary') {
        return { data: ['workflow_convert.cwl', 'tool_a.cwl', 'tool_b.cwl'].map((n) => entry(n, 'file')) };
      }
      if (path === 'code') return { data: [entry('tool_a', 'dir')] };
      return { data: [entry('dataset_description.xlsx', 'file'), entry('primary', 'dir'), entry('code', 'dir')] };
    }) as never);
    const { info, refresh } = useGitRepoInfo();
    await refresh('https://github.com/o/r', true, { kind: 'workflow' });
    expect(info.value.isSds).toBe(true);
    expect(info.value.cwlRepoErr?.available).toBe(true);
  });

  it('uses the backend probe result for an SDS workflow', async () => {
    vi.mocked(useProbeWorkflowSource).mockResolvedValue({
      ok: true,
      data: { foldersInRoot: [], hasCwl: true, isSds: true },
    } as never);
    const { info, refresh } = useGitRepoInfo();
    await refresh('https://github.com/o/r', true, { kind: 'workflow', auth: { token: 't' } });
    expect(info.value.isSds).toBe(true);
    expect(info.value.cwlRepoErr?.message).toBe(sdsWorkflowCwlResult(true).message);
  });
});
