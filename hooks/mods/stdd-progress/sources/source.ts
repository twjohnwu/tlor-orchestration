import type { StateRead, StateSetResult } from 'claude-code'

import type { PlanChecklist, PlanTask } from '../../../../types'
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
  getPlanTasks: () => Promise<StateRead<PlanTask[]>>
  getPlanChecklist: () => Promise<StateRead<PlanChecklist | null>>
}

export type ProgressToolIo = ProgressReadIo & {
  now: () => Promise<number>
  after: (ms: number, fn: () => void) => void
  invalidate: () => void
  setPlanTasks: (value: PlanTask[], version: number) => Promise<StateSetResult>
  setPlanChecklist: (value: PlanChecklist | null, version: number) => Promise<StateSetResult>
}

// Returned by `lines` when the source could not produce its view and the whole
// band must render nothing for this draw; the source keeps no cache so the
// next draw retries. Later sources are not consulted.
export const BAND_RETRY = 'retry' as const

export type SourceLines = Segment[][] | null | undefined | typeof BAND_RETRY

export type ProgressSource = {
  onToolCall: (
    event: Readonly<Record<string, unknown>>,
    result: unknown,
    io: ProgressToolIo,
  ) => Promise<void>
  // Optional read-only warm-up, run for every source before the first lines call of a draw.
  prime?: (io: ProgressReadIo) => Promise<void>
  lines: (io: ProgressReadIo, columns: number | undefined) => Promise<SourceLines>
}

export const orderedLines = async (
  sources: readonly ProgressSource[],
  io: ProgressReadIo,
  columns: number | undefined,
): Promise<SourceLines> => {
  for (const source of sources) await source.prime?.(io)
  for (const source of sources) {
    const lines = await source.lines(io, columns)
    if (lines !== undefined) return lines
  }

  return undefined
}
