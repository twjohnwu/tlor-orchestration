import type { StateRead, StateSetResult } from 'claude-code'

import type { PlanChecklist, PlanDeclaration, PlanFinishedLedger, PlanTask, StddTouched } from '../../../../types'
import type { Segment } from '../../segment'

export type ProgressFsEntry = {
  name: string
  kind: 'file' | 'dir' | 'other'
  mtimeMs: number
}

export type ProgressReadIo = {
  read: (path: string) => Promise<string>
  list: (path: string) => Promise<readonly ProgressFsEntry[]>
  cwd: () => Promise<string>
  getPlanDeclaration: () => Promise<StateRead<PlanDeclaration>>
  getPlanFinishedLedgers?: () => Promise<StateRead<PlanFinishedLedger[]>>
  setPlanFinishedLedgers?: (value: PlanFinishedLedger[], version: number) => Promise<StateSetResult>
  getPlanTasks: () => Promise<StateRead<PlanTask[]>>
  getPlanChecklist: () => Promise<StateRead<PlanChecklist | null>>
  getStddTouched: () => Promise<StateRead<StddTouched>>
  now?: () => Promise<number>
  after?: (ms: number, fn: () => void) => void
  invalidate?: () => void
  notify?: (text: string) => Promise<void>
}

export type ProgressToolIo = ProgressReadIo & {
  now: NonNullable<ProgressReadIo['now']>
  after: NonNullable<ProgressReadIo['after']>
  invalidate: NonNullable<ProgressReadIo['invalidate']>
  setPlanDeclaration: (value: PlanDeclaration, version: number) => Promise<StateSetResult>
  setPlanTasks: (value: PlanTask[], version: number) => Promise<StateSetResult>
  setPlanChecklist: (value: PlanChecklist | null, version: number) => Promise<StateSetResult>
  setStddTouched: (value: StddTouched, version: number) => Promise<StateSetResult>
}

// Returned by `lines` when the source could not produce its view and the whole
// band must render nothing for this draw; the source keeps no cache so the
// next draw retries. Later sources are not consulted.
export const BAND_RETRY = 'retry' as const

export type SourceLines = Segment[][] | null | undefined | typeof BAND_RETRY

export type SourceId = 'stdd' | 'planDeclared' | 'planTasks' | 'planChecklist'

export type ProgressSource = {
  // Stable identity, so a caller can tell which source drew a band without reading its text.
  id: SourceId
  onToolCall: (
    event: Readonly<Record<string, unknown>>,
    result: unknown,
    io: ProgressToolIo,
  ) => Promise<void>
  // Optional read-only warm-up, run for every source before the first lines call of a draw.
  prime?: (io: ProgressReadIo) => Promise<void>
  lines: (io: ProgressReadIo, columns: number | undefined) => Promise<SourceLines>
}

export type OrderedLines = { lines: SourceLines, source?: SourceId }

// The first source whose lines are not undefined, with that source's id.
export const orderedSourceLines = async (
  sources: readonly ProgressSource[],
  io: ProgressReadIo,
  columns: number | undefined,
): Promise<OrderedLines> => {
  for (const source of sources) await source.prime?.(io)
  for (const source of sources) {
    const lines = await source.lines(io, columns)
    if (lines !== undefined) return { lines, source: source.id }
  }

  return { lines: undefined }
}

export const orderedLines = async (
  sources: readonly ProgressSource[],
  io: ProgressReadIo,
  columns: number | undefined,
): Promise<SourceLines> => (await orderedSourceLines(sources, io, columns)).lines
