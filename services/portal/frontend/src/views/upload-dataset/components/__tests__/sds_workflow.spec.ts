import { describe, expect, it } from 'vitest';
import { sdsWorkflowSteps } from '../sds_workflow';

const tool = (cwlFile: string, inputs: any, outputs: any) => ({ cwlFile, content: { class: 'CommandLineTool', inputs, outputs } });

describe('sdsWorkflowSteps', () => {
  it('maps each step to the ports of the tool it runs (map form)', () => {
    const wf = { steps: { convert: { run: 'tool_a.cwl', in: {}, out: [] } } };
    expect(sdsWorkflowSteps(wf, [tool('tool_a.cwl', { src: 'Directory' }, { nifti: 'File' })])).toEqual([{
      step: 'convert', tool: 'tool_a.cwl',
      inputs: [{ name: 'src', resource: '' }],
      outputs: [{ name: 'nifti', resource: '', code: '', system: '', unit: '' }],
    }]);
  });

  it('accepts list-form steps and ports', () => {
    const wf = { steps: [{ id: 'convert', run: 'tool_a.cwl' }] };
    const [step] = sdsWorkflowSteps(wf, [tool('tool_a.cwl', [{ id: 'src', type: 'Directory' }], [{ id: 'nifti' }])]);
    expect(step.inputs.map((p) => p.name)).toEqual(['src']);
    expect(step.outputs.map((p) => p.name)).toEqual(['nifti']);
  });

  it('matches a tool by the basename of run, and ignores a leading # on a list-form step id', () => {
    const wf = { steps: [{ id: '#convert', run: './tool_a.cwl' }] };
    const [step] = sdsWorkflowSteps(wf, [tool('tool_a.cwl', {}, {})]);
    expect(step).toMatchObject({ step: 'convert', tool: 'tool_a.cwl' });
  });

  it('names a step whose tool CWL is not in primary/', () => {
    const wf = { steps: { convert: { run: 'tool_missing.cwl' } } };
    expect(() => sdsWorkflowSteps(wf, [])).toThrow(/convert.*tool_missing\.cwl/);
  });
});
