import { expect, test } from 'claude-code/testing'

import {
  isPlanTaskStatus,
  isStddEdit,
  normalizedPath,
  taskCreateId,
  updatedPlanTasks,
} from '../../hooks/mods/stdd-progress/progress'
import { renderedTextLines } from '../../hooks/mods/stdd-progress/renderText'
import { addPlanReminder } from '../../hooks/mods/stdd-progress/planReminder'

const PLAN_REMINDER = "Track this plan's progress in the plan file at /plans/session.md: if it has no `- [ ]` step list, add one (one line per step); tick each step `- [x]` right after it is done."

test('plan reminder is appended to successful main-session ExitPlanMode results', async () => {
  const result = {
    result: { filePath: '/plans/session.md' },
    context: ['existing context'],
    ref: 42,
    text: 'approved',
  }

  expect(addPlanReminder({ tool: 'ExitPlanMode' }, result, true)).toEqual({
    ...result,
    context: ['existing context', PLAN_REMINDER],
  })
})

test('plan reminder leaves ineligible results unchanged by identity', async () => {
  const cases = [
    { enabled: false, event: { tool: 'ExitPlanMode' }, result: { result: { filePath: '/plans/session.md' } } },
    { enabled: true, event: { tool: 'ExitPlanMode', agentId: 'agent-1' }, result: { result: { filePath: '/plans/session.md' } } },
    { enabled: true, event: { tool: 'ExitPlanMode' }, result: { deny: 'not approved' } },
    { enabled: true, event: { tool: 'ExitPlanMode' }, result: { result: { filePath: '/plans/session.md' }, isError: true } },
  ]

  for (const one of cases) {
    expect(addPlanReminder(one.event, one.result, one.enabled)).toBe(one.result)
  }
})

test('taskCreateId reads structured and text task ids in priority order', async () => {
  expect(taskCreateId({ result: { task: { id: 7 }, taskId: 'lower' } })).toBe('7')
  expect(taskCreateId({ result: { taskId: 'task-id' } })).toBe('task-id')
  expect(taskCreateId({ result: { id: 9 } })).toBe('9')
  expect(taskCreateId({ text: 'Created task #abc_12' })).toBe('abc_12')
  expect(taskCreateId({ text: 'Created Task fallback-3' })).toBe('fallback-3')
  expect(taskCreateId(null)).toBeUndefined()
})

test('updatedPlanTasks replaces todos and creates, updates, and deletes tasks', async () => {
  expect(updatedPlanTasks([], {
    tool: 'TodoWrite',
    todos: [
      { content: 'valid', activeForm: 'Working', status: 'in_progress' },
      { content: 'ignored', status: 'deleted' },
    ],
  }, {}, () => 'unused')).toEqual([
    { id: 'todo:0', subject: 'valid', activeForm: 'Working', status: 'in_progress' },
  ])

  const created = updatedPlanTasks([], { tool: 'TaskCreate', subject: 'new' }, {}, () => 'synthetic:1')
  expect(created).toEqual([{ id: 'synthetic:1', subject: 'new', status: 'pending' }])
  expect(updatedPlanTasks(created ?? [], {
    tool: 'TaskUpdate', taskId: 'synthetic:1', subject: 'renamed', status: 'completed',
  }, {}, () => 'unused')).toEqual([{ id: 'synthetic:1', subject: 'renamed', status: 'completed' }])
  expect(updatedPlanTasks(created ?? [], {
    tool: 'TaskUpdate', taskId: 'synthetic:1', status: 'deleted',
  }, {}, () => 'unused')).toEqual([])
  expect(updatedPlanTasks(created ?? [], {
    tool: 'TaskUpdate', taskId: 'missing', status: 'completed',
  }, {}, () => 'unused')).toBeNull()
})

test('STDD edit detection handles edit paths, notebook paths, and Bash', async () => {
  expect(isStddEdit({ tool: 'Edit', file_path: '/work/STDD/change/tasks.md' })).toBe(true)
  expect(isStddEdit({ tool: 'NotebookEdit', notebook_path: 'C:\\work\\STDD\\change\\notes.ipynb' })).toBe(true)
  expect(isStddEdit({ tool: 'Write', file_path: '/work/docs/tasks.md' })).toBe(false)
  expect(isStddEdit({ tool: 'TaskUpdate' })).toBe(false)
  expect(isStddEdit({ tool: 'Bash' })).toBe(true)
})

test('path normalization and the plan status guard preserve their literal rules', async () => {
  expect(normalizedPath('C:\\work\\plan.md///')).toBe('C:/work/plan.md')
  expect(isPlanTaskStatus('pending')).toBe(true)
  expect(isPlanTaskStatus('in_progress')).toBe(true)
  expect(isPlanTaskStatus('completed')).toBe(true)
  expect(isPlanTaskStatus('deleted')).toBe(false)
})

test('renderedTextLines collects one line per Text across strings, arrays, nesting, and empty values', async () => {
  const text = (...children: unknown[]) => ({ type: 'Text', children })
  const tree = {
    type: 'Box',
    children: [
      text('Plan', ' · ', 'x.md'),
      [text(text('nested '), 'line'), null, undefined, false, true],
      'bare string',
      { type: 'Box', children: [text('deep')] },
    ],
  }

  expect(renderedTextLines(tree as never)).toEqual(['Plan · x.md', 'nested line', 'bare string', 'deep'])
  expect(renderedTextLines('solo')).toEqual(['solo'])
  expect(renderedTextLines([null, undefined, false, 7 as never])).toEqual(['7'])
  expect(renderedTextLines(null)).toEqual([])
  expect(renderedTextLines({ type: 'Text', props: { children: 'via props' } } as never)).toEqual(['via props'])
})

test('plan reminder is not added again when a context string already tracks the same file', async () => {
  const lower = 'Update /plans/session.md and tick each step `- [x]` when done.'
  const result = { result: { filePath: '/plans/session.md' }, context: [lower] }

  expect(addPlanReminder({ tool: 'ExitPlanMode' }, result, true)).toBe(result)
})

test('plan reminder is still added when the existing context names another file or lacks the tick form', async () => {
  const otherFile = { result: { filePath: '/plans/session.md' }, context: ['Track /plans/other.md with `- [x]`'] }
  const noTick = { result: { filePath: '/plans/session.md' }, context: ['See /plans/session.md'] }

  expect(addPlanReminder({ tool: 'ExitPlanMode' }, otherFile, true).context).toEqual([...otherFile.context, PLAN_REMINDER])
  expect(addPlanReminder({ tool: 'ExitPlanMode' }, noTick, true).context).toEqual([...noTick.context, PLAN_REMINDER])
})
