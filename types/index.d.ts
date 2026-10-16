export type FellowshipAgent = {
  id: string
  type: string
  description: string
  status: 'running' | 'completed' | 'failed' | 'killed'
  startedAt: number
  endedAt: number | null
  tokens: number
  tools: number
  model?: string
  effort?: string
  toolStartedAt?: number
  lastEventAt?: number
}

export type PlanTask = {
  id: string
  subject: string
  activeForm?: string
  status: 'pending' | 'in_progress' | 'completed'
}

export type PlanChecklist = {
  path: string
}

export type PlanDeclaration =
  | { plan: string; progress: 'checklist'; ledger?: undefined }
  | { plan?: string; progress: 'ledger'; ledger: string }

export type StddTouched = {
  changes: string[]
  any: boolean
}

declare module 'claude-code' {
  interface PluginState {
    tlor: {
      agents: FellowshipAgent[]
      planDeclaration: PlanDeclaration
      planTasks: PlanTask[]
      planChecklist: PlanChecklist | null
      stddTouched: StddTouched
    }
  }
}
