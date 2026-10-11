import type { On, PluginOptions } from 'claude-code'

import { createChecklistSource } from './sources/checklist'
import { createPlanTasksSource } from './sources/planTasks'
import { BAND_RETRY, orderedLines } from './sources/source'
import type { ProgressReadIo, ProgressSource, ProgressToolIo } from './sources/source'
import { createStddSource } from './sources/stdd'

const PLAN_TASKS = { plugin: 'tlor', key: 'planTasks' } as const
const PLAN_CHECKLIST = { plugin: 'tlor', key: 'planChecklist' } as const

export const register = (on: On, options: PluginOptions): void => {
  const stddEnabled = options.stdd_progress !== 'off'
  const planEnabled = options.plan_progress === 'on'
  // A fourth source needs its file, one entry here, its feature switch, and any
  // state key or io method it uses added to ProgressReadIo/ProgressToolIo in
  // sources/source.ts and wired in the two io objects below.
  const sources: ProgressSource[] = [
    ...(stddEnabled ? [createStddSource()] : []),
    ...(planEnabled ? [createPlanTasksSource(), createChecklistSource()] : []),
  ]

  // The matcher is a literal so `claude plugin validate` can print it; it must list every tool
  // any source reacts to (a test pins it to the union of the tool lists in progress.ts).
  on('tool.call', { tool: /^(?:Bash|Edit|Write|MultiEdit|NotebookEdit|TodoWrite|TaskCreate|TaskUpdate|ExitPlanMode)$/ }, async ($, e, next) => {
    const result = await next(e)
    const io: ProgressToolIo = {
      now: () => $.clock.now(),
      after: (ms, fn) => { $.clock.after(ms, fn) },
      read: path => $.fs.read(path),
      list: path => $.fs.list(path),
      cwd: () => $.session.cwd(),
      invalidate: () => $.ui.invalidate('ui.render'),
      getPlanTasks: () => $.state.get(PLAN_TASKS),
      setPlanTasks: (value, version) => $.state.set(PLAN_TASKS, value, { ifVersion: version }),
      getPlanChecklist: () => $.state.get(PLAN_CHECKLIST),
      setPlanChecklist: (value, version) => $.state.set(PLAN_CHECKLIST, value, { ifVersion: version }),
    }
    const event = e as unknown as Readonly<Record<string, unknown>>
    for (const source of sources) {
      try {
        await source.onToolCall(event, result, io)
      } catch {
        // Progress is observational; a source failure never affects a tool call.
      }
    }

    return result
  }).catch(($, e, next) => next(e))

  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    if (e.props.hasSurvey) return next(e)

    try {
      const io: ProgressReadIo = {
        read: path => $.fs.read(path),
        list: path => $.fs.list(path),
        cwd: () => $.session.cwd(),
        getPlanTasks: () => $.state.get(PLAN_TASKS),
        getPlanChecklist: () => $.state.get(PLAN_CHECKLIST),
      }
      const lines = await orderedLines(sources, io, e.viewport?.columns)
      if (lines !== undefined && lines !== null && lines !== BAND_RETRY) {
        const { Box, Text } = $.ui.resolve(e)

        return (
          <Box flexDirection="column">
            {lines.map(line => (
              <Text>
                {line.map(segment => (
                  <Text color={segment.color} bold={segment.bold} dimColor={segment.dim}>{segment.text}</Text>
                ))}
              </Text>
            ))}
          </Box>
        )
      }
    } catch {
      // Missing or unreadable progress never takes over the prompt band.
    }

    return next(e)
  })
}
