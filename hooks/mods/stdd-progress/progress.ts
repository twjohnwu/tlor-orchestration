import type { ThemeKey } from 'claude-code'

export type Segment = {
  text: string
  color?: ThemeKey
  bold?: boolean
  dim?: boolean
}

export type StddPhase = 'uiux' | 'spec (draft)' | 'plan' | 'execute' | 'done'

export type StddFiles = {
  designUx?: string
  spec?: string
  tasks?: string
}

export type StddCandidate = {
  name: string
  mtimeMs: number
  files: StddFiles
}

export type StddProgressView = {
  name: string
  phase: Exclude<StddPhase, 'done'>
  completed: number
  total: number
  wip?: string
}

export type TaskProgress = {
  completed: number
  total: number
  wip?: string
}

type TaskLine = {
  status: ' ' | 'wip' | 'x'
  id: string
  tag?: '[MANUAL]' | '[INFRA]'
}

type ProgressFsEntry = {
  name: string
  kind: 'file' | 'dir' | 'other'
  mtimeMs: number
}

type ProgressFs = {
  list: (path: string) => Promise<readonly ProgressFsEntry[]>
  read: (path: string) => Promise<string>
}

const TASK_LINE = /^- \[( |wip|x)\] `([^`]+)`(?: `(\[MANUAL\]|\[INFRA\])`)?/
const FENCE_LINE = /^\s*```/
const ARTIFACTS = ['tasks.md', 'spec.md', 'design-ux.md'] as const

// Mirrors utf-8-sig in scripts/stdd_custody_check.py: a leading BOM must not hide the first line.
const stripBom = (text: string): string => text.startsWith('\uFEFF') ? text.slice(1) : text

const taskLines = (text: string): TaskLine[] => {
  const found: TaskLine[] = []
  let inFence = false

  for (const line of stripBom(text).split(/\r?\n/)) {
    if (FENCE_LINE.test(line)) {
      inFence = !inFence
      continue
    }
    if (inFence) continue

    const match = TASK_LINE.exec(line)
    if (match === null) continue
    const status = match[1]
    const id = match[2]
    if ((status !== ' ' && status !== 'wip' && status !== 'x') || id === undefined) continue

    const tag = match[3]
    found.push({
      status,
      id,
      ...(tag === '[MANUAL]' || tag === '[INFRA]' ? { tag } : {}),
    })
  }

  return found
}

export const parseTasks = (text: string): TaskProgress => {
  const lines = taskLines(text)
  const counted = lines.filter(line => line.tag !== '[MANUAL]')
  const wip = lines.find(line => line.status === 'wip')?.id

  return {
    completed: counted.filter(line => line.status === 'x').length,
    total: counted.length,
    ...(wip === undefined ? {} : { wip }),
  }
}

const frontmatterStatus = (text: string): string | undefined => {
  const lines = stripBom(text).split(/\r?\n/)
  const first = lines.findIndex(line => line === '---')
  if (first < 0) return undefined
  const secondOffset = lines.slice(first + 1).findIndex(line => line === '---')
  if (secondOffset < 0) return undefined
  const second = first + secondOffset + 1

  for (const line of lines.slice(first + 1, second)) {
    const match = /^status:[ \t]*(.*?)[ \t]*$/.exec(line)
    if (match !== null) return match[1]
  }

  return undefined
}

export const phaseOf = (files: StddFiles): StddPhase => {
  if (files.designUx !== undefined && files.spec === undefined) return 'uiux'
  if (files.spec === undefined || frontmatterStatus(files.spec) !== 'approved') return 'spec (draft)'
  if (files.tasks === undefined) return 'plan'

  const lines = taskLines(files.tasks)
  return lines.some(line => line.status === ' ' || line.status === 'wip') ? 'execute' : 'done'
}

export const pickNewestChange = (candidates: readonly StddCandidate[]): StddProgressView | null => {
  const ordered = candidates
    .filter(candidate => ARTIFACTS.some(name => {
      if (name === 'design-ux.md') return candidate.files.designUx !== undefined
      if (name === 'spec.md') return candidate.files.spec !== undefined
      return candidate.files.tasks !== undefined
    }))
    .slice()
    .sort((left, right) => right.mtimeMs - left.mtimeMs)

  for (const candidate of ordered) {
    const phase = phaseOf(candidate.files)
    if (phase === 'done') continue
    const tasks = candidate.files.tasks === undefined
      ? { completed: 0, total: 0 }
      : parseTasks(candidate.files.tasks)

    return { name: candidate.name, phase, ...tasks }
  }

  return null
}

const PHASE_COLORS: Record<StddProgressView['phase'], ThemeKey> = {
  uiux: 'merged',
  'spec (draft)': 'warning',
  plan: 'suggestion',
  execute: 'success',
}

export const progressSegments = (view: StddProgressView, columns: number | undefined): Segment[][] => {
  const lines: Segment[][] = [[
    { text: 'STDD', color: 'claude', bold: true },
    { text: ' ' },
    { text: view.name, color: 'text', bold: true },
    { text: ' · ', color: 'subtle' },
    { text: view.phase, color: PHASE_COLORS[view.phase] },
  ]]
  if (view.phase !== 'execute') return lines

  const width = columns === undefined ? 24 : Math.max(4, Math.min(24, columns - 30))
  const ratio = view.total === 0 ? 0 : view.completed / view.total
  const filled = Math.max(0, Math.min(width, Math.round(width * ratio)))
  const hasWipCell = view.wip !== undefined && filled < width
  lines.push([
    { text: '▓'.repeat(filled), color: 'success' },
    { text: hasWipCell ? '▓' : '', color: 'warning' },
    { text: '░'.repeat(width - filled - (hasWipCell ? 1 : 0)), color: 'inactive' },
    { text: ' ' },
    { text: `${view.completed}/${view.total}`, color: 'text', bold: true },
    { text: ' tasks', color: 'subtle' },
    ...(view.wip === undefined ? [] : [{ text: ` · wip ${view.wip}`, color: 'warning' as const }]),
  ])

  return lines
}

export const formatProgress = (view: StddProgressView, columns: number | undefined): string[] =>
  progressSegments(view, columns).map(line => line.map(segment => segment.text).join(''))

const parentOf = (path: string): string | null => {
  const trimmed = path.length > 1 ? path.replace(/\/+$/, '') : path
  if (trimmed === '/') return null
  const cut = trimmed.lastIndexOf('/')
  return cut <= 0 ? '/' : trimmed.slice(0, cut)
}

export const scanProgress = async (cwd: string, fs: ProgressFs): Promise<StddProgressView | null> => {
  let directory: string | null = cwd
  let stddRoot: string | undefined

  while (directory !== null) {
    const entries = await fs.list(directory)
    if (entries.some(entry => entry.name === 'STDD' && entry.kind === 'dir')) {
      stddRoot = directory === '/' ? '/STDD' : `${directory}/STDD`
      break
    }
    directory = parentOf(directory)
  }

  if (stddRoot === undefined) return null

  const candidates: StddCandidate[] = []
  const changes = await fs.list(stddRoot)
  for (const change of changes) {
    if (change.kind !== 'dir') continue
    const changePath = `${stddRoot}/${change.name}`
    const entries = await fs.list(changePath)
    const artifacts = entries.filter(entry =>
      entry.kind === 'file' && ARTIFACTS.some(name => name === entry.name),
    )
    if (artifacts.length === 0) continue

    const files: StddFiles = {}
    for (const artifact of artifacts) {
      const path = `${changePath}/${artifact.name}`
      if (artifact.name === 'design-ux.md') files.designUx = ''
      if (artifact.name === 'spec.md') files.spec = await fs.read(path)
      if (artifact.name === 'tasks.md') files.tasks = await fs.read(path)
    }

    candidates.push({
      name: change.name,
      mtimeMs: Math.max(...artifacts.map(artifact => artifact.mtimeMs)),
      files,
    })
  }

  // Do not recompute custody fingerprints here: /stdd remains the authority.
  return pickNewestChange(candidates)
}
