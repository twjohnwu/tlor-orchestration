import type { On } from 'claude-code'
import { test, expect, mock } from 'claude-code/testing'

import { register as registerMods } from '../../hooks/mods/register'
import {
  formatProgress,
  parseTasks,
  phaseOf,
  pickNewestChange,
} from '../../hooks/mods/stdd-progress/progress'

test('task parsing mirrors formal task lines and fenced-code handling', async () => {
  const tasks = parseTasks([
    '- [x] `S-01`',
    '- [ ] `S-02`',
    '- [wip] `S-03,S-04` `[INFRA]` trailing prose',
    '- [x] `S-05` `[MANUAL]`',
    '  - [x] `S-06`',
    '- [X] `S-07`',
    '```md',
    '- [wip] `S-08`',
    '```',
  ].join('\n'))

  expect(tasks).toEqual({ completed: 1, total: 3, wip: 'S-03,S-04' })
})

test('phaseOf covers uiux, draft spec, plan, execute, and done', async () => {
  expect(phaseOf({ designUx: '# UX' })).toBe('uiux')
  expect(phaseOf({ spec: '---\nstatus: draft\n---\n# Spec' })).toBe('spec (draft)')
  expect(phaseOf({ spec: '---\nstatus: approved\n---' })).toBe('plan')
  expect(phaseOf({
    spec: '---\nstatus: approved\n---',
    tasks: '- [x] `S-01`\n- [wip] `S-02`',
  })).toBe('execute')
  expect(phaseOf({
    spec: '---\nstatus: approved\n---',
    tasks: '- [x] `S-01`\n- [x] `S-02` `[INFRA]`\n- [x] `S-03` `[MANUAL]`',
  })).toBe('done')
  expect(phaseOf({ spec: 'status: approved' })).toBe('spec (draft)')
})

test('newest-change selection skips completed changes and empty directories', async () => {
  const selected = pickNewestChange([
    {
      name: 'older-active',
      mtimeMs: 20,
      files: {
        spec: '---\nstatus: approved\n---',
        tasks: '- [x] `S-01`\n- [wip] `S-02`',
      },
    },
    {
      name: 'newest-done',
      mtimeMs: 30,
      files: {
        spec: '---\nstatus: approved\n---',
        tasks: '- [x] `S-01`',
      },
    },
    { name: 'ignored-empty', mtimeMs: 40, files: {} },
  ])

  expect(selected).toEqual({
    name: 'older-active',
    phase: 'execute',
    completed: 1,
    total: 2,
    wip: 'S-02',
  })
})

test('progress formatting sizes the bar and handles zero tasks', async () => {
  const executing = {
    name: 'checkout-flow',
    phase: 'execute' as const,
    completed: 7,
    total: 12,
    wip: 'S-03,S-04',
  }

  expect(formatProgress(executing, 42)).toEqual([
    'STDD checkout-flow · execute',
    '▓▓▓▓▓▓▓░░░░░ 7/12 tasks · wip S-03,S-04',
  ])
  expect(formatProgress({ ...executing, completed: 6 }, 100)[1]).toStartWith('▓'.repeat(12) + '░'.repeat(12))
  expect(formatProgress({ ...executing, completed: 0 }, 20)[1]).toStartWith('░'.repeat(4))
  expect(formatProgress({ ...executing, completed: 0, total: 0, wip: undefined }, undefined)).toEqual([
    'STDD checkout-flow · execute',
    `${'░'.repeat(24)} 0/0 tasks`,
  ])
  expect(formatProgress({ ...executing, phase: 'plan' }, 42)).toEqual([
    'STDD checkout-flow · plan',
  ])
})

test('stdd_progress off registers no STDD hooks', { options: { fellowship: 'off', stdd_progress: 'off' } }, async () => {
  const events: string[] = []
  const on = ((event: string) => {
    events.push(event)
    return { catch: () => undefined }
  }) as never

  registerMods(on, { fellowship: 'off', stdd_progress: 'off' })
  expect(events).toEqual([])
})

test('a BOM before the first task line does not hide it', async () => {
  expect(parseTasks('﻿- [x] `S-01`\n- [ ] `S-02`')).toEqual({ completed: 1, total: 2 })
  expect(phaseOf({ spec: '﻿---\nstatus: approved\n---', tasks: '﻿- [ ] `S-01`' })).toBe('execute')
})

const SPEC = '---\nstatus: approved\n---\n'

// A fake disk: /work/STDD/checkout holds spec.md and tasks.md; `tasks` is read live so a test can change it.
const mountDisk = (on: On, disk: { tasks: string }) => {
  const clock = mock.clock(on)
  on('session.cwd', async () => ({ value: '/work' }) as never)
  on('fs.list', async (_$, e) => {
    const path = (e as { path: string }).path
    if (path === '/work') return { value: [{ name: 'STDD', kind: 'dir', mtimeMs: 1 }] } as never
    if (path === '/work/STDD') return { value: [{ name: 'checkout', kind: 'dir', mtimeMs: 1 }] } as never
    if (path === '/work/STDD/checkout') {
      return {
        value: [
          { name: 'spec.md', kind: 'file', mtimeMs: 1 },
          { name: 'tasks.md', kind: 'file', mtimeMs: 2 },
        ],
      } as never
    }
    return { value: [] } as never
  })
  on('fs.read', async (_$, e) => {
    return { value: (e as { path: string }).path.endsWith('spec.md') ? SPEC : disk.tasks } as never
  })

  return clock
}

const BAND = {
  plugin: 'tlor',
  surface: 'terminal',
  component: 'AbovePrompt',
  props: { hasSurvey: false },
  viewport: { columns: 80, rows: 24 },
} as never

const bandText = async (ui: { find: (q: { type: string; text: RegExp }) => Promise<unknown> }, text: RegExp): Promise<boolean> => {
  return (await ui.find({ type: 'Text', text })) !== undefined
}

test('the first AbovePrompt render scans the disk without writing state', { options: { fellowship: 'off', stdd_progress: 'on' } }, async ($, on) => {
  mountDisk(on, { tasks: '- [x] `S-01`\n- [wip] `S-02`\n' })
  const ui = await $.ui.mount({ ...(BAND as object), plugin: 'tlor' } as never)
  expect(await bandText(ui as never, /STDD checkout · execute/)).toBe(true)
  expect(await bandText(ui as never, /1\/2 tasks · wip S-02/)).toBe(true)
})

test('a BOM on tasks.md still counts its first task in the band', { options: { fellowship: 'off', stdd_progress: 'on' } }, async ($, on) => {
  mountDisk(on, { tasks: '﻿- [x] `S-01`\n- [ ] `S-02`\n' })
  const ui = await $.ui.mount(BAND)
  expect(await bandText(ui as never, /1\/2 tasks/)).toBe(true)
})

const stddEdit = { tool: 'Edit', file_path: '/work/STDD/checkout/tasks.md', tool_use_id: 'u1' } as never

test('a throttled STDD edit still gets a trailing rescan when the window ends', { options: { fellowship: 'off', stdd_progress: 'on' } }, async ($, on) => {
  const disk = { tasks: '- [ ] `S-01`\n- [ ] `S-02`\n' }
  const clock = mountDisk(on, disk)
  on('tool.call', async () => ({ result: {} }) as never)
  const ui = await $.ui.mount(BAND)
  expect(await bandText(ui as never, /0\/2 tasks/)).toBe(true)

  await $.tool.call(stddEdit) // first scan runs at once
  disk.tasks = '- [x] `S-01`\n- [ ] `S-02`\n'
  await $.tool.call(stddEdit) // inside the 1 s window: skipped, trailing rescan queued
  expect(await bandText(ui as never, /1\/2 tasks/)).toBe(false)
  await clock.advance(1000)
  expect(await bandText(ui as never, /1\/2 tasks/)).toBe(true)
})
