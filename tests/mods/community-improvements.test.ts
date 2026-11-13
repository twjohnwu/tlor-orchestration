import type { On } from 'claude-code'
import { expect, mock, test, type Engine } from 'claude-code/testing'

import { formatClock, parseFields, rowSegments } from '../../hooks/mods/fellowship/fellowship'
import type { FellowshipAgent } from '../../types'

const running = {
  id: 'a1',
  type: 'eagle-sentinel',
  description: 'verify',
  status: 'running' as const,
  startedAt: 0,
  endedAt: null,
  tokens: 0,
  tools: 0,
  lastEventAt: 0,
}

const rowText = (agent: typeof running, now: number): string =>
  rowSegments(agent, now).map(segment => segment.text).join('')

test('slow tool attention starts at 30 seconds, not 29 seconds', async () => {
  const agent = { ...running, toolStartedAt: 1000, lastEventAt: 1000 }

  expect(rowText(agent, 30_999)).not.toContain('slow tool')
  expect(rowText(agent, 31_000)).toContain('slow tool')
})

test('idle attention starts at 120 seconds and finished rows have no attention tags', async () => {
  expect(rowText(running, 119_999)).not.toContain('idle')
  expect(rowText(running, 120_000)).toContain('idle')

  const finished = { ...running, status: 'completed' as const, endedAt: 120_000, toolStartedAt: 0 }
  const text = rowSegments(finished, 999_999).map(segment => segment.text).join('')
  expect(text).not.toContain('idle')
  expect(text).not.toContain('slow tool')
})

const fieldsAgent: FellowshipAgent = {
  ...running,
  description: 'verify',
  tokens: 380_000,
  tools: 7,
  model: 'claude-sonnet-5-5',
  effort: 'medium',
  samples: [1, 2, 3, 4],
}

const fieldText = (agent: FellowshipAgent, fields?: string[]): string =>
  rowSegments(agent, 75_000, fields).map(segment => segment.text).join('')

const ctxSegment = (agent: FellowshipAgent) =>
  rowSegments(agent, 0, ['ctx'])[0]

test('the default fields render in order with exact text', async () => {
  expect(fieldText(fieldsAgent)).toBe(
    '🦅 eagle-sentinel  verify  Sonnet 5.5  med  running  ⬡ ▓▓░░░ 38%  ▁▃▆█  01:15  380.0k tok  7 tools',
  )
  const ended = { ...fieldsAgent, status: 'completed' as const, endedAt: 61_000 }
  expect(fieldText(ended)).toBe(
    `🦅 eagle-sentinel  verify  Sonnet 5.5  med  completed  ⬡ ▓▓░░░ 38%  ▁▃▆█  01:01  ended ${formatClock(61_000)}  380.0k tok  7 tools`,
  )
})

test('fellowship_fields picks and orders the fields; attention tags stay last', async () => {
  expect(fieldText(fieldsAgent, parseFields('elapsed,name'))).toBe('01:15  🦅 eagle-sentinel')
  const idle = { ...fieldsAgent, lastEventAt: 0 }
  expect(fieldText(idle, ['status'])).toBe('running')
  expect(rowSegments(idle, 130_000, ['status']).map(segment => segment.text).join('')).toBe('running  [idle]')
})

test('parseFields drops unknown names and duplicates and accepts case and whitespace', async () => {
  expect(parseFields('name,bogus,elapsed')).toEqual(['name', 'elapsed'])
  expect(parseFields('name,elapsed,name')).toEqual(['name', 'elapsed'])
  expect(parseFields('ELAPSED, Name')).toEqual(['elapsed', 'name'])
  expect(parseFields('elapsed name\ttokens')).toEqual(['elapsed', 'name', 'tokens'])
  const everything = ['name', 'desc', 'model', 'effort', 'status', 'ctx', 'activity', 'elapsed', 'ended', 'tokens', 'tools']
  expect(parseFields('')).toEqual(everything)
  expect(parseFields('bogus')).toEqual(everything)
  expect(parseFields(undefined)).toEqual(everything)
  expect(parseFields(5)).toEqual(everything)
})

test('model field shows a display name', async () => {
  const shown = (model: string | undefined): string | undefined =>
    rowSegments({ ...fieldsAgent, model }, 0, ['model'])[0]?.text
  expect(shown('claude-sonnet-5-5')).toBe('Sonnet 5.5')
  expect(shown('claude-fable-5-2')).toBe('Fable 5.2')
  expect(shown('claude-sonnet-4-5-20250929')).toBe('Sonnet 4.5')
  expect(shown('claude-opus-4-6[1m]')).toBe('Opus 4.6')
  expect(shown('sonnet')).toBe('Sonnet')
  expect(shown(undefined)).toBeUndefined()
  expect(rowSegments({ ...fieldsAgent, effort: undefined }, 0, ['effort'])).toEqual([])
})

test('ctx shows gauge and percent for a known window', async () => {
  const at = (tokens: number, model = 'claude-sonnet-5-5') => ctxSegment({ ...fieldsAgent, tokens, model })
  expect(at(0)?.text).toBe('⬡ ░░░░░ 0%')
  expect(at(380_000)?.text).toBe('⬡ ▓▓░░░ 38%')
  expect(at(1_000_000)?.text).toBe('⬡ ▓▓▓▓▓ 100%')
  expect(at(2_500_000)?.text).toBe('⬡ ▓▓▓▓▓ 100%')
  expect(at(790_000)?.color).toBe('text')
  expect(at(800_000)?.color).toBe('warning')
})

test('ctx falls back to tokens when the window is unknown', async () => {
  expect(ctxSegment({ ...fieldsAgent, tokens: 76_000, model: 'opus' })?.text).toBe('⬡ 76.0k')
  expect(ctxSegment({ ...fieldsAgent, tokens: 76_000, model: undefined })?.text).toBe('⬡ 76.0k')
  expect(ctxSegment({ ...fieldsAgent, tokens: 76_000, model: 'gpt-x' })?.text).toBe('⬡ 76.0k')
})

test('context windows follow the model id', async () => {
  const pct = (model: string): string | undefined =>
    ctxSegment({ ...fieldsAgent, tokens: 100_000, model })?.text
  expect(pct('claude-opus-4-6[1m]')).toBe('⬡ ▓░░░░ 10%')
  expect(pct('claude-opus-4-8')).toBe('⬡ ▓░░░░ 10%')
  expect(pct('claude-opus-4-7')).toBe('⬡ ▓░░░░ 10%')
  expect(pct('claude-opus-4-5-20251101')).toBe('⬡ ▓▓▓░░ 50%')
  expect(pct('claude-opus-4-6')).toBe('⬡ ▓▓▓░░ 50%')
  expect(pct('claude-opus-4-20250514')).toBe('⬡ ▓▓▓░░ 50%')
  expect(pct('claude-sonnet-4-6')).toBe('⬡ ▓▓▓░░ 50%')
  expect(pct('claude-sonnet-5')).toBe('⬡ ▓░░░░ 10%')
  expect(pct('claude-haiku-4-5')).toBe('⬡ ▓▓▓░░ 50%')
  expect(pct('claude-haiku-5-5')).toBe('⬡ ▓░░░░ 10%')
  expect(pct('claude-fable-5')).toBe('⬡ ▓░░░░ 10%')
})

test('activity draws a sparkline of the samples', async () => {
  const spark = (samples: number[] | undefined): string | undefined =>
    rowSegments({ ...fieldsAgent, samples }, 0, ['activity'])[0]?.text
  expect(spark([1, 2, 3, 4])).toBe('▁▃▆█')
  expect(spark([5, 5, 5])).toBe('▁▁▁')
  expect(spark([7])).toBeUndefined()
  expect(spark([])).toBeUndefined()
  expect(spark(undefined)).toBeUndefined()
  expect(spark(Array.from({ length: 20 }, (_, index) => index))).toHaveLength(16)
  const legacy: FellowshipAgent = { ...running }
  expect(() => rowSegments(legacy, 0)).not.toThrow()
})

const BAND = {
  plugin: 'tlor',
  surface: 'terminal',
  component: 'AbovePrompt',
  props: { hasSurvey: false },
  viewport: { columns: 80, rows: 24 },
} as never

const bandHas = async (ui: { find: (query: { type: string; text: RegExp }) => Promise<unknown> }, text: RegExp): Promise<boolean> =>
  (await ui.find({ type: 'Text', text })) !== undefined

type ChecklistDisk = { files: Record<string, string> }

const mountChecklistDisk = (on: On, disk: ChecklistDisk) => {
  const clock = mock.clock(on)
  on('session.cwd', async () => ({ value: '/work' }) as never)
  on('fs.list', async () => ({ value: [] }) as never)
  on('fs.read', async (_$, e) => ({ value: disk.files[(e as { path: string }).path] ?? '' }) as never)
  on('tool.call', async (_$, e) => {
    if (e.tool === 'Write') disk.files[e.file_path] = e.content
    if (e.tool === 'Edit') {
      disk.files[e.file_path] = (disk.files[e.file_path] ?? '').replace(e.old_string, e.new_string)
    }
    return { result: {} } as never
  })
  on('ui.render', ($, e) => {
    const { Text } = $.ui.resolve(e)
    return h(Text, null, '') as never
  })
  return clock
}

test('a known ticked checklist title stays ticked after an edit unticks it', {
  options: { fellowship: 'off', stdd_progress: 'off', plan_progress: 'on' },
}, async ($, on) => {
  const path = '/work/plan.md'
  mountChecklistDisk(on, { files: {} })
  await $.tool.call({
    tool: 'Write',
    file_path: path,
    content: '- [x] first   step\n- [ ] second\n- [ ] third',
  })
  const ui = await $.ui.mount(BAND)
  expect(await bandHas(ui as never, /Plan · plan\.md · 1\/3 items/)).toBe(true)

  await $.tool.call({
    tool: 'Edit',
    file_path: path,
    old_string: '- [x] first   step',
    new_string: '- [ ] first step',
  })
  expect(await bandHas(ui as never, /Plan · plan\.md · 1\/3 items/)).toBe(true)
  expect(await bandHas(ui as never, /▶ second/)).toBe(true)
})

test('plan autoclose hides at its deadline and not before', {
  options: { fellowship: 'off', stdd_progress: 'off', plan_progress: 'on', plan_autoclose_s: 2 },
}, async ($, on) => {
  const path = '/work/plan.md'
  const clock = mountChecklistDisk(on, { files: {} })
  await $.tool.call({ tool: 'Write', file_path: path, content: '- [x] one\n- [x] two' })
  const ui = await $.ui.mount(BAND)

  expect(await bandHas(ui as never, /Plan · plan\.md · 2\/2 items/)).toBe(true)
  await clock.advance(1999)
  expect(await bandHas(ui as never, /Plan · plan\.md · 2\/2 items/)).toBe(true)
  await clock.advance(1)
  expect(await bandHas(ui as never, /Plan ·/)).toBe(false)
})

test('plan autoclose zero never hides a completed plan', {
  options: { fellowship: 'off', stdd_progress: 'off', plan_progress: 'on', plan_autoclose_s: 0 },
}, async ($, on) => {
  const path = '/work/plan.md'
  const clock = mountChecklistDisk(on, { files: {} })
  await $.tool.call({ tool: 'Write', file_path: path, content: '- [x] one\n- [x] two' })
  const ui = await $.ui.mount(BAND)

  await clock.advance(600_000)
  expect(await bandHas(ui as never, /Plan · plan\.md · 2\/2 items/)).toBe(true)
})

let spawned = 0
const spawnInput = {
  tool_use_id: 'spawn-1',
  prompt: 'p',
  description: 'verify',
  subagentType: 'eagle-sentinel',
  isAborted: false,
  turnId: 'turn-1',
} as never

const fellowshipCommand = {
  command: 'fellowship',
  args: '',
  origin: { kind: 'composer' },
  presentation: { isFullscreen: false, columns: 80 },
} as const

const mountFellowship = (on: On, toasts: string[]): void => {
  mock.clock(on)
  on('agent.spawn', async () => {
    spawned += 1
    return { agentId: `agent-${spawned}`, model: 'claude-sonnet-4-5' } as never
  })
  on('turn.complete', async () => ({ text: '' }) as never)
  on('ui.open', async () => ({ value: { isPlaced: true } }) as never)
  on('ui.toast', async (_$, e) => {
    toasts.push((e as { text: string }).text)
    return { value: undefined } as never
  })
  on('ui.render', ($, e) => {
    const { Text } = $.ui.resolve(e)
    return h(Text, null, '') as never
  })
}

const completeAgent = async ($: Engine, agentId: string): Promise<void> => {
  await $.turn.complete({
    turnId: 'turn-1',
    reason: 'answer',
    answer: '',
    durationMs: 1,
    agentId,
    isAborted: false,
  } as never)
}

test('notify off emits no completion toast', {
  options: { fellowship: 'manual', stdd_progress: 'off', plan_progress: 'off', notify: 'off' },
}, async ($, on) => {
  const toasts: string[] = []
  mountFellowship(on, toasts)
  const result = await $.agent.spawn(spawnInput)
  await completeAgent($, (result as { agentId: string }).agentId)

  expect(toasts.filter(text => text.includes('done'))).toEqual([])
})

test('notify toast emits exactly once for an agent completion', {
  options: { fellowship: 'manual', stdd_progress: 'off', plan_progress: 'off', notify: 'toast' },
}, async ($, on) => {
  const toasts: string[] = []
  mountFellowship(on, toasts)
  const result = await $.agent.spawn(spawnInput)
  await completeAgent($, (result as { agentId: string }).agentId)

  expect(toasts.filter(text => text === 'eagle-sentinel done (00:00)')).toHaveLength(1)
})

test('notify toast emits once when the main plan reaches 100% and ignores subagent plan events', {
  options: { fellowship: 'off', stdd_progress: 'off', plan_progress: 'on', notify: 'toast' },
}, async ($, on) => {
  const toasts: string[] = []
  mock.clock(on)
  on('tool.call', async () => ({ result: {} }) as never)
  on('ui.toast', async (_$, e) => {
    toasts.push((e as { text: string }).text)
    return { value: undefined } as never
  })
  on('ui.render', ($, e) => {
    const { Text } = $.ui.resolve(e)
    return h(Text, null, '') as never
  })

  await $.tool.call({ tool: 'TodoWrite', todos: [{ content: 'one', status: 'pending', activeForm: 'one' }] })
  await $.tool.call({
    tool: 'TodoWrite',
    agentId: 'subagent-1',
    todos: [{ content: 'child', status: 'completed' }],
  } as never)
  await $.tool.call({ tool: 'TodoWrite', todos: [{ content: 'one', status: 'completed', activeForm: 'one' }] })
  await $.ui.mount(BAND)
  await $.ui.mount(BAND)

  expect(toasts.filter(text => text === 'Plan complete')).toHaveLength(1)
})

test('/fellowship returns empty text and current row text without a second formatter', {
  options: { fellowship: 'manual', stdd_progress: 'off', plan_progress: 'off' },
}, async ($, on) => {
  mountFellowship(on, [])
  const empty = await $.command.run(fellowshipCommand)
  expect((empty as { text: string }).text).toBe('No agents yet.')

  await $.agent.spawn(spawnInput)
  const rows = await $.command.run(fellowshipCommand)
  expect((rows as { text: string }).text).toContain('🦅 eagle-sentinel')
  expect((rows as { text: string }).text.split('\n')).toHaveLength(1)
})

test('STDD notifies once when a main-session change first becomes done', {
  options: { fellowship: 'off', stdd_progress: 'on', plan_progress: 'off', notify: 'toast' },
}, async ($, on) => {
  const disk = { tasks: '- [ ] `S-01`\n' }
  const toasts: string[] = []
  mock.clock(on)
  on('session.cwd', async () => ({ value: '/work' }) as never)
  on('fs.list', async (_$, e) => {
    const path = (e as { path: string }).path
    if (path === '/work') return { value: [{ name: 'STDD', kind: 'dir', mtimeMs: 1 }] } as never
    if (path === '/work/STDD') return { value: [{ name: 'checkout', kind: 'dir', mtimeMs: 1 }] } as never
    if (path === '/work/STDD/checkout') {
      return { value: [
        { name: 'spec.md', kind: 'file', mtimeMs: 1 },
        { name: 'tasks.md', kind: 'file', mtimeMs: 2 },
      ] } as never
    }
    return { value: [] } as never
  })
  on('fs.read', async (_$, e) => ({
    value: (e as { path: string }).path.endsWith('spec.md')
      ? '---\nstatus: approved\n---\n'
      : disk.tasks,
  }) as never)
  on('tool.call', async () => ({ result: {} }) as never)
  on('ui.toast', async (_$, e) => {
    toasts.push((e as { text: string }).text)
    return { value: undefined } as never
  })
  on('ui.render', ($, e) => {
    const { Text } = $.ui.resolve(e)
    return h(Text, null, '') as never
  })

  await $.ui.mount(BAND)
  disk.tasks = '- [x] `S-01`\n'
  await $.tool.call({
    tool: 'Edit',
    file_path: '/work/STDD/checkout/tasks.md',
    old_string: '',
    new_string: '',
  })
  await $.tool.call({
    tool: 'Edit',
    agentId: 'subagent-1',
    file_path: '/work/STDD/checkout/tasks.md',
  } as never)

  expect(toasts.filter(text => text === 'STDD checkout complete')).toHaveLength(1)
})
