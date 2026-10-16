export type NotifyMode = 'off' | 'toast' | 'sound'

type NotifyContext = {
  ui: {
    toast: (text: string) => unknown
  }
  audio: {
    play: (input: { asset: string }) => unknown
  }
  process: {
    run: (argv: readonly string[], init?: { timeoutMs?: number }) => Promise<{ exitCode: number }>
  }
}

// The system alert sound; false when this host cannot play it (no osascript, non-macOS, no process API).
async function playAlertSound($: NotifyContext): Promise<boolean> {
  try {
    const result = await $.process.run(['osascript', '-e', 'beep'], { timeoutMs: 3000 })

    return result.exitCode === 0
  } catch {
    return false
  }
}

export const notifyMode = (value: unknown): NotifyMode =>
  value === 'toast' || value === 'sound' ? value : 'off'

export async function notify($: NotifyContext, mode: NotifyMode, text: string): Promise<void> {
  if (mode === 'off') return
  $.ui.toast(text)
  if (mode === 'sound' && !(await playAlertSound($))) await $.audio.play({ asset: 'hooks/mods/sounds/done.wav' })
}
