import type { On, PluginOptions } from 'claude-code'

import type { ChecklistFileView, PlanTask, StddProgressView } from './progress'
import {
  checklistProgressSegments,
  isPlanVisible,
  parseMarkdownChecklist,
  planProgressSegments,
  progressSegments,
  scanProgress,
} from './progress'

const THROTTLE_MS = 1000
const EDIT_TOOLS = ['Edit', 'Write', 'MultiEdit', 'NotebookEdit'] as const
const PLAN_TASKS = { plugin: 'tlor', key: 'planTasks' } as const
const PLAN_CHECKLIST = { plugin: 'tlor', key: 'planChecklist' } as const

const isRecord = (value: unknown): value is Readonly<Record<string, unknown>> =>
  typeof value === 'object' && value !== null

const taskCreateId = (callResult: unknown): string | undefined => {
  if (!isRecord(callResult)) return undefined
  const output = callResult.result
  if (isRecord(output)) {
    const task = output.task
    if (isRecord(task) && (typeof task.id === 'string' || typeof task.id === 'number')) return String(task.id)
    if (typeof output.taskId === 'string' || typeof output.taskId === 'number') return String(output.taskId)
    if (typeof output.id === 'string' || typeof output.id === 'number') return String(output.id)
  }

  if (typeof callResult.text !== 'string') return undefined
  const hash = /#([A-Za-z0-9_-]+)/.exec(callResult.text)?.[1]
  if (hash !== undefined) return hash
  return /\bTask\s+([A-Za-z0-9_-]+)/i.exec(callResult.text)?.[1]
}

const updatedPlanTasks = (
  current: readonly PlanTask[],
  event: Readonly<Record<string, unknown>>,
  callResult: unknown,
  syntheticId: () => string,
): PlanTask[] | null => {
  if (event.tool === 'TodoWrite') {
    if (!Array.isArray(event.todos)) return null
    return event.todos.flatMap((todo, index) => {
      if (!isRecord(todo)) return []
      if (typeof todo.content !== 'string') return []
      if (todo.status !== 'pending' && todo.status !== 'in_progress' && todo.status !== 'completed') return []
      return [{
        id: `todo:${index}`,
        subject: todo.content,
        ...(typeof todo.activeForm === 'string' ? { activeForm: todo.activeForm } : {}),
        status: todo.status,
      }]
    })
  }

  if (event.tool === 'TaskCreate') {
    if (typeof event.subject !== 'string') return null
    return [...current, {
      id: taskCreateId(callResult) ?? syntheticId(),
      subject: event.subject,
      ...(typeof event.activeForm === 'string' ? { activeForm: event.activeForm } : {}),
      status: 'pending',
    }]
  }

  if (event.tool !== 'TaskUpdate' || typeof event.taskId !== 'string') return null
  const index = current.findIndex(task => task.id === event.taskId)
  if (index < 0) return null
  if (event.status === 'deleted') return current.filter((_task, taskIndex) => taskIndex !== index)

  const task = current[index]
  if (task === undefined) return null
  const status = event.status === 'pending' || event.status === 'in_progress' || event.status === 'completed'
    ? event.status
    : task.status
  const replacement: PlanTask = {
    ...task,
    ...(typeof event.subject === 'string' ? { subject: event.subject } : {}),
    ...(typeof event.activeForm === 'string' ? { activeForm: event.activeForm } : {}),
    status,
  }
  return current.map((item, taskIndex) => taskIndex === index ? replacement : item)
}

const isStddEdit = (event: Readonly<Record<string, unknown>>): boolean => {
  const tool = String(event.tool)
  if (tool === 'Bash') return true
  if (!EDIT_TOOLS.some(name => name === tool)) return false
  const path = typeof event.file_path === 'string'
    ? event.file_path
    : typeof event.notebook_path === 'string'
      ? event.notebook_path
      : ''

  return path.replace(/\\/g, '/').includes('/STDD/')
}

const normalizedPath = (path: string): string => path.replace(/\\/g, '/').replace(/\/+$/, '')

export const register = (on: On, options: PluginOptions): void => {
  const stddEnabled = options.stdd_progress !== 'off'
  const planEnabled = options.plan_progress === 'on'
  // The render path must never write ($.state is refused while ui.render draws),
  // so the view lives in this closure: undefined until first scanned.
  let view: StddProgressView | null | undefined
  let lastScanAt = Number.NEGATIVE_INFINITY
  let isTrailingScheduled = false
  let syntheticTaskId = 0
  let trackedChecklist: { path: string } | null | undefined
  let trackedChecklistView: ChecklistFileView | null | undefined
  let lastChecklistScanAt = Number.NEGATIVE_INFINITY
  let isChecklistTrailingScheduled = false

  on('tool.call', { tool: /^(?:Bash|Edit|Write|MultiEdit|NotebookEdit|TodoWrite|TaskCreate|TaskUpdate|ExitPlanMode)$/ }, async ($, e, next) => {
    const result = await next(e)
    const event = e as unknown as Readonly<Record<string, unknown>>

    // A denied or failed call changed nothing, so the plan stays as it was.
    const didSucceed = !('deny' in result) && result.isError !== true
    if (planEnabled && e.agentId === undefined && didSucceed) {
      try {
        for (let attempt = 0; attempt < 5; attempt += 1) {
          const { value = [], version } = await $.state.get(PLAN_TASKS)
          const tasks = updatedPlanTasks(value, event, result, () => {
            syntheticTaskId += 1
            return `synthetic:${syntheticTaskId}`
          })
          if (tasks === null) break
          const saved = await $.state.set(PLAN_TASKS, tasks, { ifVersion: version })
          if (saved.isSet) break
        }
      } catch {
        // Plan progress is observational; state failures never affect a tool call.
      }

      const tool = String(event.tool)
      const exitOutput = isRecord(result) ? result.result : undefined
      const exitPlanPath = tool === 'ExitPlanMode' && isRecord(exitOutput) && typeof exitOutput.filePath === 'string'
        ? exitOutput.filePath
        : undefined
      const filePath = typeof event.file_path === 'string' && EDIT_TOOLS.some(name => name === tool)
        ? event.file_path
        : exitPlanPath

      if (filePath !== undefined && /\.md$/i.test(filePath)) {
        try {
          const checklist = parseMarkdownChecklist(await $.fs.read(filePath))
          for (let attempt = 0; attempt < 5; attempt += 1) {
            const { value, version } = await $.state.get(PLAN_CHECKLIST)
            const current = value ?? null
            const replacement = checklist.total >= 2
              ? { path: filePath }
              : current !== null && normalizedPath(current.path) === normalizedPath(filePath)
                ? null
                : undefined
            if (replacement === undefined) break
            const saved = await $.state.set(PLAN_CHECKLIST, replacement, { ifVersion: version })
            if (saved.isSet) {
              trackedChecklist = replacement
              trackedChecklistView = replacement === null ? null : { path: filePath, checklist }
              lastChecklistScanAt = await $.clock.now()
              $.ui.invalidate('ui.render')
              break
            }
          }
        } catch {
          // An unreadable markdown edit does not replace the last known checklist.
        }
      }

      if (tool === 'Bash' || tool === 'Write' || tool === 'Edit' || tool === 'MultiEdit') {
        const rescanTrackedChecklist = async (): Promise<void> => {
          try {
            if (trackedChecklist === undefined) {
              const { value } = await $.state.get(PLAN_CHECKLIST)
              trackedChecklist = value ?? null
            }
            if (trackedChecklist === null) {
              trackedChecklistView = null
              return
            }
            const path = trackedChecklist.path
            const checklist = parseMarkdownChecklist(await $.fs.read(path))
            trackedChecklistView = checklist.total >= 2 ? { path, checklist } : null
            lastChecklistScanAt = await $.clock.now()
          } catch {
            trackedChecklistView = null
          }
          try {
            $.ui.invalidate('ui.render')
          } catch {
            // A failed redraw request must not affect the session.
          }
        }

        try {
          if (trackedChecklist === undefined) {
            const { value } = await $.state.get(PLAN_CHECKLIST)
            trackedChecklist = value ?? null
          }
          if (trackedChecklist !== null) {
            const now = await $.clock.now()
            const wait = THROTTLE_MS - (now - lastChecklistScanAt)
            if (wait <= 0) {
              await rescanTrackedChecklist()
            } else if (!isChecklistTrailingScheduled) {
              isChecklistTrailingScheduled = true
              $.clock.after(wait, () => {
                isChecklistTrailingScheduled = false
                void rescanTrackedChecklist()
              })
            }
          }
        } catch {
          isChecklistTrailingScheduled = false
        }
      }
    }

    if (stddEnabled && isStddEdit(event)) {
      const rescan = async (): Promise<void> => {
        try {
          const cwd = await $.session.cwd()
          view = await scanProgress(cwd, {
            list: async path => {
              return $.fs.list(path)
            },
            read: async path => {
              return $.fs.read(path)
            },
          })
          lastScanAt = await $.clock.now()
        } catch {
          // Progress is observational; a failed scan hides the band.
          view = null
        }
        try {
          $.ui.invalidate('ui.render')
        } catch {
          // A failed redraw request must not affect the session.
        }
      }

      try {
        const now = await $.clock.now()
        const wait = THROTTLE_MS - (now - lastScanAt)
        if (wait <= 0) {
          await rescan()
        } else if (!isTrailingScheduled) {
          // Throttled: one trailing rescan when the window ends, so the last edit shows.
          isTrailingScheduled = true
          $.clock.after(wait, () => {
            isTrailingScheduled = false
            void rescan()
          })
        }
      } catch {
        isTrailingScheduled = false
      }
    }

    return result
  }).catch(($, e, next) => next(e))

  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    if (e.props.hasSurvey) return next(e)

    try {
      if (stddEnabled && view === undefined) {
        // First draw: read-only scan, cached in the closure; no state write here.
        const cwd = await $.session.cwd()
        view = await scanProgress(cwd, {
          list: async path => {
            return $.fs.list(path)
          },
          read: async path => {
            return $.fs.read(path)
          },
        })
      }
      if (planEnabled && trackedChecklistView === undefined) {
        try {
          if (trackedChecklist === undefined) {
            const { value } = await $.state.get(PLAN_CHECKLIST)
            trackedChecklist = value ?? null
          }
          if (trackedChecklist === null) {
            trackedChecklistView = null
          } else {
            const path = trackedChecklist.path
            const checklist = parseMarkdownChecklist(await $.fs.read(path))
            trackedChecklistView = checklist.total >= 2 ? { path, checklist } : null
          }
        } catch {
          trackedChecklistView = null
        }
      }
      let lines = view === undefined || view === null
        ? undefined
        : progressSegments(view, e.viewport?.columns)

      if (lines === undefined && planEnabled) {
        const { value: tasks = [] } = await $.state.get(PLAN_TASKS)
        if (tasks.length >= 1) {
          if (isPlanVisible(tasks)) lines = planProgressSegments(tasks, e.viewport?.columns)
        } else if (trackedChecklistView !== undefined && trackedChecklistView !== null) {
          if (trackedChecklistView.checklist.completed < trackedChecklistView.checklist.total) {
            lines = checklistProgressSegments(
              trackedChecklistView.path,
              trackedChecklistView.checklist,
              e.viewport?.columns,
            )
          }
        }
      }

      if (lines !== undefined) {
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
