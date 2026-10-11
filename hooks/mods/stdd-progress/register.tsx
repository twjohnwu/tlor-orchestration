import type { On, PluginOptions } from 'claude-code'

import type { StddProgressView } from './progress'
import { formatProgress, scanProgress } from './progress'

const THROTTLE_MS = 1000
const EDIT_TOOLS = ['Edit', 'Write', 'MultiEdit', 'NotebookEdit'] as const

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

export const register = (on: On, _options: PluginOptions): void => {
  // The render path must never write ($.state is refused while ui.render draws),
  // so the view lives in this closure: undefined until first scanned.
  let view: StddProgressView | null | undefined
  let lastScanAt = Number.NEGATIVE_INFINITY
  let isTrailingScheduled = false

  on('tool.call', { tool: /^(?:Bash|Edit|Write|MultiEdit|NotebookEdit)$/ }, async ($, e, next) => {
    const result = await next(e)
    if (isStddEdit(e as unknown as Readonly<Record<string, unknown>>)) {
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
      if (view === undefined) {
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
      if (view !== undefined && view !== null) {
        const { Box, Text } = $.ui.resolve(e)
        const lines = formatProgress(view, e.viewport?.columns)

        return (
          <Box flexDirection="column">
            <Text>{lines[0]}</Text>
            {lines[1] !== undefined && <Text>{lines[1]}</Text>}
          </Box>
        )
      }
    } catch {
      // Missing or unreadable progress never takes over the prompt band.
    }

    return next(e)
  })
}
