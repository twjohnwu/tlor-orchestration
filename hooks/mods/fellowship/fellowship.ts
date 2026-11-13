import type { ThemeKey } from 'claude-code'

import type { Segment } from '../segment'
import type { FellowshipAgent } from '../../../types'

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

export const formatClock = (ms: number): string => {
  const date = new Date(ms)
  const hh = String(date.getHours()).padStart(2, '0')
  const mm = String(date.getMinutes()).padStart(2, '0')
  const ss = String(date.getSeconds()).padStart(2, '0')

  return `${hh}:${mm}:${ss}`
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

const DEFAULT_FIELDS = ['name', 'desc', 'model', 'effort', 'status', 'ctx', 'activity', 'elapsed', 'ended', 'tokens', 'tools']

// Values from the official models overview and Claude Code model-config pages, read 2026-11-14.
// First match wins, so a newer version is listed before the bare family rule it would fall into.
export const CONTEXT_WINDOWS: Array<{ pattern: RegExp; window: number }> = [
  { pattern: /\[1m\]/, window: 1_000_000 },
  { pattern: /(?:fable|mythos)-5(?!\d)/, window: 1_000_000 },
  { pattern: /opus-(?:5|4-8|4-7)(?!\d)/, window: 1_000_000 },
  { pattern: /opus-4(?:-[156])?(?!\d)/, window: 200_000 },
  { pattern: /sonnet-5(?!\d)/, window: 1_000_000 },
  { pattern: /sonnet-4(?:-[56])?(?!\d)/, window: 200_000 },
  { pattern: /haiku-5-5(?!\d)/, window: 1_000_000 },
  { pattern: /haiku-4-5(?!\d)/, window: 200_000 },
]

const contextWindow = (model: string | undefined): number | undefined =>
  model === undefined ? undefined : CONTEXT_WINDOWS.find(rule => rule.pattern.test(model))?.window

// `claude-sonnet-4-5-20250929` -> `Sonnet 4.5`; an id that is not family plus digits is shown as given.
const displayModel = (model: string): string => {
  const parts = model.toLowerCase().replace(/^claude-/, '').replace(/\[1m\]$/, '').replace(/-\d{8}$/, '').split('-')
  const [family = '', ...version] = parts
  if (family === '' || !version.every(part => /^\d+$/.test(part))) return model
  const name = family.charAt(0).toUpperCase() + family.slice(1)

  return version.length === 0 ? name : `${name} ${version.join('.')}`
}

const SPARKS = '▁▂▃▄▅▆▇█'

const sparkline = (samples: number[]): string => {
  const low = Math.min(...samples)
  const high = Math.max(...samples)

  return samples
    .map(value => SPARKS.charAt(high === low ? 0 : Math.round(((value - low) / (high - low)) * (SPARKS.length - 1))))
    .join('')
}

const formatTokens = (tokens: number): string => `${(tokens / 1000).toFixed(1)}k`

type FieldStyle = { now: number; running: boolean; dim: Pick<Segment, 'dim'>; detail: ThemeKey }

const FIELDS: Record<string, (agent: FellowshipAgent, style: FieldStyle) => Segment[]> = {
  name: (agent, { dim }) => [
    { text: `${iconFor(agent.type)} ${agent.type}`, color: modelColor(shortModel(agent.model)), bold: true, ...dim },
  ],
  desc: (agent, { dim }) => [{ text: agent.description, color: 'text', ...dim }],
  model: (agent, { running, dim }) =>
    agent.model === undefined || agent.model === ''
      ? []
      : [{ text: displayModel(agent.model), color: running ? 'warning' : 'subtle', ...dim }],
  effort: (agent, { running, dim }) =>
    agent.effort === undefined || agent.effort === ''
      ? []
      : [{ text: agent.effort === 'medium' ? 'med' : agent.effort, color: running ? 'warning' : 'subtle', ...dim }],
  status: agent => [{ text: agent.status, ...statusStyle(agent.status) }],
  ctx: (agent, { detail, dim }) => {
    const window = contextWindow(agent.model)
    if (window === undefined) return [{ text: `⬡ ${formatTokens(agent.tokens)}`, color: detail, ...dim }]
    const pct = Math.min(100, Math.max(0, Math.round((agent.tokens / window) * 100)))
    const filled = Math.min(5, Math.max(0, Math.round(pct / 20)))

    return [{ text: `⬡ ${'▓'.repeat(filled)}${'░'.repeat(5 - filled)} ${pct}%`, color: pct >= 80 ? 'warning' : detail, ...dim }]
  },
  activity: (agent, { detail, dim }) =>
    agent.samples === undefined || agent.samples.length < 2
      ? []
      : [{ text: sparkline(agent.samples.slice(-16)), color: detail, ...dim }],
  elapsed: (agent, { now, detail, dim }) => [{ text: formatElapsed((agent.endedAt ?? now) - agent.startedAt), color: detail, ...dim }],
  ended: (agent, { detail, dim }) =>
    typeof agent.endedAt === 'number' ? [{ text: `ended ${formatClock(agent.endedAt)}`, color: detail, ...dim }] : [],
  tokens: (agent, { detail, dim }) => [{ text: `${formatTokens(agent.tokens)} tok`, color: detail, ...dim }],
  tools: (agent, { detail, dim }) => [{ text: `${agent.tools} tools`, color: detail, ...dim }],
}

export const parseFields = (raw: unknown): string[] => {
  if (typeof raw !== 'string') return DEFAULT_FIELDS
  const picked = raw
    .toLowerCase()
    .split(/[\s,]+/)
    .filter((name, index, names) => Object.hasOwn(FIELDS, name) && names.indexOf(name) === index)

  return picked.length === 0 ? DEFAULT_FIELDS : picked
}

export const rowSegments = (agent: FellowshipAgent, now: number, fields: string[] = DEFAULT_FIELDS): Segment[] => {
  const running = agent.status === 'running'
  const style: FieldStyle = { now, running, dim: running ? {} : { dim: true }, detail: running ? 'text' : 'subtle' }
  const segments = fields.flatMap(name => (Object.hasOwn(FIELDS, name) ? FIELDS[name]?.(agent, style) ?? [] : []))

  return [
    ...segments.map((segment, index) => (index === 0 ? segment : { ...segment, text: `  ${segment.text}` })),
    ...attentionTags(agent, now).map(text => ({ text: `  [${text}]`, color: 'warning' as const, bold: true })),
  ]
}

export const attentionTags = (agent: FellowshipAgent, now: number): string[] => {
  if (agent.status !== 'running') return []

  return [
    ...(typeof agent.toolStartedAt === 'number' && now - agent.toolStartedAt >= 30_000 ? ['slow tool'] : []),
    ...(typeof agent.lastEventAt === 'number' && now - agent.lastEventAt >= 120_000 ? ['idle'] : []),
  ]
}

export const formatRow = (agent: FellowshipAgent, now: number, fields?: string[]): string =>
  rowSegments(agent, now, fields).map(segment => segment.text).join('')

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
): FellowshipAgent[] => (usage == null ? list : update(list, id, one => ({
    ...one,
    tokens: tokensOf(usage),
    samples: [...(one.samples ?? []), tokensOf(usage)].slice(-16),
  })))

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
  // Only hidden running rows get a summary line; older finished rows just drop off.
  const lineCount = (): number =>
    runningCount + completedCount + (running.length > runningCount ? 1 : 0)

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
