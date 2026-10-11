import { casUpdate } from '../../state'
import type { PlanChecklist } from '../../../../types'
import type { ChecklistFileView } from '../progress'
import {
  CHECKLIST_TOOLS,
  EDIT_TOOLS,
  checklistProgressSegments,
  isRecord,
  normalizedPath,
  parseMarkdownChecklist,
} from '../progress'
import { THROTTLE_MS, invalidateQuietly, succeeded } from '../shared'
import { throttled } from '../throttle'
import type { ProgressReadIo, ProgressSource, ProgressToolIo } from './source'

type LazyChecklist = {
  tracked: (io: ProgressReadIo) => Promise<PlanChecklist | null>
  load: (io: ProgressReadIo) => Promise<ChecklistFileView | null>
  reload: (io: ProgressReadIo) => Promise<ChecklistFileView | null>
  replace: (tracked: PlanChecklist | null, view: ChecklistFileView | null) => void
  hide: () => void
}

// Caches the tracked file and its parsed view; every read uses the io of the current call.
const lazyChecklist = (): LazyChecklist => {
  let trackedChecklist: PlanChecklist | null | undefined
  let trackedChecklistView: ChecklistFileView | null | undefined

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

    const checklist = parseMarkdownChecklist(await io.read(selected.path))
    trackedChecklistView = checklist.total >= 2 ? { path: selected.path, checklist } : null
    return trackedChecklistView
  }

  return {
    tracked,
    load: async io => trackedChecklistView === undefined ? reload(io) : trackedChecklistView,
    reload,
    replace: (selected, view) => {
      trackedChecklist = selected
      trackedChecklistView = view
    },
    hide: () => {
      trackedChecklistView = null
    },
  }
}

export const createChecklistSource = (): ProgressSource => {
  const selected = lazyChecklist()
  const throttle = throttled(THROTTLE_MS)

  return {
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
          const checklist = parseMarkdownChecklist(await io.read(filePath))
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
              replacement === null ? null : { path: filePath, checklist },
            )
            // A newly selected file starts a throttle window, so a rescan in this call is trailing.
            throttle.markRun(await io.now())
            io.invalidate()
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
          await selected.reload(io)
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
        if (view === null || view.checklist.completed >= view.checklist.total) return null
        return checklistProgressSegments(view.path, view.checklist, columns)
      } catch {
        selected.hide()
        return null
      }
    },
  }
}
