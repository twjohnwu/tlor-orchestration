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

export const shortModel = (model: string | undefined): string => {
  if (model === undefined || model === '') return '-'
  const family = /haiku|sonnet|opus|fable/.exec(model.toLowerCase())

  return family === null ? model : family[0]
}

export const formatRow = (agent: FellowshipAgent, now: number): string => {
  const elapsed = formatElapsed((agent.endedAt ?? now) - agent.startedAt)
  const tokens = (agent.tokens / 1000).toFixed(1)
  const effort = agent.effort === undefined || agent.effort === '' ? '-' : agent.effort

  return `${iconFor(agent.type)} ${agent.type}  ${shortModel(agent.model)}/${effort}  ${agent.description}  ${agent.status}  ${elapsed}  ${tokens}k tok  ${agent.tools} tools`
}

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

export const addStepTokens = (
  list: FellowshipAgent[],
  id: string | undefined,
  usage: { input_tokens?: number; output_tokens?: number } | null | undefined,
): FellowshipAgent[] => update(list, id, one => ({ ...one, tokens: one.tokens + tokensOf(usage ?? undefined) }))

export const completeAgent = (
  list: FellowshipAgent[],
  id: string | undefined,
  status: FellowshipAgent['status'],
  endedAt: number,
): FellowshipAgent[] => update(list, id, one => ({ ...one, status, endedAt }))

export type FellowshipSelection = {
  rows: FellowshipAgent[]
  hiddenCompleted: number
}

// Running rows are never hidden. Completed rows use the remaining room, reserving one row for
// the summary whenever some completed rows must be omitted.
export const selectPaneRows = (list: FellowshipAgent[], maxRows: number): FellowshipSelection => {
  const running = list.filter(one => one.status === 'running')
  const completed = list.filter(one => one.status !== 'running')
  const room = Math.max(0, Math.floor(maxRows) - running.length)

  if (completed.length <= room) return { rows: [...running, ...completed], hiddenCompleted: 0 }

  const visibleCount = Math.max(0, room - 1)
  const visible = visibleCount === 0 ? [] : completed.slice(-visibleCount)

  return {
    rows: [...running, ...visible],
    hiddenCompleted: completed.length - visible.length,
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
