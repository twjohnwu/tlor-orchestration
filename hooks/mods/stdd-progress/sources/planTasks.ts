import { casUpdate } from '../../state'
import { PLAN_TOOLS, isPlanVisible, planProgressSegments, updatedPlanTasks } from '../progress'
import { succeeded } from '../shared'
import type { ProgressSource } from './source'

export const createPlanTasksSource = (): ProgressSource => {
  let syntheticTaskId = 0

  return {
    onToolCall: async (event, result, io) => {
      if (
        event.agentId !== undefined ||
        !PLAN_TOOLS.some(name => name === event.tool) ||
        !succeeded(result)
      ) return

      await casUpdate(
        io.getPlanTasks,
        io.setPlanTasks,
        value => {
          const tasks = updatedPlanTasks(value ?? [], event, result, () => {
            syntheticTaskId += 1
            return `synthetic:${syntheticTaskId}`
          })

          return tasks === null ? null : { value: tasks }
        },
      )
    },
    lines: async (io, columns) => {
      const { value: tasks = [] } = await io.getPlanTasks()
      if (tasks.length === 0) return undefined
      return isPlanVisible(tasks) ? planProgressSegments(tasks, columns) : null
    },
  }
}
