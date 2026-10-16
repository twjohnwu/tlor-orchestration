import type { On, PluginOptions } from 'claude-code'

import { notify, notifyMode } from '../notify'
import { parsePlanAutoclose } from './planCompletion'
import { createChecklistSource } from './sources/checklist'
import { createPlanTasksSource } from './sources/planTasks'
import { BAND_RETRY, orderedSourceLines } from './sources/source'
import type { ProgressReadIo, ProgressSource, ProgressToolIo } from './sources/source'
import { createStddSource } from './sources/stdd'
import { addPlanReminder } from './planReminder'
import { renderedTextLines } from './renderText'

const PLAN_TASKS = { plugin: 'tlor', key: 'planTasks' } as const
const PLAN_CHECKLIST = { plugin: 'tlor', key: 'planChecklist' } as const
const PLAN_ROW = /^Plan · /
const STDD_TOUCHED = { plugin: 'tlor', key: 'stddTouched' } as const

export const register = (on: On, options: PluginOptions): void => {
  const stddEnabled = options.stdd_progress !== 'off'
  const planEnabled = options.plan_progress === 'on'
  const reminderEnabled = options.plan_reminder === 'on'
  const autocloseSeconds = parsePlanAutoclose(options.plan_autoclose_s)
  const notifications = notifyMode(options.notify)
  // A fourth source needs its file, one entry here, its feature switch, and any
  // state key or io method it uses added to ProgressReadIo/ProgressToolIo in
  // sources/source.ts and wired in the two io objects below.
  const sources: ProgressSource[] = [
    ...(stddEnabled ? [createStddSource()] : []),
    ...(planEnabled ? [createPlanTasksSource(autocloseSeconds), createChecklistSource(autocloseSeconds)] : []),
  ]

  // The matcher is a literal so `claude plugin validate` can print it; it must list every tool
  // any source reacts to (a test pins it to the union of the tool lists in progress.ts).
  on('tool.call', { tool: /^(?:Bash|Edit|Write|MultiEdit|NotebookEdit|Skill|TodoWrite|TaskCreate|TaskUpdate|ExitPlanMode)$/ }, async ($, e, next) => {
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
      getStddTouched: () => $.state.get(STDD_TOUCHED),
      setStddTouched: (value, version) => $.state.set(STDD_TOUCHED, value, { ifVersion: version }),
      notify: text => notify($, notifications, text),
    }
    const event = e as unknown as Readonly<Record<string, unknown>>
    for (const source of sources) {
      try {
        await source.onToolCall(event, result, io)
      } catch {
        // Progress is observational; a source failure never affects a tool call.
      }
    }

    return addPlanReminder(e, result, reminderEnabled)
  }).catch(($, e, next) => next(e))

  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    if (e.props.hasSurvey) return next(e)

    let drawn: Awaited<ReturnType<typeof orderedSourceLines>> | undefined
    try {
      const io: ProgressReadIo = {
        read: path => $.fs.read(path),
        list: path => $.fs.list(path),
        cwd: () => $.session.cwd(),
        getPlanTasks: () => $.state.get(PLAN_TASKS),
        getPlanChecklist: () => $.state.get(PLAN_CHECKLIST),
        getStddTouched: () => $.state.get(STDD_TOUCHED),
        now: () => $.clock.now(),
        after: (ms, fn) => { $.clock.after(ms, fn) },
        invalidate: () => $.ui.invalidate('ui.render'),
        notify: text => notify($, notifications, text),
      }
      drawn = await orderedSourceLines(sources, io, e.viewport?.columns)
    } catch {
      // Missing or unreadable progress draws nothing; the bands beneath still render.
    }

    // The drawing beneath resolves once per render, outside the try so its errors are not swallowed.
    const below = await next(e)
    const lines = drawn?.lines
    if (lines === undefined || lines === null || lines === BAND_RETRY) return below
    // A lower plugin that already draws a Plan row would show the plan twice; STDD rows are unrelated.
    if (drawn?.source !== 'stdd' && renderedTextLines(below).some(line => PLAN_ROW.test(line))) return below

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
        {below}
      </Box>
    )
  })
}
