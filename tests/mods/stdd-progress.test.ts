import type { On } from 'claude-code'
import { test, expect, mock } from 'claude-code/testing'

import { register as registerMods } from '../../hooks/mods/register'
import {
  barSegments,
  checklistProgressSegments,
  formatProgress,
  parseMarkdownChecklist,
  parseTasks,
  phaseOf,
  isPlanVisible,
  planProgressSegments,
  pickNewestChange,
  progressSegments,
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

test('progress segments colour phases and preserve the plain formatter', async () => {
  const phases = [
    ['uiux', 'merged'],
    ['spec (draft)', 'warning'],
    ['plan', 'suggestion'],
    ['execute', 'success'],
  ] as const

  for (const [phase, color] of phases) {
    const view = { name: 'checkout-flow', phase, completed: 0, total: 0 }
    const lines = progressSegments(view, 42)
    expect(lines[0]?.[4]).toEqual({ text: phase, color })
    expect(lines.map(line => line.map(segment => segment.text).join(''))).toEqual(formatProgress(view, 42))
  }
})

test('progress bar segments represent completed, wip, complete-edge, and zero-task states', async () => {
  const executing = {
    name: 'checkout-flow',
    phase: 'execute' as const,
    completed: 7,
    total: 12,
  }

  const noWip = progressSegments(executing, 42)[1]
  expect(noWip?.slice(0, 3)).toEqual([
    { text: '▓'.repeat(7), color: 'success' },
    { text: '', color: 'warning' },
    { text: '░'.repeat(5), color: 'inactive' },
  ])

  const withWipView = { ...executing, wip: 'S-03,S-04' }
  const withWip = progressSegments(withWipView, 42)[1]
  expect(withWip?.slice(0, 3)).toEqual([
    { text: '▓'.repeat(7), color: 'success' },
    { text: '▓', color: 'warning' },
    { text: '░'.repeat(4), color: 'inactive' },
  ])
  expect(withWip?.map(segment => segment.text).join('')).toBe(
    '▓▓▓▓▓▓▓▓░░░░ 7/12 tasks · wip S-03,S-04',
  )

  const complete = progressSegments({ ...withWipView, completed: 12 }, 42)[1]
  expect(complete?.slice(0, 3)).toEqual([
    { text: '▓'.repeat(12), color: 'success' },
    { text: '', color: 'warning' },
    { text: '', color: 'inactive' },
  ])

  const zeroView = { ...executing, completed: 0, total: 0 }
  const zero = progressSegments(zeroView, undefined)[1]
  expect(zero?.slice(0, 3)).toEqual([
    { text: '', color: 'success' },
    { text: '', color: 'warning' },
    { text: '░'.repeat(24), color: 'inactive' },
  ])

  for (const view of [executing, withWipView, { ...withWipView, completed: 12 }, zeroView]) {
    expect(progressSegments(view, 42).map(line => line.map(segment => segment.text).join(''))).toEqual(formatProgress(view, 42))
  }
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
    '▓▓▓▓▓▓▓▓░░░░ 7/12 tasks · wip S-03,S-04',
  ])
  expect(formatProgress({ ...executing, completed: 6 }, 100)[1]).toStartWith('▓'.repeat(13) + '░'.repeat(11))
  expect(formatProgress({ ...executing, completed: 0 }, 20)[1]).toStartWith('▓' + '░'.repeat(3))
  expect(formatProgress({ ...executing, completed: 0, total: 0, wip: undefined }, undefined)).toEqual([
    'STDD checkout-flow · execute',
    `${'░'.repeat(24)} 0/0 tasks`,
  ])
  expect(formatProgress({ ...executing, phase: 'plan' }, 42)).toEqual([
    'STDD checkout-flow · plan',
  ])
})

test('progress switches register one shared band only when either feature is on', async () => {
  const registered = (stdd_progress: 'on' | 'off', plan_progress: 'on' | 'off'): string[] => {
    const events: string[] = []
    const on = ((event: string) => {
      events.push(event)
      return { catch: () => undefined }
    }) as never

    registerMods(on, { fellowship: 'off', stdd_progress, plan_progress })
    return events
  }

  expect(registered('off', 'off')).toEqual([])
  expect(registered('on', 'off')).toEqual(['tool.call', 'ui.render'])
  expect(registered('off', 'on')).toEqual(['session.start', 'tool.call', 'tool.call', 'ui.render'])
  expect(registered('on', 'on')).toEqual(['session.start', 'tool.call', 'tool.call', 'ui.render'])
})

test('plan bar segments share sizing, show K/T and one warning cell, and truncate the active label', async () => {
  expect(barSegments({ completed: 2, total: 4, hasInProgress: true }, 42)).toEqual([
    { text: '▓'.repeat(6), color: 'success' },
    { text: '▓', color: 'warning' },
    { text: '░'.repeat(5), color: 'inactive' },
  ])

  const lines = planProgressSegments([
    { id: '1', subject: 'done', status: 'completed' },
    { id: '2', subject: 'fallback', activeForm: 'x'.repeat(70), status: 'in_progress' },
    { id: '3', subject: 'later', status: 'pending' },
  ], 42)
  expect(lines[0]?.map(segment => segment.text).join('')).toBe('Plan · 1/3 tasks')
  expect(lines[1]?.slice(0, 3)).toEqual([
    { text: '▓'.repeat(4), color: 'success' },
    { text: '▓', color: 'warning' },
    { text: '░'.repeat(7), color: 'inactive' },
  ])
  expect(lines[1]?.at(-1)).toEqual({ text: ` · ▶ ${'x'.repeat(59)}…`, color: 'warning' })
})

test('a BOM before the first task line does not hide it', async () => {
  expect(parseTasks('﻿- [x] `S-01`\n- [ ] `S-02`')).toEqual({ completed: 1, total: 2 })
  expect(phaseOf({ spec: '﻿---\nstatus: approved\n---', tasks: '﻿- [ ] `S-01`' })).toBe('execute')
})

test('markdown checklist parsing handles markers, indentation, fences, BOM, and non-checklist lines', async () => {
  const checklist = parseMarkdownChecklist([
    '\uFEFF- [x] **finished**',
    '  * [X] `also finished`',
    '\t+ [ ] _next_ `step`',
    '- [ ] ' + 'x'.repeat(70),
    '- [wip] not a checklist item',
    'plain text',
    '```md',
    '- [ ] hidden backtick item',
    '```',
    '~~~',
    '+ [x] hidden tilde item',
    '~~~',
  ].join('\n'))

  expect(checklist).toEqual({
    completed: 2,
    total: 4,
    next: 'next step',
  })
  expect(parseMarkdownChecklist('- [x] done\n- [ ] ' + 'x'.repeat(70)).next).toBe(`${'x'.repeat(59)}…`)
  expect(parseMarkdownChecklist('- [ ] run_some_code\n- [ ] later').next).toBe('run_some_code')
})

test('checklist plan segments show the basename, item count, next item, and warning cell', async () => {
  const lines = checklistProgressSegments('/work/docs/plan.md', {
    completed: 1,
    total: 3,
    next: 'ship it',
  }, 42)

  expect(lines[0]?.map(segment => segment.text).join('')).toBe('Plan · plan.md · 1/3 items')
  expect(lines[1]?.slice(0, 3)).toEqual([
    { text: '▓'.repeat(4), color: 'success' },
    { text: '▓', color: 'warning' },
    { text: '░'.repeat(7), color: 'inactive' },
  ])
  expect(lines[1]?.at(-1)).toEqual({ text: ' · ▶ ship it', color: 'warning' })
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

type StddChangeDisk = {
  name: string
  mtimeMs: number
  tasks: string
}

const mountChangesDisk = (on: On, changes: readonly StddChangeDisk[]) => {
  const clock = mock.clock(on)
  on('session.cwd', async () => ({ value: '/work' }) as never)
  on('fs.list', async (_$, e) => {
    const path = (e as { path: string }).path
    if (path === '/work') return { value: [{ name: 'STDD', kind: 'dir', mtimeMs: 1 }] } as never
    if (path === '/work/STDD') {
      return { value: changes.map(change => ({ name: change.name, kind: 'dir', mtimeMs: change.mtimeMs })) } as never
    }
    const change = changes.find(candidate => path === `/work/STDD/${candidate.name}`)
    if (change !== undefined) {
      return {
        value: [
          { name: 'spec.md', kind: 'file', mtimeMs: change.mtimeMs - 1 },
          { name: 'tasks.md', kind: 'file', mtimeMs: change.mtimeMs },
        ],
      } as never
    }
    return { value: [] } as never
  })
  on('fs.read', async (_$, e) => {
    const path = (e as { path: string }).path
    if (path.endsWith('/spec.md')) return { value: SPEC } as never
    const change = changes.find(candidate => path === `/work/STDD/${candidate.name}/tasks.md`)
    return { value: change?.tasks ?? '' } as never
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

// The plugin's band draws above whatever the stack beneath it draws, so a mounted band needs a terminal hook.
const mountLowerBand = (on: On, text = ''): void => {
  on('ui.render', ($, e) => {
    const { Text } = $.ui.resolve(e)
    return h(Text, null, text) as never
  })
}

const mountEmptyDisk = (on: On): void => {
  on('session.cwd', async () => ({ value: '/work' }) as never)
  on('fs.list', async () => ({ value: [] }) as never)
}

type ChecklistDisk = {
  files: Record<string, string>
  exitPlanPath?: string
}

const mountChecklistDisk = (on: On, disk: ChecklistDisk, lowerBand = '') => {
  const clock = mock.clock(on)
  on('session.cwd', async () => ({ value: '/work' }) as never)
  on('fs.list', async () => ({ value: [] }) as never)
  on('fs.read', async (_$, e) => ({ value: disk.files[(e as { path: string }).path] ?? '' }) as never)
  on('tool.call', async (_$, e) => {
    if (e.tool === 'Write') {
      if (e.file_path.includes('denied')) return { deny: 'no' } as never
      if (e.file_path.includes('failed')) return { result: 'boom', isError: true } as never
      disk.files[e.file_path] = e.content
    } else if (e.tool === 'Edit') {
      disk.files[e.file_path] = (disk.files[e.file_path] ?? '').replace(e.old_string, e.new_string)
    }
    if (e.tool === 'ExitPlanMode') return { result: { filePath: disk.exitPlanPath } } as never
    return { result: {} } as never
  })
  mountLowerBand(on, lowerBand)
  return clock
}

const mountTaskTools = (on: On): void => {
  let created = 0
  on('tool.call', async (_$, e) => {
    if (e.tool === 'TaskCreate') {
      created += 1
      return { result: { task: { id: String(created), subject: String(e.subject) } } } as never
    }
    return { result: {} } as never
  })
}

test('TodoWrite replaces the plan list and renders its active task', { options: { fellowship: 'off', stdd_progress: 'off', plan_progress: 'on' } }, async ($, on) => {
  mountLowerBand(on)
  mountTaskTools(on)
  await $.tool.call({
    tool: 'TodoWrite',
    todos: [
      { content: 'old done', activeForm: 'Old done', status: 'completed' },
      { content: 'old active', activeForm: 'Working old task', status: 'in_progress' },
    ],
  })
  await $.tool.call({
    tool: 'TodoWrite',
    todos: [{ content: 'new active', activeForm: 'Working new task', status: 'in_progress' }],
  })

  const ui = await $.ui.mount(BAND)
  expect(await bandText(ui as never, /Plan · 0\/1 tasks/)).toBe(true)
  expect(await bandText(ui as never, /▶ Working new task/)).toBe(true)
})

test('TaskCreate and TaskUpdate edit the task plan, ignoring unknown ids and removing deleted tasks', { options: { fellowship: 'off', stdd_progress: 'off', plan_progress: 'on' } }, async ($, on) => {
  mountLowerBand(on)
  mountTaskTools(on)
  await $.tool.call({ tool: 'TaskCreate', subject: 'first', description: '' })
  await $.tool.call({ tool: 'TaskCreate', subject: 'second', description: '', activeForm: 'Working second' })
  await $.tool.call({ tool: 'TaskUpdate', taskId: 'missing', status: 'completed' })
  await $.tool.call({ tool: 'TaskUpdate', taskId: '2', status: 'in_progress', subject: 'second renamed' })
  await $.tool.call({ tool: 'TaskUpdate', taskId: '1', status: 'deleted' })

  const ui = await $.ui.mount(BAND)
  expect(await bandText(ui as never, /Plan · 0\/1 tasks/)).toBe(true)
  expect(await bandText(ui as never, /▶ Working second/)).toBe(true)
})

test('subagent task tool calls do not change the main plan', { options: { fellowship: 'off', stdd_progress: 'off', plan_progress: 'on' } }, async ($, on) => {
  mountLowerBand(on)
  mountTaskTools(on)
  await $.tool.call({
    tool: 'TodoWrite',
    todos: [{ content: 'main', activeForm: 'Working main', status: 'pending' }],
  })
  await $.tool.call({
    tool: 'TodoWrite',
    agentId: 'subagent-1',
    todos: [{ content: 'child', activeForm: 'Working child', status: 'in_progress' }],
  } as never)

  const ui = await $.ui.mount(BAND)
  expect(await bandText(ui as never, /Plan · 0\/1 tasks/)).toBe(true)
  expect(await bandText(ui as never, /Working child/)).toBe(false)
})

test('unfinished STDD progress takes precedence over plan progress', { options: { fellowship: 'off', stdd_progress: 'on', plan_progress: 'on' } }, async ($, on) => {
  mountLowerBand(on)
  mountDisk(on, { tasks: '- [ ] `S-01`\n' })
  mountTaskTools(on)
  await $.tool.call({
    tool: 'TodoWrite',
    todos: [{ content: 'main', activeForm: 'Working main', status: 'in_progress' }],
  })
  await $.tool.call({ tool: 'Edit', file_path: '/work/STDD/checkout/tasks.md' } as never)

  const ui = await $.ui.mount(BAND)
  expect(await bandText(ui as never, /STDD checkout · execute/)).toBe(true)
  expect(await bandText(ui as never, /Plan ·/)).toBe(false)
})

test('an untouched STDD change does not hide this session plan', { options: { fellowship: 'off', stdd_progress: 'on', plan_progress: 'on' } }, async ($, on) => {
  mountLowerBand(on)
  mountDisk(on, { tasks: '- [ ] `S-01`\n' })
  mountTaskTools(on)
  await $.tool.call({
    tool: 'TodoWrite',
    todos: [{ content: 'main', activeForm: 'Working main', status: 'in_progress' }],
  })

  const ui = await $.ui.mount(BAND)
  expect(await bandText(ui as never, /Plan ·/)).toBe(true)
  expect(await bandText(ui as never, /STDD/)).toBe(false)
})

test('editing an STDD change makes it take precedence over this session plan', { options: { fellowship: 'off', stdd_progress: 'on', plan_progress: 'on' } }, async ($, on) => {
  mountLowerBand(on)
  mountDisk(on, { tasks: '- [ ] `S-01`\n' })
  mountTaskTools(on)
  await $.tool.call({
    tool: 'TodoWrite',
    todos: [{ content: 'main', activeForm: 'Working main', status: 'in_progress' }],
  })
  await $.tool.call({ tool: 'Edit', file_path: '/work/STDD/checkout/tasks.md' } as never)

  const ui = await $.ui.mount(BAND)
  expect(await bandText(ui as never, /STDD checkout · execute/)).toBe(true)
  expect(await bandText(ui as never, /Plan ·/)).toBe(false)
})

test('STDD progress shows an older touched change instead of a newer untouched change', { options: { fellowship: 'off', stdd_progress: 'on' } }, async ($, on) => {
  mountLowerBand(on)
  mountChangesDisk(on, [
    { name: 'older-touched', mtimeMs: 10, tasks: '- [ ] `S-01`\n' },
    { name: 'newer-untouched', mtimeMs: 20, tasks: '- [ ] `S-01`\n' },
  ])
  mountTaskTools(on)
  await $.tool.call({ tool: 'Edit', file_path: '/work/STDD/older-touched/tasks.md' } as never)

  const ui = await $.ui.mount(BAND)
  expect(await bandText(ui as never, /STDD older-touched · execute/)).toBe(true)
  expect(await bandText(ui as never, /newer-untouched/)).toBe(false)
})

test('a subagent STDD edit counts as touching that change', { options: { fellowship: 'off', stdd_progress: 'on' } }, async ($, on) => {
  mountLowerBand(on)
  mountDisk(on, { tasks: '- [ ] `S-01`\n' })
  mountTaskTools(on)
  await $.tool.call({
    tool: 'Edit',
    agentId: 'subagent-1',
    file_path: '/work/STDD/checkout/tasks.md',
  } as never)

  const ui = await $.ui.mount(BAND)
  expect(await bandText(ui as never, /STDD checkout · execute/)).toBe(true)
})

test('an STDD skill call without a path shows the newest unfinished change', { options: { fellowship: 'off', stdd_progress: 'on' } }, async ($, on) => {
  mountLowerBand(on)
  mountChangesDisk(on, [
    { name: 'older', mtimeMs: 10, tasks: '- [ ] `S-01`\n' },
    { name: 'newer', mtimeMs: 20, tasks: '- [ ] `S-01`\n' },
  ])
  mountTaskTools(on)
  await $.tool.call({ tool: 'Skill', skill: 'tlor:stdd-execute' } as never)

  const ui = await $.ui.mount(BAND)
  expect(await bandText(ui as never, /STDD newer · execute/)).toBe(true)
  expect(await bandText(ui as never, /STDD older · execute/)).toBe(false)
})

test('plan source priority is task list, then tracked checklist', { options: { fellowship: 'off', stdd_progress: 'off', plan_progress: 'on' } }, async ($, on) => {
  const tracked = '/work/session.md'
  mountChecklistDisk(on, {
    files: {
      [tracked]: '- [ ] tracked next\n- [ ] tracked later',
    },
  })

  await $.tool.call({ tool: 'Write', file_path: tracked, content: '- [ ] tracked next\n- [ ] tracked later' })
  await $.tool.call({
    tool: 'TodoWrite',
    todos: [{ content: 'task source', activeForm: 'Task source wins', status: 'in_progress' }],
  })
  const ui = await $.ui.mount(BAND)
  expect(await bandText(ui as never, /Plan · 0\/1 tasks/)).toBe(true)
  expect(await bandText(ui as never, /session\.md/)).toBe(false)

  await $.tool.call({ tool: 'TodoWrite', todos: [] })
  expect(await bandText(ui as never, /Plan · session\.md · 0\/2 items/)).toBe(true)
})

test('a successful Write tracks a three-item markdown checklist and Edit updates its count', { options: { fellowship: 'off', stdd_progress: 'off', plan_progress: 'on' } }, async ($, on) => {
  const path = '/work/roadmap.md'
  mountChecklistDisk(on, { files: {} })
  await $.tool.call({
    tool: 'Write',
    file_path: path,
    content: '- [x] first\n- [ ] **second**\n- [ ] third',
  })
  const ui = await $.ui.mount(BAND)
  expect(await bandText(ui as never, /Plan · roadmap\.md · 1\/3 items/)).toBe(true)
  expect(await bandText(ui as never, /▶ second/)).toBe(true)

  await $.tool.call({ tool: 'Edit', file_path: path, old_string: '- [ ] **second**', new_string: '- [X] **second**' })
  expect(await bandText(ui as never, /Plan · roadmap\.md · 2\/3 items/)).toBe(true)
  expect(await bandText(ui as never, /▶ third/)).toBe(true)
})

test('Bash re-reads a tracked checklist and a throttled read has a trailing refresh', { options: { fellowship: 'off', stdd_progress: 'off', plan_progress: 'on' } }, async ($, on) => {
  const path = '/work/roadmap.md'
  const disk = { files: { [path]: '- [ ] first\n- [ ] second\n- [ ] third' } }
  const clock = mountChecklistDisk(on, disk)
  await $.tool.call({ tool: 'Write', file_path: path, content: disk.files[path] })
  const ui = await $.ui.mount(BAND)
  expect(await bandText(ui as never, /0\/3 items/)).toBe(true)

  disk.files[path] = '- [x] first\n- [ ] second\n- [ ] third'
  await $.tool.call({ tool: 'Bash', command: 'true', description: 'mutate markdown elsewhere' })
  expect(await bandText(ui as never, /1\/3 items/)).toBe(false)
  await clock.advance(1000)
  expect(await bandText(ui as never, /1\/3 items/)).toBe(true)
})

test('subagent, denied, and too-short markdown writes are not tracked', { options: { fellowship: 'off', stdd_progress: 'off', plan_progress: 'on' } }, async ($, on) => {
  mountChecklistDisk(on, { files: {} })
  await $.tool.call({
    tool: 'Write',
    agentId: 'subagent-1',
    file_path: '/work/subagent.md',
    content: '- [ ] one\n- [ ] two\n- [ ] three',
  } as never)
  await $.tool.call({
    tool: 'Write',
    file_path: '/work/denied.md',
    content: '- [ ] one\n- [ ] two\n- [ ] three',
  }).catch(() => undefined)
  await $.tool.call({ tool: 'Write', file_path: '/work/short.md', content: '- [ ] only one' })

  const ui = await $.ui.mount(BAND)
  expect(await bandText(ui as never, /Plan ·/)).toBe(false)
})

test('a denied Write of an existing checklist file is not tracked', { options: { fellowship: 'off', stdd_progress: 'off', plan_progress: 'on' } }, async ($, on) => {
  mountChecklistDisk(on, { files: { '/work/denied.md': '- [ ] one\n- [ ] two\n- [ ] three' } })
  await $.tool.call({ tool: 'Write', file_path: '/work/denied.md', content: 'x' }).catch(() => undefined)

  const ui = await $.ui.mount(BAND)
  expect(await bandText(ui as never, /Plan ·/)).toBe(false)
})

test('a failed Write of an existing checklist file is not tracked', { options: { fellowship: 'off', stdd_progress: 'off', plan_progress: 'on' } }, async ($, on) => {
  mountChecklistDisk(on, { files: { '/work/failed.md': '- [ ] one\n- [ ] two\n- [ ] three' } })
  await $.tool.call({ tool: 'Write', file_path: '/work/failed.md', content: 'x' }).catch(() => undefined)

  const ui = await $.ui.mount(BAND)
  expect(await bandText(ui as never, /Plan ·/)).toBe(false)
})

test('a tracked file edited down to fewer than two items clears the band', { options: { fellowship: 'off', stdd_progress: 'off', plan_progress: 'on' } }, async ($, on) => {
  const path = '/work/roadmap.md'
  mountChecklistDisk(on, { files: {} })
  await $.tool.call({ tool: 'Write', file_path: path, content: '- [ ] one\n- [ ] two' })
  const ui = await $.ui.mount(BAND)
  expect(await bandText(ui as never, /Plan · roadmap\.md · 0\/2 items/)).toBe(true)

  await $.tool.call({ tool: 'Edit', file_path: path, old_string: '- [ ] two', new_string: 'gone' })
  expect(await bandText(ui as never, /Plan ·/)).toBe(false)
})

test('ExitPlanMode with a plan file path tracks that file like a Write', { options: { fellowship: 'off', stdd_progress: 'off', plan_progress: 'on' } }, async ($, on) => {
  const path = '/plans/session-plan.md'
  mountChecklistDisk(on, {
    files: { [path]: '- [x] one\n- [ ] two\n- [ ] three' },
    exitPlanPath: path,
  })
  await $.tool.call({ tool: 'ExitPlanMode' })

  const ui = await $.ui.mount(BAND)
  expect(await bandText(ui as never, /Plan · session-plan\.md · 1\/3 items/)).toBe(true)
})

test('ExitPlanMode without a plan file path changes nothing', { options: { fellowship: 'off', stdd_progress: 'off', plan_progress: 'on' } }, async ($, on) => {
  mountChecklistDisk(on, { files: {} })
  await $.tool.call({ tool: 'ExitPlanMode' })

  const ui = await $.ui.mount(BAND)
  expect(await bandText(ui as never, /Plan ·/)).toBe(false)
})

test('an all-done chosen checklist remains visible until the default autoclose deadline', { options: { fellowship: 'off', stdd_progress: 'off', plan_progress: 'on' } }, async ($, on) => {
  const tracked = '/work/done.md'
  mountChecklistDisk(on, {
    files: {
      [tracked]: '- [x] one\n- [X] two',
    },
  })
  await $.tool.call({ tool: 'Write', file_path: tracked, content: '- [x] one\n- [X] two' })

  const ui = await $.ui.mount(BAND)
  expect(await bandText(ui as never, /Plan · done\.md · 2\/2 items/)).toBe(true)
})

test('unfinished STDD progress takes precedence over tracked checklists', { options: { fellowship: 'off', stdd_progress: 'on', plan_progress: 'on' } }, async ($, on) => {
  mountLowerBand(on)
  const disk = { tasks: '- [ ] `S-01`\n' }
  mountDisk(on, disk)
  on('env.get', async () => ({ value: '/home/test' }) as never)
  on('tool.call', async () => ({ result: {} }) as never)
  await $.tool.call({
    tool: 'Write',
    file_path: '/work/notes.md',
    content: '- [ ] first\n- [ ] second\n- [ ] third',
  })
  await $.tool.call(stddEdit)

  const ui = await $.ui.mount(BAND)
  expect(await bandText(ui as never, /STDD checkout · execute/)).toBe(true)
  expect(await bandText(ui as never, /Plan ·/)).toBe(false)
})

test('an all-completed or empty plan is hidden', async () => {
  expect(isPlanVisible([])).toBe(false)
  expect(isPlanVisible([{ id: '1', subject: 'done', status: 'completed' }] as never)).toBe(false)
  expect(isPlanVisible([{ id: '1', subject: 'a', status: 'completed' }, { id: '2', subject: 'b', status: 'pending' }] as never)).toBe(true)
})

test('the first AbovePrompt render after an STDD touch scans the disk', { options: { fellowship: 'off', stdd_progress: 'on' } }, async ($, on) => {
  mountLowerBand(on)
  mountDisk(on, { tasks: '- [x] `S-01`\n- [wip] `S-02`\n' })
  mountTaskTools(on)
  await $.tool.call(stddEdit)
  const ui = await $.ui.mount({ ...(BAND as object), plugin: 'tlor' } as never)
  expect(await bandText(ui as never, /STDD checkout · execute/)).toBe(true)
  expect(await bandText(ui as never, /1\/2 tasks · wip S-02/)).toBe(true)
})

test('a BOM on tasks.md still counts its first task in the band', { options: { fellowship: 'off', stdd_progress: 'on' } }, async ($, on) => {
  mountLowerBand(on)
  mountDisk(on, { tasks: '﻿- [x] `S-01`\n- [ ] `S-02`\n' })
  mountTaskTools(on)
  await $.tool.call(stddEdit)
  const ui = await $.ui.mount(BAND)
  expect(await bandText(ui as never, /1\/2 tasks/)).toBe(true)
})

const stddEdit = { tool: 'Edit', file_path: '/work/STDD/checkout/tasks.md', tool_use_id: 'u1' } as never

test('a throttled STDD edit still gets a trailing rescan when the window ends', { options: { fellowship: 'off', stdd_progress: 'on' } }, async ($, on) => {
  mountLowerBand(on)
  const disk = { tasks: '- [ ] `S-01`\n- [ ] `S-02`\n' }
  const clock = mountDisk(on, disk)
  on('tool.call', async () => ({ result: {} }) as never)
  await $.tool.call(stddEdit)
  await clock.advance(1000)
  const ui = await $.ui.mount(BAND)
  expect(await bandText(ui as never, /0\/2 tasks/)).toBe(true)

  await $.tool.call(stddEdit) // the throttle window has elapsed, so this scan runs at once
  disk.tasks = '- [x] `S-01`\n- [ ] `S-02`\n'
  await $.tool.call(stddEdit) // inside the 1 s window: skipped, trailing rescan queued
  expect(await bandText(ui as never, /1\/2 tasks/)).toBe(false)
  await clock.advance(1000)
  expect(await bandText(ui as never, /1\/2 tasks/)).toBe(true)
})

test('a denied or failed task call leaves the plan unchanged', { options: { fellowship: 'off', stdd_progress: 'off', plan_progress: 'on' } }, async ($, on) => {
  mountLowerBand(on)
  on('tool.call', async (_$, e) => {
    const todos = (e as { todos?: Array<{ content: string }> }).todos ?? []
    if (todos.some(todo => todo.content === 'denied')) return { deny: 'no' } as never
    if (todos.some(todo => todo.content === 'failed')) return { result: 'boom', isError: true } as never
    return { result: {} } as never
  })
  await $.tool.call({ tool: 'TodoWrite', todos: [{ content: 'kept', activeForm: 'Keeping', status: 'in_progress' }] })
  await $.tool.call({ tool: 'TodoWrite', todos: [{ content: 'denied', activeForm: 'Denied', status: 'pending' }] }).catch(() => undefined)
  await $.tool.call({ tool: 'TodoWrite', todos: [{ content: 'failed', activeForm: 'Failed', status: 'pending' }] }).catch(() => undefined)

  const ui = await $.ui.mount(BAND)
  expect(await bandText(ui as never, /▶ Keeping/)).toBe(true)
})

test('the plan band stacks above a lower AbovePrompt hook instead of hiding it', { options: { fellowship: 'off', stdd_progress: 'off', plan_progress: 'on' } }, async ($, on) => {
  const path = '/work/roadmap.md'
  const content = '- [x] one\n- [ ] two\n- [ ] three'
  mountChecklistDisk(on, { files: { [path]: content } }, 'LOWER-BAND-MARKER')
  await $.tool.call({ tool: 'Write', file_path: path, content })

  const ui = await $.ui.mount(BAND)
  expect(await bandText(ui as never, /Plan · roadmap\.md · 1\/3 items/)).toBe(true)
  expect(await bandText(ui as never, /LOWER-BAND-MARKER/)).toBe(true)
})

test('a lower AbovePrompt hook still draws when the plan band has nothing to show', { options: { fellowship: 'off', stdd_progress: 'off', plan_progress: 'on' } }, async ($, on) => {
  mountChecklistDisk(on, { files: {} }, 'LOWER-BAND-MARKER')

  const ui = await $.ui.mount(BAND)
  expect(await bandText(ui as never, /Plan ·/)).toBe(false)
  expect(await bandText(ui as never, /LOWER-BAND-MARKER/)).toBe(true)
})

const LOWER_PLAN_ROW = 'Plan · x.md · 1/2 items'

test('the plan band is skipped when a lower band already draws a Plan row', { options: { fellowship: 'off', stdd_progress: 'off', plan_progress: 'on' } }, async ($, on) => {
  const path = '/work/roadmap.md'
  const content = '- [x] one\n- [ ] two'
  mountChecklistDisk(on, { files: { [path]: content } }, LOWER_PLAN_ROW)
  await $.tool.call({ tool: 'Write', file_path: path, content })

  const ui = await $.ui.mount(BAND)
  expect(await (ui as never as { findAll: (q: { type: string; text: RegExp }) => Promise<unknown[]> }).findAll({ type: 'Text', text: /^Plan · / })).toHaveLength(1)
  expect(await bandText(ui as never, /Plan · x\.md · 1\/2 items/)).toBe(true)
})

test('a touched STDD change still draws above a lower Plan row', { options: { fellowship: 'off', stdd_progress: 'on', plan_progress: 'on' } }, async ($, on) => {
  mountLowerBand(on, LOWER_PLAN_ROW)
  mountDisk(on, { tasks: '- [ ] `S-01`\n' })
  mountTaskTools(on)
  await $.tool.call({ tool: 'Edit', file_path: '/work/STDD/checkout/tasks.md' } as never)

  const ui = await $.ui.mount(BAND)
  expect(await bandText(ui as never, /STDD checkout · execute/)).toBe(true)
  expect(await bandText(ui as never, /Plan · x\.md · 1\/2 items/)).toBe(true)
})

const PLAN_TRACK = 'mcp__tlor__PlanTrack'

test('PlanTrack declared ledger renders completed tasks', { options: { fellowship: 'off', stdd_progress: 'off', plan_progress: 'on' } }, async ($, on) => {
  const plan = '/work/plans/session.md'
  const ledger = '/work/.superpowers/sdd/session/progress.md'
  mountChecklistDisk(on, {
    files: {
      [plan]: '### Task 1: first\n### Task 2: second\n### Task 3: third',
      [ledger]: 'Task 1: complete\n',
    },
  })

  const answer = await $.tool.call({ tool: PLAN_TRACK, plan, progress: 'ledger', ledger } as never)
  expect(answer.result).toBe('Tracking session.md from progress.md.')
  const ui = await $.ui.mount(BAND)
  expect(await bandText(ui as never, /Plan · session\.md · 1\/3 tasks/)).toBe(true)
})

test('PlanTrack checklist remembers a completed step after the plan is rewritten', { options: { fellowship: 'off', stdd_progress: 'off', plan_progress: 'on' } }, async ($, on) => {
  const plan = '/work/plans/session.md'
  const disk = { files: { [plan]: '- [x] first\n- [ ] second' } }
  mountChecklistDisk(on, disk)
  await $.tool.call({ tool: PLAN_TRACK, plan, progress: 'checklist' } as never)

  const ui = await $.ui.mount(BAND)
  expect(await bandText(ui as never, /Plan · session\.md · 1\/2 items/)).toBe(true)
  await $.tool.call({
    tool: 'Write',
    file_path: plan,
    content: '- [ ] first\n- [ ] second\n- [ ] third',
  })
  expect(await bandText(ui as never, /Plan · session\.md · 1\/3 items/)).toBe(true)
})

test('Bash progress ledger detection uses the known plan pointer', { options: { fellowship: 'off', stdd_progress: 'off', plan_progress: 'on' } }, async ($, on) => {
  const plan = '/work/plans/session.md'
  const ledger = '/work/.superpowers/sdd/session/progress.md'
  const disk = {
    files: {
      [plan]: '### Task 1: first\n### Task 2: second\n### Task 3: third\n\n- [ ] keep plan pointer\n- [ ] second pointer item',
      [ledger]: 'Task 1: complete\n',
    },
  }
  mountChecklistDisk(on, disk)
  await $.tool.call({ tool: 'Write', file_path: plan, content: disk.files[plan] })
  await $.tool.call({
    tool: 'Bash',
    command: 'echo "Task 1: complete" >> .superpowers/sdd/session/progress.md',
  })

  const ui = await $.ui.mount(BAND)
  expect(await bandText(ui as never, /Plan · session\.md · 1\/3 tasks/)).toBe(true)
})

test('a touched STDD change wins over a declared plan', { options: { fellowship: 'off', stdd_progress: 'on', plan_progress: 'on' } }, async ($, on) => {
  const plan = '/work/plans/session.md'
  const ledger = '/work/.superpowers/sdd/session/progress.md'
  const files: Record<string, string> = {
    '/work/STDD/checkout/spec.md': SPEC,
    '/work/STDD/checkout/tasks.md': '- [ ] `S-01`\n',
    [plan]: '### Task 1: first\n### Task 2: second',
    [ledger]: 'Task 1: complete\n',
  }
  mock.clock(on)
  on('session.cwd', async () => ({ value: '/work' }) as never)
  on('fs.list', async (_$, e) => {
    const path = (e as { path: string }).path
    if (path === '/work') return { value: [{ name: 'STDD', kind: 'dir', mtimeMs: 1 }] } as never
    if (path === '/work/STDD') return { value: [{ name: 'checkout', kind: 'dir', mtimeMs: 1 }] } as never
    if (path === '/work/STDD/checkout') return { value: [
      { name: 'spec.md', kind: 'file', mtimeMs: 1 },
      { name: 'tasks.md', kind: 'file', mtimeMs: 2 },
    ] } as never
    return { value: [] } as never
  })
  on('fs.read', async (_$, e) => ({ value: files[(e as { path: string }).path] ?? '' }) as never)
  on('tool.call', async () => ({ result: {} }) as never)
  mountLowerBand(on)
  await $.tool.call({ tool: PLAN_TRACK, plan, progress: 'ledger', ledger } as never)
  await $.tool.call({ tool: 'Edit', file_path: '/work/STDD/checkout/tasks.md' } as never)

  const ui = await $.ui.mount(BAND)
  expect(await bandText(ui as never, /STDD checkout · execute/)).toBe(true)
  expect(await bandText(ui as never, /Plan · session\.md/)).toBe(false)
})

test('a lower Plan row suppresses a declared plan row', { options: { fellowship: 'off', stdd_progress: 'off', plan_progress: 'on' } }, async ($, on) => {
  const plan = '/work/plans/session.md'
  const ledger = '/work/.superpowers/sdd/session/progress.md'
  mountChecklistDisk(on, {
    files: {
      [plan]: '### Task 1: first\n### Task 2: second',
      [ledger]: 'Task 1: complete\n',
    },
  }, LOWER_PLAN_ROW)
  await $.tool.call({ tool: PLAN_TRACK, plan, progress: 'ledger', ledger } as never)

  const ui = await $.ui.mount(BAND)
  expect(await (ui as never as { findAll: (q: { type: string; text: RegExp }) => Promise<unknown[]> }).findAll({ type: 'Text', text: /^Plan · / })).toHaveLength(1)
  expect(await bandText(ui as never, /Plan · x\.md · 1\/2 items/)).toBe(true)
})

test('PlanTrack rejects ledger mode without a ledger and does not write state', { options: { fellowship: 'off', stdd_progress: 'off', plan_progress: 'on' } }, async ($, on) => {
  const plan = '/work/plans/session.md'
  mountChecklistDisk(on, { files: { [plan]: '### Task 1: first\n### Task 2: second', '/work/.superpowers/sdd/session/progress.md': 'Task 1: complete\n' } })
  const answer = await $.tool.call({ tool: PLAN_TRACK, plan, progress: 'ledger' } as never)

  expect(answer.isError).toBe(true)
  expect(answer.text).toMatch(/ledger/i)
  // A saved declaration would draw the plan; nothing drawn means nothing was written.
  const ui = await $.ui.mount(BAND)
  expect(await bandText(ui as never, /^Plan · /)).toBe(false)
})

const exitPlan = async ($: { tool: { call: (input: never) => Promise<unknown> } }, on: On) => {
  on('tool.call', async () => ({ result: { filePath: '/plans/session.md' } }) as never)
  mountLowerBand(on)
  return await $.tool.call({ tool: 'ExitPlanMode' } as never) as { context?: string[] }
}

test('plan_reminder off drops the reminder while the plan band still draws', { options: { fellowship: 'off', stdd_progress: 'off', plan_progress: 'on', plan_reminder: 'off' } }, async ($, on) => {
  const result = await exitPlan($ as never, on)
  expect(result.context ?? []).toEqual([])

  await $.tool.call({ tool: 'TodoWrite', todos: [{ content: 'main', activeForm: 'Working main', status: 'in_progress' }] })
  const ui = await $.ui.mount(BAND)
  expect(await bandText(ui as never, /Plan · 0\/1 tasks/)).toBe(true)
})

test('plan_reminder on adds the reminder even when the plan band is off', { options: { fellowship: 'off', stdd_progress: 'off', plan_progress: 'off', plan_reminder: 'on' } }, async ($, on) => {
  const result = await exitPlan($ as never, on)
  expect(result.context?.some(text => text.includes('/plans/session.md') && text.includes('- [x]'))).toBe(true)
})
