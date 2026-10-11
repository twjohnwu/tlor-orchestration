import type { On } from 'claude-code'
import { test, expect, mock, type Engine } from 'claude-code/testing'

import { register as registerMods } from '../../hooks/mods/register'
import type { FellowshipAgent } from '../../types'
import {
  FALLBACK_ICON,
  addStepTokens,
  completeAgent,
  formatRow,
  iconFor,
  parseFrontmatter,
  register,
  selectPaneRows,
  shortModel,
  statusOf,
  tokensOf,
  update,
} from '../../hooks/mods/fellowship/fellowship'

test('icon lookup uses the map and falls back to the robot', async () => {
  expect(iconFor('gondor-builder')).toBe('🔨')
  expect(iconFor('Explore')).toBe('🧭')
  expect(iconFor('general-purpose')).toBe(FALLBACK_ICON)
  expect(iconFor('toString')).toBe(FALLBACK_ICON)
  expect(iconFor(undefined)).toBe('🤖')
})

test('pane row format', async () => {
  const agent = {
    id: 'a1',
    type: 'eagle-sentinel',
    description: 'verify diff',
    status: 'running' as const,
    startedAt: 1000,
    endedAt: null,
    tokens: 12345,
    tools: 7,
    model: 'claude-opus-4-7',
    effort: 'medium',
  }
  expect(formatRow(agent, 1000 + 75_000)).toBe('🦅 eagle-sentinel  opus/medium  verify diff  running  01:15  12.3k tok  7 tools')
  expect(formatRow({ ...agent, status: 'completed', endedAt: 61_000 }, 999_999)).toBe(
    '🦅 eagle-sentinel  opus/medium  verify diff  completed  01:00  12.3k tok  7 tools',
  )
  expect(formatRow({ ...agent, model: undefined, effort: undefined }, 1000)).toBe(
    '🦅 eagle-sentinel  -/-  verify diff  running  00:00  12.3k tok  7 tools',
  )
})

test('model ids shorten to their family', async () => {
  expect(shortModel('claude-haiku-4-5-20251001')).toBe('haiku')
  expect(shortModel('sonnet')).toBe('sonnet')
  expect(shortModel('claude-fable-5')).toBe('fable')
  expect(shortModel('gpt-x')).toBe('gpt-x')
  expect(shortModel(undefined)).toBe('-')
})

test('frontmatter yields model and effort', async () => {
  expect(parseFrontmatter('---\nname: x\nmodel: haiku\neffort: low\n---\nbody\nmodel: opus')).toEqual({
    model: 'haiku',
    effort: 'low',
  })
  expect(parseFrontmatter('no block')).toEqual({})
})

const spawned = {
  id: 'a1',
  type: 'rohirrim-outrider',
  description: 'locate',
  status: 'running' as const,
  startedAt: 0,
  endedAt: null,
  tokens: 0,
  tools: 0,
}

test('only a spawn creates a row; events of unknown ids and the main thread are ignored', async () => {
  const bump = (one: FellowshipAgent) => ({ ...one, tools: one.tools + 1 })
  const one = register([], spawned)
  expect(one).toHaveLength(1)
  expect(register(one, spawned)).toHaveLength(1)

  const hit = update(one, 'a1', bump)
  expect(hit).toHaveLength(1)
  expect(hit[0]?.tools).toBe(1)

  expect(update(one, 'ghost', bump)).toBe(one)
  expect(update(one, undefined, bump)).toBe(one)
})

test('pane selection keeps every running row and the newest completed rows with a summary', async () => {
  const row = (id: string, status: 'running' | 'completed') => ({ ...spawned, id, status })
  const list = [row('done-1', 'completed'), row('run-1', 'running'), row('done-2', 'completed'), row('run-2', 'running'), row('done-3', 'completed')]

  const selected = selectPaneRows(list, 4)
  expect(selected.rows.map(one => one.id)).toEqual(['run-1', 'run-2', 'done-3'])
  expect(selected.hiddenCompleted).toBe(2)

  const roomy = selectPaneRows(list, 5)
  expect(roomy.rows.map(one => one.id)).toEqual(['run-1', 'run-2', 'done-1', 'done-2', 'done-3'])
  expect(roomy.hiddenCompleted).toBe(0)
})

test('a completed turn does not count step tokens twice', async () => {
  const afterStep = addStepTokens([spawned], 'a1', { input_tokens: 120, output_tokens: 30 })
  const afterComplete = completeAgent(afterStep, 'a1', 'completed', 500)

  expect(afterStep[0]?.tokens).toBe(150)
  expect(afterComplete[0]?.tokens).toBe(150)
  expect(afterComplete[0]?.status).toBe('completed')
  expect(afterComplete[0]?.endedAt).toBe(500)
})

const BAND_REGISTRATION = ['tool.call', 'ui.render']

const recordRegistrations = (options: { fellowship: string; stdd_progress: string }): string[] => {
  const events: string[] = []
  const on = ((event: string) => {
    events.push(event)
    return { catch: () => undefined }
  }) as never

  registerMods(on, options as never)
  return events
}

test('each mod switches off on its own', async () => {
  const fellowshipOff = recordRegistrations({ fellowship: 'off', stdd_progress: 'on' })
  expect(fellowshipOff).toEqual(BAND_REGISTRATION)

  const stddOff = recordRegistrations({ fellowship: 'auto', stdd_progress: 'off' })
  expect(stddOff).toContain('session.start')
  expect(stddOff).toContain('agent.spawn')
  expect(stddOff).not.toEqual(BAND_REGISTRATION)
  expect(stddOff).toHaveLength(recordRegistrations({ fellowship: 'auto', stdd_progress: 'on' }).length - BAND_REGISTRATION.length)
})

let spawnCount = 0
const spawnInput = (description: string) => ({
  tool_use_id: `t-${description}`,
  prompt: 'p',
  description,
  subagentType: 'rohirrim-outrider',
  isAborted: false,
  turnId: 'turn-1',
}) as never

// Bottom hooks must be registered before the test first calls $.
const bottom = (on: On, opened: string[]): void => {
  mock.clock(on)
  on('agent.spawn', async () => {
    spawnCount += 1
    return { agentId: `a${spawnCount}`, model: 'claude-sonnet-4-5' } as never
  })
  on('ui.open', async (_$, e) => {
    opened.push((e as { id: string }).id)
    return { value: { isPlaced: true } } as never
  })
  on('turn.step', async function* (_$, e) {
    return { turnId: e.turnId, index: e.index, answer: '', toolUses: [], usage: { input_tokens: 100, output_tokens: 20 } } as never
  })
  on('turn.complete', async () => ({ text: '' }) as never)
}

const complete = async ($: Engine, agentId: string): Promise<void> => {
  await $.turn.complete({ turnId: 'turn-1', reason: 'answer', answer: '', durationMs: 1, agentId, isAborted: false } as never)
}

const mountPane = async ($: Engine, rows: number) => {
  return $.ui.mount({
    plugin: 'tlor',
    surface: 'terminal',
    component: 'Pane',
    props: {} as never,
    requestId: 'tlor-fellowship',
    viewport: { columns: 120, rows },
  } as never)
}

test('fellowship manual does not open the pane on agent.spawn', { options: { fellowship: 'manual', stdd_progress: 'off' } }, async ($, on) => {
  const opened: string[] = []
  bottom(on, opened)
  await $.agent.spawn(spawnInput('locate'))
  expect(opened).toEqual([])
})

test('fellowship auto opens the pane on agent.spawn', { options: { fellowship: 'auto', stdd_progress: 'off' } }, async ($, on) => {
  const opened: string[] = []
  bottom(on, opened)
  await $.agent.spawn(spawnInput('locate'))
  expect(opened).toEqual(['tlor-fellowship'])
})

test('pane render text shows the +K done line when completed rows are dropped', { options: { fellowship: 'manual', stdd_progress: 'off' } }, async ($, on) => {
  bottom(on, [])
  const ids: string[] = []
  for (const name of ['d1', 'd2', 'd3']) {
    const spawned = await $.agent.spawn(spawnInput(name))
    ids.push((spawned as { agentId: string }).agentId)
  }
  for (const id of ids) await complete($, id)

  // rows 5 leaves room for one row, so two of the three completed rows are hidden
  const ui = await mountPane($, 6)
  expect(await ui.find({ type: 'Text', text: '+2 done' })).toBeDefined()
})

test('several turn.step usages add up and turn.complete adds nothing', { options: { fellowship: 'manual', stdd_progress: 'off' } }, async ($, on) => {
  bottom(on, [])
  const spawned = await $.agent.spawn(spawnInput('locate'))
  const id = (spawned as { agentId: string }).agentId
  for (let index = 0; index < 3; index += 1) {
    const stream = $.turn.step({ turnId: 'turn-1', index, model: 'claude-sonnet-4-5', messageCount: 1, agentId: id } as never)
    for await (const _chunk of stream) {
      // drain the stream so the hook chain finishes
    }
  }
  const ui = await mountPane($, 24)
  expect(await ui.find({ type: 'Text', text: /0\.4k tok/ })).toBeDefined()
  await ui.unmount()

  await complete($, id)
  const done = await mountPane($, 24)
  expect(await done.find({ type: 'Text', text: /0\.4k tok/ })).toBeDefined()
  expect(await done.find({ type: 'Text', text: /completed/ })).toBeDefined()
})

test('step tokens include cached input', async () => {
  expect(tokensOf({ input_tokens: 10, output_tokens: 5, cache_read_input_tokens: 40_000, cache_creation_input_tokens: 2_000 })).toBe(42_015)
  expect(tokensOf({ input_tokens: 10, output_tokens: 5, cache_read_input_tokens: null, cache_creation_input_tokens: null })).toBe(15)
})

test('turn end reason maps to row status', async () => {
  expect(statusOf('answer')).toBe('completed')
  expect(statusOf('aborted')).toBe('killed')
  expect(statusOf('error')).toBe('failed')
  expect(statusOf('refusal')).toBe('failed')
})
