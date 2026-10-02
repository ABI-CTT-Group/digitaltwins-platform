/** An SDS workflow package's steps, each with the ports of the primary/tool_*.cwl it runs. */
export interface SdsStepAnnotation {
  step: string;
  tool: string;
  inputs: { name: string; resource: string }[];
  outputs: { name: string; resource: string; code: string; system: string; unit: string }[];
}

/** CWL ports and steps come as a map (`{id: …}`) or a list (`[{id, …}]`). */
const ids = (section: any): string[] =>
  Array.isArray(section) ? section.map((entry) => entry.id) : Object.keys(section ?? {});

export function sdsWorkflowSteps(workflowCwl: any, toolCwls: { cwlFile: string; content: any }[]): SdsStepAnnotation[] {
  const steps = workflowCwl?.steps ?? {};
  const entries: [string, any][] = Array.isArray(steps) ? steps.map((s: any) => [String(s.id).replace(/^#/, ''), s]) : Object.entries(steps);
  return entries.map(([step, def]) => {
    const tool = toolCwls.find((t) => t.cwlFile === String(def?.run).split('/').pop());
    if (!tool) throw new Error(`Step ${step} runs ${def?.run}, which is not a tool CWL in primary/`);
    return {
      step,
      tool: tool.cwlFile,
      inputs: ids(tool.content?.inputs).map((name) => ({ name, resource: '' })),
      outputs: ids(tool.content?.outputs).map((name) => ({ name, resource: '', code: '', system: '', unit: '' })),
    };
  });
}
