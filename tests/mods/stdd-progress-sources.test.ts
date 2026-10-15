import type { On, PluginOptions } from 'claude-code'
import { test, expect } from 'claude-code/testing'

import { CHECKLIST_TOOLS, PLAN_TOOLS, STDD_TOOLS } from '../../hooks/mods/stdd-progress/progress'
import { register } from '../../hooks/mods/stdd-progress/register'
import { createChecklistSource } from '../../hooks/mods/stdd-progress/sources/checklist'
import { createPlanTasksSource } from '../../hooks/mods/stdd-progress/sources/planTasks'
import { BAND_RETRY, orderedLines } from '../../hooks/mods/stdd-progress/sources/source'
import type { ProgressReadIo, ProgressSource, ProgressToolIo } from '../../hooks/mods/stdd-progress/sources/source'
import { createStddSource } from '../../hooks/mods/stdd-progress/sources/stdd'
import { throttled } from '../../hooks/mods/stdd-progress/throttle'

test('throttled runs immediately and coalesces calls into one trailing run', async () => {
  let time = 0
  let runs = 0
  const scheduled: Array<() => void> = []
  const throttle = throttled(1000)
  const trigger = (): Promise<void> => throttle.run(
    async () => time,
    (_ms, fn) => { scheduled.push(fn) },
    async () => { runs += 1 },
  )

  await trigger()
  await trigger()
  await trigger()
  expect(runs).toBe(1)
  expect(scheduled).toHaveLength(1)

  time = 1000
  scheduled[0]?.()
  await Promise.resolve()
  expect(runs).toBe(2)
})

test('throttled records the last scan time only after a successful run', async () => {
  let time = 0
  let shouldFail = true
  let runs = 0
  const throttle = throttled(1000)
  const trigger = (): Promise<void> => throttle.run(
    async () => time,
    () => undefined,
    async () => {
      runs += 1
      if (shouldFail) throw new Error('scan failed')
    },
  )

  await trigger()
  shouldFail = false
  time = 1
  await trigger()
  expect(runs).toBe(2)
})

const readIo = (overrides: Partial<ProgressReadIo> = {}): ProgressReadIo => ({
  read: async () => '',
  list: async () => [],
  cwd: async () => '/work',
  getPlanTasks: async () => ({ value: [], version: 0 }),
  getPlanChecklist: async () => ({ value: null, version: 0 }),
  getStddTouched: async () => ({ value: undefined, version: 0 }),
  ...overrides,
})

test('STDD lines returns undefined when no active change claims the band', async () => {
  expect(await createStddSource().lines(readIo(), 80)).toBeUndefined()
})

test('plan-task lines distinguishes no plan from a completed plan', async () => {
  expect(await createPlanTasksSource().lines(readIo(), 80)).toBeUndefined()
  expect(await createPlanTasksSource().lines(readIo({
    getPlanTasks: async () => ({
      value: [{ id: '1', subject: 'done', status: 'completed' }],
      version: 1,
    }),
  }), 80)).toBeNull()
})

test('checklist lines distinguishes no tracked file from a completed checklist', async () => {
  expect(await createChecklistSource().lines(readIo(), 80)).toBeUndefined()
  expect(await createChecklistSource().lines(readIo({
    getPlanChecklist: async () => ({ value: { path: '/work/plan.md' }, version: 1 }),
    read: async () => '- [x] one\n- [X] two',
  }), 80)).toBeNull()
})

test('source order is respected and null stops the chain', async () => {
  const visited: string[] = []
  const source = (name: string, value: Awaited<ReturnType<ProgressSource['lines']>>): ProgressSource => ({
    onToolCall: async () => undefined,
    lines: async () => {
      visited.push(name)
      return value
    },
  })
  const visible = [[{ text: 'late' }]]

  expect(await orderedLines([
    source('stdd', undefined),
    source('tasks', null),
    source('checklist', visible),
  ], readIo(), 80)).toBeNull()
  expect(visited).toEqual(['stdd', 'tasks'])
})

test('throttled markRun starts a window so the next call is trailing', async () => {
  const scheduled: Array<() => void> = []
  let runs = 0
  const throttle = throttled(1000)
  throttle.markRun(0)
  await throttle.run(async () => 10, (_ms, fn) => { scheduled.push(fn) }, async () => { runs += 1 })
  expect(runs).toBe(0)
  expect(scheduled).toHaveLength(1)
})

test('writing a tracked checklist file does not read it twice in the same call', async () => {
  let reads = 0
  let tracked: { value: { path: string } | null, version: number } = { value: null, version: 0 }
  const scheduled: Array<() => void> = []
  const io: ProgressToolIo = {
    ...readIo({
      read: async () => {
        reads += 1
        return '- [ ] one\n- [ ] two'
      },
      getPlanChecklist: async () => tracked,
    }),
    now: async () => 5,
    after: (_ms, fn) => { scheduled.push(fn) },
    invalidate: () => undefined,
    setPlanTasks: async () => ({ isSet: true }) as never,
    setPlanChecklist: async value => {
      tracked = { value, version: tracked.version + 1 }
      return { isSet: true } as never
    },
    setStddTouched: async () => ({ isSet: true }) as never,
  }

  await createChecklistSource().onToolCall({ tool: 'Write', file_path: '/work/plan.md' }, {}, io)
  expect(reads).toBe(1)
  expect(scheduled).toHaveLength(1)
})

test('a failed first STDD scan empties the band, skips later sources, and retries next draw', async () => {
  let failing = true
  const stdd = createStddSource()
  const io = readIo({
    getStddTouched: async () => ({ value: { changes: [], any: true }, version: 1 }),
    cwd: async () => {
      if (failing) throw new Error('no cwd')
      return '/work'
    },
    list: async path => {
      if (path === '/work') return [{ name: 'STDD', kind: 'dir', mtimeMs: 1 }]
      if (path === '/work/STDD') return [{ name: 'checkout', kind: 'dir', mtimeMs: 1 }]
      if (path === '/work/STDD/checkout') {
        return [
          { name: 'spec.md', kind: 'file', mtimeMs: 1 },
          { name: 'tasks.md', kind: 'file', mtimeMs: 2 },
        ]
      }
      return []
    },
    read: async path => path.endsWith('spec.md') ? '---\nstatus: approved\n---\n' : '- [ ] `S-01`\n- [ ] `S-02`\n',
  })
  const later: ProgressSource = {
    onToolCall: async () => undefined,
    lines: async () => { throw new Error('plan source must not be consulted') },
  }

  expect(await orderedLines([stdd, later], io, 80)).toBe(BAND_RETRY)
  failing = false
  const lines = await stdd.lines(io, 80)
  expect(lines).not.toBe(BAND_RETRY)
  expect(lines).not.toBeUndefined()
  expect(lines).not.toBeNull()
})

const toolIo = (overrides: Partial<ProgressToolIo> = {}): ProgressToolIo => ({
  ...readIo(),
  now: async () => 5,
  after: () => undefined,
  invalidate: () => undefined,
  setPlanTasks: async () => ({ isSet: true }) as never,
  setPlanChecklist: async () => ({ isSet: true }) as never,
  setStddTouched: async () => ({ isSet: true }) as never,
  ...overrides,
})

test('a state failure during a tool call leaves the checklist view unset so the next render reloads', async () => {
  let failures = 1
  const getPlanChecklist: ProgressReadIo['getPlanChecklist'] = async () => {
    if (failures > 0) {
      failures -= 1
      throw new Error('state unavailable')
    }
    return { value: { path: '/work/plan.md' }, version: 1 }
  }
  const source = createChecklistSource()

  await source.onToolCall({ tool: 'Bash' }, {}, toolIo({ getPlanChecklist }))
  const lines = await source.lines(readIo({
    getPlanChecklist,
    read: async () => '- [ ] one\n- [ ] two',
  }), 80)

  expect(lines).not.toBeNull()
  expect(lines).not.toBeUndefined()
  expect(JSON.stringify(lines)).toContain('0/2')
})

test('the first draw loads the checklist view even when a task list claims the band', async () => {
  let reads = 0
  const io = readIo({
    getPlanTasks: async () => ({
      value: [{ id: '1', subject: 'work', status: 'pending' }],
      version: 1,
    }),
    getPlanChecklist: async () => ({ value: { path: '/work/plan.md' }, version: 1 }),
    read: async () => {
      reads += 1
      return '- [ ] one\n- [ ] two'
    },
  })
  const sources = [createPlanTasksSource(), createChecklistSource()]

  expect(await orderedLines(sources, io, 80)).not.toBeNull()
  expect(reads).toBe(1)
  await orderedLines(sources, io, 80)
  expect(reads).toBe(1)
})

test('the watched-tool matcher literal lists exactly the tools the sources react to', async () => {
  let matcher: unknown
  const on = ((hook: string, options: { tool?: unknown }) => {
    if (hook === 'tool.call') matcher = options.tool
    return { catch: () => undefined }
  }) as unknown as On
  register(on, { plan_progress: 'on' } as PluginOptions)
  expect(matcher).toBeInstanceOf(RegExp)
  const listed = (matcher as RegExp).source.replace(/^\^\(\?:/, '').replace(/\)\$$/, '').split('|')

  expect([...listed].sort()).toEqual(
    [...new Set<string>([...STDD_TOOLS, ...PLAN_TOOLS, ...CHECKLIST_TOOLS])].sort(),
  )
  expect(listed).toHaveLength(10)
})
