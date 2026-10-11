export type Throttle = {
  // The trailing run uses the now/after/run of the call that scheduled it.
  run: (
    now: () => Promise<number>,
    after: (ms: number, fn: () => void) => void,
    fn: () => Promise<void>,
  ) => Promise<void>
  // Starts a new window at `at`, as if a run had just succeeded.
  markRun: (at: number) => void
}

export const throttled = (windowMs: number): Throttle => {
  let lastSuccessAt = Number.NEGATIVE_INFINITY
  let trailingScheduled = false

  const runAndMark = async (now: () => Promise<number>, fn: () => Promise<void>): Promise<void> => {
    await fn()
    lastSuccessAt = await now()
  }

  return {
    run: async (now, after, fn) => {
      try {
        const current = await now()
        const wait = windowMs - (current - lastSuccessAt)
        if (wait <= 0) {
          await runAndMark(now, fn)
        } else if (!trailingScheduled) {
          trailingScheduled = true
          after(wait, () => {
            trailingScheduled = false
            void runAndMark(now, fn).catch(() => undefined)
          })
        }
      } catch {
        trailingScheduled = false
      }
    },
    markRun: at => {
      lastSuccessAt = at
    },
  }
}
