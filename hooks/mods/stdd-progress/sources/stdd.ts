import type { StddProgressView } from '../progress'
import { isStddEdit, progressSegments, scanProgress } from '../progress'
import { THROTTLE_MS, invalidateQuietly } from '../shared'
import { throttled } from '../throttle'
import { BAND_RETRY } from './source'
import type { ProgressReadIo, ProgressSource } from './source'

export const createStddSource = (): ProgressSource => {
  let view: StddProgressView | null | undefined
  const throttle = throttled(THROTTLE_MS)
  const scan = async (io: ProgressReadIo): Promise<StddProgressView | null> =>
    scanProgress(await io.cwd(), { list: io.list, read: io.read })

  return {
    onToolCall: async (event, _result, io) => {
      if (!isStddEdit(event)) return

      await throttle.run(io.now, io.after, async () => {
        try {
          view = await scan(io)
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
          view = await scan(io)
        } catch {
          // Leave the cache unset: the band stays empty now and the next draw retries.
          return BAND_RETRY
        }
      }

      return view === null ? undefined : progressSegments(view, columns)
    },
  }
}
