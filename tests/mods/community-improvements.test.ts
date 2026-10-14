import type { On } from 'claude-code'
import { expect, mock, test, type Engine } from 'claude-code/testing'

import { rowSegments } from '../../hooks/mods/fellowship/fellowship'

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

  await $.tool.call({ tool: 'TodoWrite', todos: [{ content: 'one', status: 'pending' }] })
  await $.tool.call({
    tool: 'TodoWrite',
    agentId: 'subagent-1',
    todos: [{ content: 'child', status: 'completed' }],
  } as never)
  await $.tool.call({ tool: 'TodoWrite', todos: [{ content: 'one', status: 'completed' }] })
  await $.ui.mount(BAND)
  await $.ui.mount(BAND)

  expect(toasts.filter(text => text === 'Plan complete')).toHaveLength(1)
})

test('/fellowship returns empty text and current row text without a second formatter', {
  options: { fellowship: 'manual', stdd_progress: 'off', plan_progress: 'off' },
}, async ($, on) => {
  mountFellowship(on, [])
  const empty = await $.command.run({ command: 'fellowship' })
  expect((empty as { text: string }).text).toBe('No agents yet.')

  await $.agent.spawn(spawnInput)
  const rows = await $.command.run({ command: 'fellowship' })
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
  await $.tool.call({ tool: 'Edit', file_path: '/work/STDD/checkout/tasks.md' })
  await $.tool.call({
    tool: 'Edit',
    agentId: 'subagent-1',
    file_path: '/work/STDD/checkout/tasks.md',
  } as never)

  expect(toasts.filter(text => text === 'STDD checkout complete')).toHaveLength(1)
})
