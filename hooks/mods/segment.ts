import type { Color } from 'claude-code'

export type Segment = {
  text: string
  color?: Color
  bold?: boolean
  dim?: boolean
}
