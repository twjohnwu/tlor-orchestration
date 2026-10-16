import { expect, test } from 'claude-code/testing'

import { notify } from '../../hooks/mods/notify'

type Played = { asset: string }

const fakeContext = (run: unknown) => {
  const played: Played[] = []
  const ran: Array<{ argv: readonly string[], init: unknown }> = []
  const $ = {
    ui: { toast: () => undefined },
    audio: { play: async (input: Played) => { played.push(input) } },
    ...(run === undefined ? {} : {
      process: {
        run: async (argv: readonly string[], init: unknown) => {
          ran.push({ argv, init })
          return (run as () => unknown)()
        },
      },
    }),
  }

  return { $: $ as never, played, ran }
}

const CHIME = { asset: 'hooks/mods/sounds/done.wav' }

test('sound mode plays the macOS alert sound and skips the chime when it exits 0', async () => {
  const { $, played, ran } = fakeContext(() => ({ exitCode: 0, stdout: '', stderr: '' }))
  await notify($, 'sound', 'done')

  expect(ran).toEqual([{ argv: ['osascript', '-e', 'beep'], init: { timeoutMs: 3000 } }])
  expect(played).toEqual([])
})

test('sound mode falls back to the chime when the alert sound exits non-zero', async () => {
  const { $, played } = fakeContext(() => ({ exitCode: 1, stdout: '', stderr: 'no osascript' }))
  await notify($, 'sound', 'done')

  expect(played).toEqual([CHIME])
})

test('sound mode falls back to the chime when running the alert sound throws', async () => {
  const { $, played } = fakeContext(() => { throw new Error('cannot start') })
  await notify($, 'sound', 'done')

  expect(played).toEqual([CHIME])
})

test('sound mode falls back to the chime when the context has no process API', async () => {
  const { $, played } = fakeContext(undefined)
  await notify($, 'sound', 'done')

  expect(played).toEqual([CHIME])
})

test('toast mode never runs a process or plays a sound', async () => {
  const { $, played, ran } = fakeContext(() => ({ exitCode: 0, stdout: '', stderr: '' }))
  await notify($, 'toast', 'done')

  expect(ran).toEqual([])
  expect(played).toEqual([])
})
