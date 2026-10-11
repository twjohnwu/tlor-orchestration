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

declare module 'claude-code' {
  interface PluginState {
    tlor: {
      agents: FellowshipAgent[]
      planTasks: PlanTask[]
      planChecklist: PlanChecklist | null
    }
  }
}
