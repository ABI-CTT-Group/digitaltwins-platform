import { describe, expect, it } from 'vitest';
import * as XLSX from 'xlsx';
import { readSampleTypesFromFiles } from '../sampleTypes';

// A real .xlsx written by SheetJS, so these tests go through the same `XLSX.read` and
// `sheet_to_json` calls the upload form makes when a dataset folder is dropped.
const xlsxFile = (path: string, rows: unknown[][]) => {
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, XLSX.utils.aoa_to_sheet(rows), 'Sheet1');
  const bytes: ArrayBuffer = XLSX.write(wb, { type: 'array', bookType: 'xlsx' });
  const f = new File([bytes], path.split('/').pop()!);
  Object.defineProperty(f, 'webkitRelativePath', { value: path });
  // jsdom's File has no arrayBuffer(); browsers do.
  Object.defineProperty(f, 'arrayBuffer', { value: async () => bytes });
  return f;
};

const SPARC_HEADER = ['sample id', 'subject id', 'Sample_Type'];

describe('readSampleTypesFromFiles', () => {
  it('reads the de-duplicated sample type column from samples.xlsx', async () => {
    const samples = xlsxFile('ds/samples.xlsx', [
      SPARC_HEADER,
      ['sam-1', 'sub-1', 'Blood'],
      ['sam-2', 'sub-1', 'blood'],
      ['sam-3', 'sub-2', ''],
      ['sam-4', 'sub-2', 'Tissue'],
    ]);
    expect(await readSampleTypesFromFiles([samples])).toEqual(['Blood', 'Tissue']);
  });

  it('prefers the samples.xlsx at the dataset root over a nested copy', async () => {
    const nested = xlsxFile('ds/primary/samples.xlsx', [SPARC_HEADER, ['sam-1', 'sub-1', 'Nested']]);
    const root = xlsxFile('ds/samples.xlsx', [SPARC_HEADER, ['sam-1', 'sub-1', 'Root']]);
    expect(await readSampleTypesFromFiles([nested, root])).toEqual(['Root']);
  });

  it('returns no sample types when samples.xlsx has no sample type column', async () => {
    const samples = xlsxFile('ds/samples.xlsx', [['sample id'], ['sam-1']]);
    expect(await readSampleTypesFromFiles([samples])).toEqual([]);
  });
});
