import { expect, test } from 'claude-code/testing'

import {
  isPlanTaskStatus,
  isStddEdit,
  normalizedPath,
  taskCreateId,
  updatedPlanTasks,
} from '../../hooks/mods/stdd-progress/progress'

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
