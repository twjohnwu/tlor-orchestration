type PlanReminderEvent = Readonly<{
  tool: unknown
  agentId?: unknown
}>

type PlanReminderResult = Readonly<{
  deny?: unknown
  result?: unknown
  context?: readonly string[]
  isError?: unknown
}>

export const addPlanReminder = <T extends PlanReminderResult>(
  event: PlanReminderEvent,
  result: T,
  reminderEnabled: boolean,
): T => {
  if (!reminderEnabled || event.tool !== 'ExitPlanMode' || event.agentId !== undefined) return result
  if (result.deny !== undefined || result.isError !== undefined) return result
  if (typeof result.result !== 'object' || result.result === null) return result

  const filePath = (result.result as Readonly<Record<string, unknown>>).filePath
  if (typeof filePath !== 'string') return result

  // Another plugin's hook may already have asked for the same file to be tracked.
  if (result.context?.some(text => text.includes(filePath) && text.includes('- [x]'))) return result

  const reminder = `Track this plan's progress in the plan file at ${filePath}: if it has no \`- [ ]\` step list, add one (one line per step); tick each step \`- [x]\` right after it is done.`

  return {
    ...result,
    context: [...(result.context ?? []), reminder],
  }
}
