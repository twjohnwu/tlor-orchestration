import { expect, test } from 'claude-code/testing'

import { casUpdate } from '../../hooks/mods/state'

test('casUpdate lands on the first try', async () => {
  const writes: Array<{ value: number; version: number }> = []
  const landed = await casUpdate(
    async () => ({ value: 2, version: 7 }),
    async (value, version) => {
      writes.push({ value, version })
      return { isSet: true, version: version + 1 }
    },
    current => ({ value: (current ?? 0) + 1 }),
  )

  expect(landed).toBe(true)
  expect(writes).toEqual([{ value: 3, version: 7 }])
})

test('casUpdate retries a version miss and then lands', async () => {
  let reads = 0
  const writes: Array<{ value: number; version: number }> = []
  const landed = await casUpdate(
    async () => {
      reads += 1
      return { value: reads * 10, version: reads }
    },
    async (value, version) => {
      writes.push({ value, version })
      return version === 1
        ? { isSet: false, version: 2 }
        : { isSet: true, version: 3 }
    },
    current => ({ value: (current ?? 0) + 1 }),
  )

  expect(landed).toBe(true)
  expect(reads).toBe(2)
  expect(writes).toEqual([{ value: 11, version: 1 }, { value: 21, version: 2 }])
})

test('casUpdate stops without writing when compute returns null', async () => {
  let writes = 0
  const landed = await casUpdate(
    async () => ({ value: 2, version: 7 }),
    async (_value, version) => {
      writes += 1
      return { isSet: true, version: version + 1 }
    },
    () => null,
  )

  expect(landed).toBe(false)
  expect(writes).toBe(0)
})

test('casUpdate gives up after five version misses', async () => {
  let reads = 0
  let writes = 0
  const landed = await casUpdate(
    async () => ({ value: ++reads, version: reads }),
    async (_value, version) => {
      writes += 1
      return { isSet: false, version: version + 1 }
    },
    current => ({ value: current ?? 0 }),
  )

  expect(landed).toBe(false)
  expect(reads).toBe(5)
  expect(writes).toBe(5)
})
