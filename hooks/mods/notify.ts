export type NotifyMode = 'off' | 'toast' | 'sound'

type NotifyContext = {
  ui: {
    toast: (text: string) => unknown
  }
  audio: {
    play: (input: { asset: string }) => unknown
  }
}

export const notifyMode = (value: unknown): NotifyMode =>
  value === 'toast' || value === 'sound' ? value : 'off'

export async function notify($: NotifyContext, mode: NotifyMode, text: string): Promise<void> {
  if (mode === 'off') return
  $.ui.toast(text)
  if (mode === 'sound') await $.audio.play({ asset: 'hooks/mods/sounds/done.wav' })
}
