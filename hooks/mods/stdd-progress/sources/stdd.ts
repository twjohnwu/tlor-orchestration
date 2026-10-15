import { casUpdate } from '../../state'
import type { StddTouched } from '../../../../types'
import type { StddProgressView, StddScan } from '../progress'
import { EDIT_TOOLS, isStddEdit, normalizedPath, progressSegments, scanStdd } from '../progress'
import { THROTTLE_MS, invalidateQuietly } from '../shared'
import { throttled } from '../throttle'
import { BAND_RETRY } from './source'
import type { ProgressReadIo, ProgressSource } from './source'

export const createStddSource = (): ProgressSource => {
  let view: StddProgressView | null | undefined
  let phases: StddScan['phases'] | undefined
  const throttle = throttled(THROTTLE_MS)
  const scan = async (io: ProgressReadIo, canNotify: boolean): Promise<StddProgressView | null> => {
    const touched = (await io.getStddTouched()).value
    const visible = touched !== undefined && (touched.changes.length > 0 || touched.any)
    const result = await scanStdd(
      await io.cwd(),
      { list: io.list, read: io.read },
      touched !== undefined && touched.changes.length > 0 ? touched.changes : undefined,
    )
    const previous = phases
    phases = result.phases
    if (canNotify && previous !== undefined) {
      for (const [name, phase] of Object.entries(result.phases)) {
        if (phase === 'done' && previous[name] !== undefined && previous[name] !== 'done') {
          await io.notify?.(`STDD ${name} complete`)
        }
      }
    }
    return visible ? result.view : null
  }

  return {
    onToolCall: async (event, _result, io) => {
      const touched = await touchedBy(event, await io.cwd())
      if (touched.changes.length > 0 || touched.any) {
        await casUpdate(
          io.getStddTouched,
          io.setStddTouched,
          current => {
            const previous = current ?? { changes: [], any: false }
            const changes = [...new Set([...previous.changes, ...touched.changes])]
            const any = previous.any || touched.any
            if (changes.length === previous.changes.length && any === previous.any) return null
            return { value: { changes, any } }
          },
        )
      }
      if (!isStddEdit(event)) return

      await throttle.run(io.now, io.after, async () => {
        try {
          view = await scan(io, event.agentId === undefined)
        } catch {
          view = null
          throw new Error('STDD progress scan failed')
        } finally {
          invalidateQuietly(io.invalidate)
        }
      })
    },
    lines: async (io, columns) => {
      if (view === undefined) {
        try {
          // First draw is read-only; state writes only happen in onToolCall.
          view = await scan(io, false)
        } catch {
          // Leave the cache unset: the band stays empty now and the next draw retries.
          return BAND_RETRY
        }
      }

      return view === null ? undefined : progressSegments(view, columns)
    },
  }
}

const absolutePath = (cwd: string, path: string): string => {
  const normalized = normalizedPath(path)
  if (normalized.startsWith('/') || /^[A-Za-z]:\//.test(normalized)) return normalized
  return `${normalizedPath(cwd)}/${normalized}`
}

const changeFromPath = (cwd: string, path: string): string | undefined => {
  const resolved = absolutePath(cwd, path)
  const match = /(?:^|\/)STDD\/[^/]+\//.exec(`${resolved}/`)
  if (match === null) return undefined
  return resolved.slice(0, match.index + match[0].length - 1)
}

const bashChanges = (cwd: string, command: string): string[] => {
  const changes: string[] = []
  const normalized = command.replace(/\\/g, '/')
  const paths = /(?:^|[\s"'`=;|&()])((?:(?:[A-Za-z]:)?\/)?(?:[^/\s"'`=;|&()]+\/)*STDD\/[^/\s"'`=;|&()]+)\//g
  for (const match of normalized.matchAll(paths)) {
    const path = match[1]
    if (path !== undefined) changes.push(absolutePath(cwd, path))
  }
  return changes
}

const touchedBy = async (
  event: Readonly<Record<string, unknown>>,
  cwd: string,
): Promise<StddTouched> => {
  const tool = String(event.tool)
  if (tool === 'Skill') {
    return {
      changes: [],
      any: typeof event.skill === 'string' && /^(?:[^:]+:)?stdd/.test(event.skill),
    }
  }
  if (tool === 'Bash' && typeof event.command === 'string') {
    return { changes: [...new Set(bashChanges(cwd, event.command))], any: false }
  }
  if (!EDIT_TOOLS.some(name => name === tool)) return { changes: [], any: false }
  const path = typeof event.file_path === 'string'
    ? event.file_path
    : typeof event.notebook_path === 'string'
      ? event.notebook_path
      : undefined
  const change = path === undefined ? undefined : changeFromPath(cwd, path)
  return { changes: change === undefined ? [] : [change], any: false }
}
