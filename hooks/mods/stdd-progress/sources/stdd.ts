import type { StddProgressView, StddScan } from '../progress'
import { isStddEdit, progressSegments, scanStdd } from '../progress'
import { THROTTLE_MS, invalidateQuietly } from '../shared'
import { throttled } from '../throttle'
import { BAND_RETRY } from './source'
import type { ProgressReadIo, ProgressSource } from './source'

export const createStddSource = (): ProgressSource => {
  let view: StddProgressView | null | undefined
  let phases: StddScan['phases'] | undefined
  const throttle = throttled(THROTTLE_MS)
  const scan = async (io: ProgressReadIo, canNotify: boolean): Promise<StddProgressView | null> => {
    const result = await scanStdd(await io.cwd(), { list: io.list, read: io.read })
    const previous = phases
    phases = result.phases
    if (canNotify && previous !== undefined) {
      for (const [name, phase] of Object.entries(result.phases)) {
        if (phase === 'done' && previous[name] !== undefined && previous[name] !== 'done') {
          await io.notify?.(`STDD ${name} complete`)
        }
      }
    }
    return result.view
  }

  return {
    onToolCall: async (event, _result, io) => {
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
