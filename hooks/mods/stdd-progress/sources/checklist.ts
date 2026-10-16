import { casUpdate } from '../../state'
import type { PlanChecklist } from '../../../../types'
import type { ChecklistFileView } from '../progress'
import {
  CHECKLIST_TOOLS,
  EDIT_TOOLS,
  checklistProgressSegments,
  isRecord,
  normalizedPath,
  checklistProgress,
  parseMarkdownChecklistItems,
} from '../progress'
import { createPlanCompletion } from '../planCompletion'
import { THROTTLE_MS, invalidateQuietly, succeeded } from '../shared'
import { throttled } from '../throttle'
import type { ProgressReadIo, ProgressSource, ProgressToolIo } from './source'

type LazyChecklist = {
  tracked: (io: ProgressReadIo) => Promise<PlanChecklist | null>
  load: (io: ProgressReadIo) => Promise<ChecklistFileView | null>
  reload: (io: ProgressReadIo) => Promise<ChecklistFileView | null>
  replace: (tracked: PlanChecklist | null, view: ChecklistFileView | null) => void
  parse: (path: string, text: string) => ChecklistFileView | null
  hide: () => void
}

// Caches the tracked file and its parsed view; every read uses the io of the current call.
const lazyChecklist = (): LazyChecklist => {
  let trackedChecklist: PlanChecklist | null | undefined
  let trackedChecklistView: ChecklistFileView | null | undefined
  let rememberedPath: string | undefined
  let checkedTitles = new Set<string>()

  const parse = (path: string, text: string): ChecklistFileView | null => {
    const pathKey = normalizedPath(path)
    if (rememberedPath !== pathKey) {
      rememberedPath = pathKey
      checkedTitles = new Set()
    }

    const items = parseMarkdownChecklistItems(text)
    for (const item of items) if (item.checked) checkedTitles.add(item.title)
    const remembered = items.map(item => ({
      ...item,
      checked: item.checked || checkedTitles.has(item.title),
    }))
    const checklist = checklistProgress(remembered)
    return checklist.total >= 2 ? { path, checklist } : null
  }

  const tracked = async (io: ProgressReadIo): Promise<PlanChecklist | null> => {
    if (trackedChecklist === undefined) trackedChecklist = (await io.getPlanChecklist()).value ?? null
    return trackedChecklist
  }

  const reload = async (io: ProgressReadIo): Promise<ChecklistFileView | null> => {
    const selected = await tracked(io)
    if (selected === null) {
      trackedChecklistView = null
      return null
    }

    trackedChecklistView = parse(selected.path, await io.read(selected.path))
    return trackedChecklistView
  }

  return {
    tracked,
    load: async io => trackedChecklistView === undefined ? reload(io) : trackedChecklistView,
    reload,
    parse,
    replace: (selected, view) => {
      trackedChecklist = selected
      trackedChecklistView = view
    },
    hide: () => {
      trackedChecklistView = null
    },
  }
}

export const createChecklistSource = (autocloseSeconds = -1): ProgressSource => {
  const selected = lazyChecklist()
  const throttle = throttled(THROTTLE_MS)
  const completion = createPlanCompletion(autocloseSeconds)

  return {
    id: 'planChecklist',
    onToolCall: async (event, result, io) => {
      if (event.agentId !== undefined || !succeeded(result)) return

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
          const view = selected.parse(filePath, await io.read(filePath))
          const checklist = view?.checklist ?? { completed: 0, total: 0 }
          let replacement: { path: string } | null | undefined
          const didUpdate = await casUpdate(
            io.getPlanChecklist,
            io.setPlanChecklist,
            value => {
              const current = value ?? null
              replacement = checklist.total >= 2
                ? { path: filePath }
                : current !== null && normalizedPath(current.path) === normalizedPath(filePath)
                  ? null
                  : undefined

              return replacement === undefined ? null : { value: replacement }
            },
          )
          if (didUpdate && replacement !== undefined) {
            selected.replace(
              replacement,
              replacement === null ? null : view,
            )
            // A newly selected file starts a throttle window, so a rescan in this call is trailing.
            throttle.markRun(await io.now())
            io.invalidate()
            await completion.observe(
              replacement === null ? undefined : normalizedPath(filePath),
              replacement !== null && checklist.total > 0 && checklist.completed >= checklist.total,
              io,
            )
          }
        } catch {
          // An unreadable markdown edit does not replace the last known checklist.
        }
      }

      // ExitPlanMode only selects a plan file above; it never triggers a rescan.
      if (tool === 'ExitPlanMode' || !CHECKLIST_TOOLS.some(name => name === tool)) return
      try {
        if (await selected.tracked(io) === null) return
      } catch {
        // Leave the view unset so the next render reloads the file.
        return
      }

      await throttle.run(io.now, io.after, async () => {
        try {
          const view = await selected.reload(io)
          await completion.observe(
            view === null ? undefined : normalizedPath(view.path),
            view !== null && view.checklist.completed >= view.checklist.total,
            io,
          )
        } catch {
          selected.hide()
          throw new Error('Checklist progress scan failed')
        } finally {
          invalidateQuietly(io.invalidate)
        }
      })
    },
    // First draw loads the view even when an earlier source claims the band; read-only.
    prime: async io => {
      try {
        if (await selected.tracked(io) !== null) await selected.load(io)
      } catch {
        selected.hide()
      }
    },
    lines: async (io, columns) => {
      try {
        if (await selected.tracked(io) === null) return undefined
        const view = await selected.load(io)
        if (view === null) {
          await completion.observe(undefined, false, io)
          return null
        }
        const complete = view.checklist.completed >= view.checklist.total
        const visible = await completion.observe(normalizedPath(view.path), complete, io)
        if (complete && !visible) return null
        return checklistProgressSegments(view.path, view.checklist, columns)
      } catch {
        selected.hide()
        return null
      }
    },
  }
}
