import { describe, expect, it } from 'vitest';
import JSZip from 'jszip';
import { useLocalFolderInfo } from '@/composables/useLocalFolderInfo';
import type { LocalSource } from '@/bootstrap/upload_source';

const file = (path: string) => {
  const f = new File(['x'], path.split('/').pop()!);
  Object.defineProperty(f, 'webkitRelativePath', { value: path });
  return f;
};
const folder = (paths: string[]): LocalSource =>
  ({ kind: 'folder', rootName: 'workflow_convert', files: paths.map(file) }) as LocalSource;
const SDS_WORKFLOW = [
  'workflow_convert/dataset_description.xlsx',
  'workflow_convert/primary/workflow_convert.cwl',
  'workflow_convert/primary/tool_a.cwl',
  'workflow_convert/primary/tool_b.cwl',
  'workflow_convert/code/tool_a.py',
];

describe('useLocalFolderInfo', () => {
  it('accepts an SDS workflow package for a workflow', async () => {
    const { info, refresh } = useLocalFolderInfo();
    await refresh(folder(SDS_WORKFLOW), true, 'workflow');
    expect(info.value.isSds).toBe(true);
    expect(info.value.cwlExists).toBe(true);
    expect(info.value.cwlRepoErr?.available).toBe(true);
  });

  it('needs exactly one primary/workflow_*.cwl', async () => {
    const { info, refresh } = useLocalFolderInfo();
    await refresh(folder([...SDS_WORKFLOW, 'workflow_convert/primary/workflow_other.cwl']), true, 'workflow');
    expect(info.value.cwlExists).toBe(false);
    expect(info.value.cwlRepoErr?.message).toContain('primary/workflow_*.cwl');
  });

  it('keeps the root-.cwl rule for a workflow source tree', async () => {
    const { info, refresh } = useLocalFolderInfo();
    await refresh(folder(['flow/flow.cwl', 'flow/scripts/run.py']), true, 'workflow');
    expect(info.value.isSds).toBe(false);
    expect(info.value.cwlRepoErr?.available).toBe(true);
  });

  it('still requires one primary/tool_*.cwl for a tool', async () => {
    const { info, refresh } = useLocalFolderInfo();
    await refresh(folder(SDS_WORKFLOW), true, 'tool'); // two tool CWLs
    expect(info.value.cwlExists).toBe(false);
  });

  it('reads an SDS workflow zip with a wrapper folder', async () => {
    const zip = new JSZip();
    SDS_WORKFLOW.forEach((p) => zip.file(p, 'x'));
    const blob = await zip.generateAsync({ type: 'blob' });
    const { info, refresh } = useLocalFolderInfo();
    await refresh({ kind: 'zip', rootName: 'workflow_convert', blob } as LocalSource, true, 'workflow');
    expect(info.value.cwlRepoErr?.available).toBe(true);
  });
});
