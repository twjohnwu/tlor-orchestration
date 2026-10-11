import type { ThemeKey } from 'claude-code'

import type { FellowshipAgent } from '../../../types'

export type Segment = {
  text: string
  color?: ThemeKey
  bold?: boolean
  dim?: boolean
}

export const FALLBACK_ICON = '🤖'

export const ICONS: Record<string, string> = {
  'rohirrim-outrider': '🏇',
  'ranger-pathfinder': '🧭',
  'gondor-builder': '🔨',
  'dwarf-smith': '⚒️',
  'eagle-sentinel': '🦅',
  'noldor-loremaster': '📜',
  'bilbo-scribe': '✒️',
  'cirdan-shipwright': '⚓',
  'elf-archer': '🏹',
  'orc-saboteur': '🗡️',
  'hobbit-gardener': '🌱',
  'mirror-of-galadriel': '🪞',
  'palantir-stone': '🔮',
  'bombadil-freeagent': '🎵',
  Explore: '🧭',
}

export const iconFor = (type: string | undefined): string =>
  (type !== undefined && Object.hasOwn(ICONS, type) ? ICONS[type] : undefined) ?? FALLBACK_ICON

export const formatElapsed = (ms: number): string => {
  const total = Math.max(0, Math.floor(ms / 1000))
  const mm = String(Math.floor(total / 60)).padStart(2, '0')
  const ss = String(total % 60).padStart(2, '0')

  return `${mm}:${ss}`
}

export const shortModel = (model: string | undefined): string => {
  if (model === undefined || model === '') return '-'
  const family = /haiku|sonnet|opus|fable/.exec(model.toLowerCase())

  return family === null ? model : family[0]
}

const modelColor = (model: string): ThemeKey => {
  if (model === 'opus') return 'claude'
  if (model === 'sonnet') return 'suggestion'
  if (model === 'haiku') return 'ide'
  if (model === 'fable') return 'merged'
  return 'text'
}

const statusStyle = (status: FellowshipAgent['status']): Pick<Segment, 'color' | 'bold'> => {
  if (status === 'running') return { color: 'warning', bold: true }
  if (status === 'completed') return { color: 'success' }
  if (status === 'failed') return { color: 'error', bold: true }
  return { color: 'inactive' }
}

export const rowSegments = (agent: FellowshipAgent, now: number): Segment[] => {
  const elapsed = formatElapsed((agent.endedAt ?? now) - agent.startedAt)
  const tokens = (agent.tokens / 1000).toFixed(1)
  const effort = agent.effort === undefined || agent.effort === '' ? '-' : agent.effort
  const model = shortModel(agent.model)
  const dim = agent.status === 'running' ? {} : { dim: true }

  return [
    { text: `${iconFor(agent.type)} ${agent.type}`, color: modelColor(model), bold: true, ...dim },
    { text: `  ${model}/${effort}`, color: 'subtle', ...dim },
    { text: `  ${agent.description}`, color: 'text', ...dim },
    { text: `  ${agent.status}`, ...statusStyle(agent.status) },
    { text: `  ${elapsed}`, color: 'subtle', ...dim },
    { text: `  ${tokens}k tok`, color: 'subtle', ...dim },
    { text: `  ${agent.tools} tools`, color: 'subtle', ...dim },
  ]
}

export const formatRow = (agent: FellowshipAgent, now: number): string =>
  rowSegments(agent, now).map(segment => segment.text).join('')

// Records a spawned agent: the only way a row is created. A repeated spawn of one id updates its row.
export const register = (
  list: FellowshipAgent[],
  agent: FellowshipAgent,
): FellowshipAgent[] =>
  list.some(one => one.id === agent.id)
    ? list.map(one => (one.id === agent.id ? { ...one, ...agent } : one))
    : [...list, agent]

// Applies a patch to a row that a spawn already recorded; an unknown id (main thread, an engine
// fork, an event ahead of its spawn) leaves the list as it was.
export const update = (
  list: FellowshipAgent[],
  id: string | undefined,
  patch: (agent: FellowshipAgent) => FellowshipAgent,
): FellowshipAgent[] =>
  id !== undefined && list.some(one => one.id === id)
    ? list.map(one => (one.id === id ? patch(one) : one))
    : list

export const isKnown = (list: FellowshipAgent[], id: string | undefined): boolean =>
  id !== undefined && list.some(one => one.id === id)

// Each request re-reads the whole context, so the latest step's total is the agent's size; summing would recount it.
export const recordStepTokens = (
  list: FellowshipAgent[],
  id: string | undefined,
  usage: Parameters<typeof tokensOf>[0] | null,
): FellowshipAgent[] => (usage == null ? list : update(list, id, one => ({ ...one, tokens: tokensOf(usage) })))

export const completeAgent = (
  list: FellowshipAgent[],
  id: string | undefined,
  status: FellowshipAgent['status'],
  endedAt: number,
): FellowshipAgent[] => update(list, id, one => ({ ...one, status, endedAt }))

export type FellowshipSelection = {
  running: FellowshipAgent[]
  completed: FellowshipAgent[]
  hiddenRunning: number
  hiddenCompleted: number
}

export const parseMaxRows = (value: unknown): number => {
  if (typeof value !== 'number' && typeof value !== 'string') return 8
  if (typeof value === 'string' && value.trim() === '') return 8
  const parsed = typeof value === 'number' ? value : Number(value)

  return Number.isFinite(parsed) && parsed >= 1 ? Math.min(50, Math.floor(parsed)) : 8
}

const latestCompleted = (completed: FellowshipAgent[], count: number): FellowshipAgent[] =>
  completed
    .map((agent, index) => ({ agent, index }))
    .sort((left, right) =>
      ((right.agent.endedAt ?? Number.NEGATIVE_INFINITY) - (left.agent.endedAt ?? Number.NEGATIVE_INFINITY)) ||
      right.index - left.index,
    )
    .slice(0, count)
    .sort((left, right) => left.index - right.index)
    .map(one => one.agent)

// Quotas cap agent rows. Summary lines also consume viewport room, so a tight pane drops
// completed rows first and then running rows while retaining their hidden counts.
export const selectPaneRows = (list: FellowshipAgent[], maxRows: number, room: number): FellowshipSelection => {
  const running = list.filter(one => one.status === 'running')
  const completed = list.filter(one => one.status !== 'running')
  const cap = parseMaxRows(maxRows)
  const runningQuota = Math.round(cap * 5 / 8)
  let runningCount = Math.min(running.length, runningQuota)
  let completedCount = Math.min(completed.length, cap - runningQuota)
  const available = Number.isFinite(room) ? Math.max(0, Math.floor(room)) : 0
  const lineCount = (): number =>
    runningCount + completedCount +
    (running.length > runningCount ? 1 : 0) +
    (completed.length > completedCount ? 1 : 0)

  while (lineCount() > available && completedCount > 0) completedCount -= 1
  while (lineCount() > available && runningCount > 0) runningCount -= 1

  const visibleRunning = runningCount === 0 ? [] : running.slice(-runningCount)
  const visibleCompleted = latestCompleted(completed, completedCount)

  return {
    running: visibleRunning,
    completed: visibleCompleted,
    hiddenRunning: running.length - visibleRunning.length,
    hiddenCompleted: completed.length - visibleCompleted.length,
  }
}

// Reads `model:` and `effort:` out of a role file's leading frontmatter block.
export const parseFrontmatter = (text: string): { model?: string; effort?: string } => {
  const block = /^---\r?\n([\s\S]*?)\r?\n---/.exec(text)
  if (block === null) return {}
  const pick = (key: string): string | undefined => {
    const hit = new RegExp(`^${key}:[ \\t]*(.+?)[ \\t]*$`, 'm').exec(block[1] ?? '')
    const value = hit?.[1]?.replace(/^["']|["']$/g, '')

    return value === undefined || value === '' ? undefined : value
  }

  return { model: pick('model'), effort: pick('effort') }
}

// A role name that is safe to put in a path.
export const isRoleName = (type: string): boolean => /^[\w.-]+$/.test(type)

export const hasRunning = (list: FellowshipAgent[]): boolean =>
  list.some(one => one.status === 'running')

// Counts every token the step processed, cached input included, matching the engine's own agent total.
export const tokensOf = (
  usage:
    | {
        input_tokens?: number
        output_tokens?: number
        cache_read_input_tokens?: number | null
        cache_creation_input_tokens?: number | null
      }
    | undefined,
): number =>
  (usage?.input_tokens ?? 0) +
  (usage?.output_tokens ?? 0) +
  (usage?.cache_read_input_tokens ?? 0) +
  (usage?.cache_creation_input_tokens ?? 0)

export const statusOf = (reason: string): FellowshipAgent['status'] =>
  reason === 'aborted' ? 'killed' : reason === 'refusal' || reason === 'error' ? 'failed' : 'completed'
