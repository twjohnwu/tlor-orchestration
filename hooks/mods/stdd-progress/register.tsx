import type { On, PluginOptions } from 'claude-code'
import type { PlanDeclaration } from '../../../types'

import { notify, notifyMode } from '../notify'
import { casUpdate } from '../state'
import { parsePlanAutoclose } from './planCompletion'
import { createChecklistSource } from './sources/checklist'
import { createDeclaredSource } from './sources/declared'
import { createPlanTasksSource } from './sources/planTasks'
import { normalizedPath } from './progress'
import { BAND_RETRY, orderedSourceLines } from './sources/source'
import type { ProgressReadIo, ProgressSource, ProgressToolIo } from './sources/source'
import { createStddSource } from './sources/stdd'
import { addPlanReminder } from './planReminder'
import { renderedTextLines } from './renderText'

const PLAN_DECLARATION = { plugin: 'tlor', key: 'planDeclaration' } as const
const PLAN_TASKS = { plugin: 'tlor', key: 'planTasks' } as const
const PLAN_CHECKLIST = { plugin: 'tlor', key: 'planChecklist' } as const
const PLAN_ROW = /^Plan · /
const STDD_TOUCHED = { plugin: 'tlor', key: 'stddTouched' } as const
const PLAN_TRACK_TOOL = 'mcp__tlor__PlanTrack'
const PLAN_TRACK_SPEC = {
  name: 'PlanTrack',
  description: 'Declare a plan file and track its checklist or completion ledger.',
  inputSchema: {
    type: 'object',
    additionalProperties: false,
    properties: {
      plan: { type: 'string', minLength: 1, description: 'Plan file path.' },
      progress: { type: 'string', enum: ['checklist', 'ledger'] },
      ledger: { type: 'string', minLength: 1, description: 'Ledger file path for ledger progress.' },
    },
    required: ['plan', 'progress'],
  },
  isDeferred: false,
}

const basename = (path: string): string => {
  const normalized = normalizedPath(path)
  return normalized.slice(normalized.lastIndexOf('/') + 1)
}

const absolutePath = (cwd: string, path: string): string => {
  const normalized = normalizedPath(path)
  if (normalized.startsWith('/') || /^[A-Za-z]:\//.test(normalized)) return normalized
  return `${normalizedPath(cwd)}/${normalized}`
}

const toolError = (message: string): never => ({ result: message, text: message, isError: true }) as never

// Run from the plugin's one session.start hook (hooks/mods/register.tsx).
export async function setupPlanTrack($: { tool: { register: (spec: typeof PLAN_TRACK_SPEC) => Promise<unknown> } }): Promise<void> {
  await $.tool.register(PLAN_TRACK_SPEC)
}

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
    ...(planEnabled ? [
      createDeclaredSource(autocloseSeconds),
      createPlanTasksSource(autocloseSeconds),
      createChecklistSource(autocloseSeconds),
    ] : []),
  ]

  if (planEnabled) {
    on('tool.call', { tool: PLAN_TRACK_TOOL }, async ($, e) => {
      if (typeof e.plan !== 'string' || e.plan.trim() === '') return toolError('PlanTrack requires a plan path.')
      if (e.progress !== 'checklist' && e.progress !== 'ledger') {
        return toolError('PlanTrack progress must be checklist or ledger.')
      }
      if (e.progress === 'ledger' && (typeof e.ledger !== 'string' || e.ledger.trim() === '')) {
        return toolError('PlanTrack ledger mode requires a ledger path.')
      }

      const cwd = await $.session.cwd()
      const plan = absolutePath(cwd, e.plan)
      const declaration: PlanDeclaration = e.progress === 'checklist'
        ? { plan, progress: 'checklist' }
        : { plan, progress: 'ledger', ledger: absolutePath(cwd, e.ledger as string) }
      const didUpdate = await casUpdate(
        () => $.state.get(PLAN_DECLARATION),
        (value, version) => $.state.set(PLAN_DECLARATION, value, { ifVersion: version }),
        () => ({ value: declaration }),
      )
      if (!didUpdate) return toolError('PlanTrack could not save the declaration.')
      $.ui.invalidate('ui.render')
      return { result: declaration.progress === 'ledger'
        ? `Tracking ${basename(plan)} from ${basename(declaration.ledger)}.`
        : `Tracking ${basename(plan)} checklist.` }
    })
  }

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
      getPlanDeclaration: () => $.state.get(PLAN_DECLARATION),
      setPlanDeclaration: (value, version) => $.state.set(PLAN_DECLARATION, value, { ifVersion: version }),
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
        getPlanDeclaration: () => $.state.get(PLAN_DECLARATION),
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
