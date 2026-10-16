import { casUpdate } from '../../state'
import { PLAN_TOOLS, isPlanVisible, planProgressSegments, updatedPlanTasks } from '../progress'
import { createPlanCompletion } from '../planCompletion'
import { succeeded } from '../shared'
import type { ProgressSource } from './source'

export const createPlanTasksSource = (autocloseSeconds = -1): ProgressSource => {
  let syntheticTaskId = 0
  const completion = createPlanCompletion(autocloseSeconds)

  return {
    id: 'planTasks',
    onToolCall: async (event, result, io) => {
      if (
        event.agentId !== undefined ||
        !PLAN_TOOLS.some(name => name === event.tool) ||
        !succeeded(result)
      ) return

      let updated: ReturnType<typeof updatedPlanTasks> = null
      const didUpdate = await casUpdate(
        io.getPlanTasks,
        io.setPlanTasks,
        value => {
          const tasks = updatedPlanTasks(value ?? [], event, result, () => {
            syntheticTaskId += 1
            return `synthetic:${syntheticTaskId}`
          })

          updated = tasks
          return tasks === null ? null : { value: tasks }
        },
      )
      if (didUpdate && updated !== null) {
        await completion.observe(
          updated.length === 0 ? undefined : 'tasks',
          updated.length > 0 && !isPlanVisible(updated),
          io,
        )
      }
    },
    lines: async (io, columns) => {
      const { value: tasks = [] } = await io.getPlanTasks()
      if (tasks.length === 0) {
        await completion.observe(undefined, false, io)
        return undefined
      }
      if (isPlanVisible(tasks)) {
        await completion.observe('tasks', false, io)
        return planProgressSegments(tasks, columns)
      }
      return await completion.observe('tasks', true, io) ? planProgressSegments(tasks, columns) : null
    },
  }
}
