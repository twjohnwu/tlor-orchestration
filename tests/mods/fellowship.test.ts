import type { On } from 'claude-code'
import { test, expect, mock, type Engine } from 'claude-code/testing'

import { register as registerMods } from '../../hooks/mods/register'
import type { FellowshipAgent } from '../../types'
import {
  FALLBACK_ICON,
  recordStepTokens,
  completeAgent,
  formatClock,
  formatRow,
  iconFor,
  parseFrontmatter,
  parseMaxRows,
  register,
  rowSegments,
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
  const endedClock = formatClock(61_000)
  expect(formatRow(agent, 1000 + 75_000)).toBe('🦅 eagle-sentinel  opus/medium  verify diff  running  01:15  12.3k tok  7 tools')
  expect(formatRow({ ...agent, status: 'completed', endedAt: 61_000 }, 999_999)).toBe(
    `🦅 eagle-sentinel  opus/medium  verify diff  completed  01:00  ended ${endedClock}  12.3k tok  7 tools`,
  )
  expect(formatRow({ ...agent, model: undefined, effort: undefined }, 1000)).toBe(
    '🦅 eagle-sentinel  -/-  verify diff  running  00:00  12.3k tok  7 tools',
  )
})

test('clock formatting uses local time with zero-padded fields', async () => {
  const timestamp = new Date(2026, 0, 2, 3, 4, 5).getTime()
  expect(formatClock(timestamp)).toBe('03:04:05')
})

test('finished rows show their local end clock and running rows do not', async () => {
  const endedAt = new Date(2026, 0, 2, 3, 4, 5).getTime()
  const expected = new Date(endedAt)
  const clock = [expected.getHours(), expected.getMinutes(), expected.getSeconds()]
    .map(value => String(value).padStart(2, '0'))
    .join(':')
  const finished = { ...spawned, status: 'completed' as const, endedAt }

  expect(formatRow(finished, endedAt)).toContain(`ended ${clock}`)
  expect(formatRow(spawned, endedAt)).not.toContain('ended ')
})

test('row segments colour model families and preserve the plain formatter', async () => {
  const base = {
    id: 'a1',
    type: 'eagle-sentinel',
    description: 'verify diff',
    status: 'running' as const,
    startedAt: 1000,
    endedAt: null,
    tokens: 12345,
    tools: 7,
    effort: 'medium',
  }
  const families = [
    ['claude-opus-4-7', 'claude'],
    ['claude-sonnet-4-5', 'suggestion'],
    ['claude-haiku-4-5', 'ide'],
    ['claude-fable-5', 'merged'],
    ['gpt-x', 'text'],
  ] as const

  for (const [model, color] of families) {
    const agent = { ...base, model }
    const segments = rowSegments(agent, 76_000)
    expect(segments[0]).toEqual({ text: '🦅 eagle-sentinel', color, bold: true })
    expect(segments.map(segment => segment.text).join('')).toBe(formatRow(agent, 76_000))
  }
})

test('row segments colour statuses and dim every non-status segment after finishing', async () => {
  const base = {
    ...spawned,
    model: 'sonnet',
    effort: 'high',
    endedAt: 1000,
  }
  const statuses = [
    ['running', 'warning', true],
    ['completed', 'success', undefined],
    ['failed', 'error', true],
    ['killed', 'inactive', undefined],
  ] as const

  for (const [status, color, bold] of statuses) {
    const agent = { ...base, status, endedAt: status === 'running' ? null : 1000 }
    const segments = rowSegments(agent, 1000)
    const statusSegment = segments.find(segment => segment.text === `  ${status}`)
    expect(statusSegment).toEqual({ text: `  ${status}`, color, ...(bold === undefined ? {} : { bold }) })
    expect(segments.filter(segment => segment !== statusSegment).every(segment =>
      status === 'running' ? segment.dim !== true : segment.dim === true,
    )).toBe(true)
    expect(segments.map(segment => segment.text).join('')).toBe(formatRow(agent, 1000))
  }
})

test('running rows brighten model/effort to warning and detail segments to text; finished rows stay subtle', async () => {
  const base = { ...spawned, model: 'sonnet', effort: 'high' }
  const colours = (agent: FellowshipAgent): Array<string | undefined> =>
    [1, 4, 5, 6].map(index => rowSegments(agent, 5000)[index]?.color)

  expect(colours({ ...base, status: 'running', endedAt: null })).toEqual(['warning', 'text', 'text', 'text'])
  for (const status of ['completed', 'failed', 'killed'] as const) {
    const agent = { ...base, status, endedAt: 2000 }
    expect(colours(agent)).toEqual(['subtle', 'subtle', 'subtle', 'subtle'])
    expect([1, 4, 5, 6].every(index => rowSegments(agent, 5000)[index]?.dim === true)).toBe(true)
  }
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

test('pane selection uses the default 5/3 quotas and keeps the latest-ended completed rows', async () => {
  const running = Array.from({ length: 7 }, (_, index) => ({
    ...spawned,
    id: `run-${index + 1}`,
    startedAt: index + 1,
  }))
  const ended = [10, 60, 30, 50, 20, 40]
  const completed = ended.map((endedAt, index) => ({
    ...spawned,
    id: `done-${index + 1}`,
    status: 'completed' as const,
    startedAt: index + 20,
    endedAt,
  }))

  const selected = selectPaneRows([...completed, ...running], 8, 20)
  expect(selected.running.map(one => one.id)).toEqual(['run-3', 'run-4', 'run-5', 'run-6', 'run-7'])
  expect(selected.hiddenRunning).toBe(2)
  expect(selected.completed.map(one => one.id)).toEqual(['done-2', 'done-4', 'done-6'])
  expect(selected.hiddenCompleted).toBe(3)
})

test('pane selection rounds a four-row cap to three running and one completed', async () => {
  const running = Array.from({ length: 4 }, (_, index) => ({ ...spawned, id: `run-${index + 1}` }))
  const completed = Array.from({ length: 2 }, (_, index) => ({
    ...spawned,
    id: `done-${index + 1}`,
    status: 'completed' as const,
    endedAt: index + 1,
  }))

  const selected = selectPaneRows([...running, ...completed], 4, 20)
  expect(selected.running.map(one => one.id)).toEqual(['run-2', 'run-3', 'run-4'])
  expect(selected.completed.map(one => one.id)).toEqual(['done-2'])
  expect(selected.hiddenRunning).toBe(1)
  expect(selected.hiddenCompleted).toBe(1)
})

test('a small viewport trims completed rows before running rows', async () => {
  const running = Array.from({ length: 7 }, (_, index) => ({ ...spawned, id: `run-${index + 1}` }))
  const completed = Array.from({ length: 6 }, (_, index) => ({
    ...spawned,
    id: `done-${index + 1}`,
    status: 'completed' as const,
    endedAt: index + 1,
  }))

  const completedTrimmed = selectPaneRows([...running, ...completed], 8, 8)
  expect(completedTrimmed.running).toHaveLength(5)
  expect(completedTrimmed.completed.map(one => one.id)).toEqual(['done-5', 'done-6'])
  expect(completedTrimmed.hiddenRunning).toBe(2)
  expect(completedTrimmed.hiddenCompleted).toBe(4)

  const runningTrimmed = selectPaneRows([...running, ...completed], 8, 5)
  expect(runningTrimmed.running.map(one => one.id)).toEqual(['run-4', 'run-5', 'run-6', 'run-7'])
  expect(runningTrimmed.completed).toHaveLength(0)
  expect(runningTrimmed.hiddenRunning).toBe(3)
  expect(runningTrimmed.hiddenCompleted).toBe(6)
})

test('invalid fellowship row caps fall back to eight and valid caps stop at fifty', async () => {
  for (const value of [undefined, '', 'nope', 0, -1, Number.NaN]) {
    expect(parseMaxRows(value)).toBe(8)
  }
  expect(parseMaxRows('4')).toBe(4)
  expect(parseMaxRows(51)).toBe(50)
})

test('a completed turn does not count step tokens twice', async () => {
  const afterStep = recordStepTokens([spawned], 'a1', { input_tokens: 120, output_tokens: 30 })
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

const fellowshipRows = async ($: Engine): Promise<string> =>
  ((await $.command.run({ command: 'fellowship' })) as { text: string }).text

const deferred = () => {
  let resolve!: () => void
  const promise = new Promise<void>(done => {
    resolve = done
  })
  return { promise, resolve }
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

test('slow tool follows the oldest of two parallel calls until both finish', { options: { fellowship: 'manual', stdd_progress: 'off' } }, async ($, on) => {
  const clock = mock.clock(on)
  const first = deferred()
  const second = deferred()
  const bothStarted = deferred()
  let started = 0
  on('agent.spawn', async () => ({ agentId: 'parallel-agent', model: 'claude-sonnet-4-5' }) as never)
  on('ui.open', async () => ({ value: { isPlaced: true } }) as never)
  on('tool.call', async (_$, e) => {
    started += 1
    if (started === 2) bothStarted.resolve()
    await (e.tool === 'First' ? first.promise : second.promise)
    return { result: {} } as never
  })

  const spawned = await $.agent.spawn(spawnInput('parallel tools'))
  const id = (spawned as { agentId: string }).agentId
  const firstCall = $.tool.call({ tool: 'First', agentId: id } as never)
  const secondCall = $.tool.call({ tool: 'Second', agentId: id } as never)
  await bothStarted.promise

  await clock.advance(5000)
  first.resolve()
  await firstCall
  await clock.advance(26_000)
  expect(await fellowshipRows($)).toContain('slow tool')

  second.resolve()
  await secondCall
  expect(await fellowshipRows($)).not.toContain('slow tool')
})

test('a thrown tool call clears slow tool state and preserves the error', { options: { fellowship: 'manual', stdd_progress: 'off' } }, async ($, on) => {
  const clock = mock.clock(on)
  const failure = new Error('tool exploded')
  on('agent.spawn', async () => ({ agentId: 'throwing-agent', model: 'claude-sonnet-4-5' }) as never)
  on('ui.open', async () => ({ value: { isPlaced: true } }) as never)
  on('tool.call', async () => {
    throw failure
  })

  const spawned = await $.agent.spawn(spawnInput('throwing tool'))
  const id = (spawned as { agentId: string }).agentId
  let caught: unknown
  try {
    await $.tool.call({ tool: 'Throwing', agentId: id } as never)
  } catch (error) {
    caught = error
  }
  expect(caught).toBeDefined()
  expect((caught as Error).message).toContain('no implementation for tool.call')

  await clock.advance(40_000)
  expect(await fellowshipRows($)).not.toContain('slow tool')
})

test('pane render drops older completed rows without a +K done line', { options: { fellowship: 'manual', stdd_progress: 'off' } }, async ($, on) => {
  bottom(on, [])
  const ids: string[] = []
  for (const name of ['d1', 'd2', 'd3']) {
    const spawned = await $.agent.spawn(spawnInput(name))
    ids.push((spawned as { agentId: string }).agentId)
  }
  for (const id of ids) await complete($, id)

  // rows 5 leaves room for one row, so two of the three completed rows are hidden
  const ui = await mountPane($, 6)
  expect(await ui.find({ type: 'Text', text: /\+\d+ done/ })).toBeUndefined()
  expect(await ui.find({ type: 'Text', text: /d3/ })).toBeDefined()
})

test('pane render honors fellowship_max_rows and shows the running summary', { options: { fellowship: 'manual', fellowship_max_rows: 2, stdd_progress: 'off' } }, async ($, on) => {
  bottom(on, [])
  for (const name of ['r1', 'r2', 'r3']) await $.agent.spawn(spawnInput(name))

  const ui = await mountPane($, 24)
  expect(await ui.find({ type: 'Text', text: /r3/ })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: '+2 running' })).toBeDefined()
})

test('several turn.step usages show the latest step and turn.complete adds nothing', { options: { fellowship: 'manual', stdd_progress: 'off' } }, async ($, on) => {
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
  expect(await ui.find({ type: 'Text', text: /0\.1k tok/ })).toBeDefined()
  await ui.unmount()

  await complete($, id)
  const done = await mountPane($, 24)
  expect(await done.find({ type: 'Text', text: /0\.1k tok/ })).toBeDefined()
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

test('tokens show the latest step, not a running sum', async () => {
  const first = recordStepTokens([spawned], 'a1', { input_tokens: 100, output_tokens: 20, cache_read_input_tokens: 60_000 })
  const second = recordStepTokens(first, 'a1', { input_tokens: 50, output_tokens: 10, cache_read_input_tokens: 61_000 })
  expect(second[0]?.tokens).toBe(61_060)
  expect(recordStepTokens(second, 'a1', null)[0]?.tokens).toBe(61_060)
})

test('all agents finished: exactly the three latest rows, using every line of a tight pane', async () => {
  const done = [5, 70, 10, 60, 20, 50, 30].map((endedAt, index) => ({
    ...spawned,
    id: `done-${index + 1}`,
    status: 'completed' as const,
    startedAt: index + 1,
    endedAt,
  }))
  const roomy = selectPaneRows(done, 8, 20)
  expect(roomy.running).toEqual([])
  expect(roomy.completed.map(one => one.id)).toEqual(['done-2', 'done-4', 'done-6'])

  // no summary line is drawn for hidden finished rows, so three lines of room hold three rows
  const tight = selectPaneRows(done, 8, 3)
  expect(tight.completed).toHaveLength(3)
})
