import type { StateRead, StateSetResult } from 'claude-code'

export type CasUpdate<T> = { value: T } | null

export const casUpdate = async <T>(
  get: () => Promise<StateRead<T>>,
  set: (value: T, version: number) => Promise<StateSetResult>,
  compute: (current: T | undefined) => CasUpdate<T>,
): Promise<boolean> => {
  for (let attempt = 0; attempt < 5; attempt += 1) {
    const { value, version } = await get()
    const update = compute(value)
    if (update === null) return false
    const saved = await set(update.value, version)
    if (saved.isSet) return true
  }

  return false
}
