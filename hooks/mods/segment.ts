import type { ThemeKey } from 'claude-code'

export type Segment = {
  text: string
  color?: ThemeKey
  bold?: boolean
  dim?: boolean
}
