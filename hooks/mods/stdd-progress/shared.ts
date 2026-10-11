import { isRecord } from './progress'

export const THROTTLE_MS = 1000

// A denied or failed call changed nothing, so sources ignore it.
export const succeeded = (result: unknown): boolean =>
  !isRecord(result) || (!('deny' in result) && result.isError !== true)

// Always asks for a redraw once a scan settles; a failed request must not affect the session.
export const invalidateQuietly = (invalidate: () => void): void => {
  try {
    invalidate()
  } catch {
    // A failed redraw request must not affect the session.
  }
}
