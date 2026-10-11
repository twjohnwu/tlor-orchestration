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

declare module 'claude-code' {
  interface PluginState {
    tlor: { agents: FellowshipAgent[] }
  }
}
