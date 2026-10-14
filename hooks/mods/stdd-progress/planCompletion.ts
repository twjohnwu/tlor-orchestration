import type { ProgressReadIo } from './sources/source'

export const parsePlanAutoclose = (value: unknown): number => {
  if (typeof value !== 'number' && typeof value !== 'string') return 60
  if (typeof value === 'string' && value.trim() === '') return 60
  const parsed = typeof value === 'number' ? value : Number(value)

  return Number.isFinite(parsed) && parsed >= 0 ? parsed : 60
}

export type PlanCompletion = {
  observe: (key: string | undefined, isComplete: boolean, io: ProgressReadIo) => Promise<boolean>
}

export const createPlanCompletion = (autocloseSeconds: number): PlanCompletion => {
  let completion: { key: string; at: number } | undefined

  return {
    observe: async (key, isComplete, io) => {
      if (key === undefined || !isComplete) {
        completion = undefined
        return false
      }

      const now = io.now === undefined ? Date.now() : await io.now()
      if (completion?.key !== key) {
        completion = { key, at: now }
        await io.notify?.('Plan complete')
        if (autocloseSeconds > 0 && io.after !== undefined && io.invalidate !== undefined) {
          io.after(autocloseSeconds * 1000, io.invalidate)
        }
      }

      if (autocloseSeconds === 0) return true
      if (autocloseSeconds < 0) return false
      return now - completion.at < autocloseSeconds * 1000
    },
  }
}
