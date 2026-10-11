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

export type PlanTask = {
  id: string
  subject: string
  activeForm?: string
  status: 'pending' | 'in_progress' | 'completed'
}

export type ChecklistProgress = {
  completed: number
  total: number
  next?: string
}

export type ChecklistFileView = {
  path: string
  checklist: ChecklistProgress
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
const CHECKLIST_LINE = /^\s*[-*+] \[( |x|X)\] (.+)$/
const CHECKLIST_FENCE_LINE = /^\s*(`{3,}|~{3,})(.*)$/
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

type BarProgress = {
  completed: number
  total: number
  hasInProgress: boolean
}

export const barSegments = (progress: BarProgress, columns: number | undefined): Segment[] => {
  const width = columns === undefined ? 24 : Math.max(4, Math.min(24, columns - 30))
  const ratio = progress.total === 0 ? 0 : progress.completed / progress.total
  const filled = Math.max(0, Math.min(width, Math.round(width * ratio)))
  const hasWarningCell = progress.hasInProgress && filled < width

  return [
    { text: '▓'.repeat(filled), color: 'success' },
    { text: hasWarningCell ? '▓' : '', color: 'warning' },
    { text: '░'.repeat(width - filled - (hasWarningCell ? 1 : 0)), color: 'inactive' },
  ]
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

  lines.push([
    ...barSegments({ completed: view.completed, total: view.total, hasInProgress: view.wip !== undefined }, columns),
    { text: ' ' },
    { text: `${view.completed}/${view.total}`, color: 'text', bold: true },
    { text: ' tasks', color: 'subtle' },
    ...(view.wip === undefined ? [] : [{ text: ` · wip ${view.wip}`, color: 'warning' as const }]),
  ])

  return lines
}

export const formatProgress = (view: StddProgressView, columns: number | undefined): string[] =>
  progressSegments(view, columns).map(line => line.map(segment => segment.text).join(''))

const truncateLabel = (label: string): string => label.length <= 60 ? label : `${label.slice(0, 59)}…`

const checklistLabel = (label: string): string => {
  const withoutCode = label.replace(/`([^`]*)`/g, '$1')
  const withoutOpeningEmphasis = withoutCode.replace(/(^|\s)(?:\*\*|__|\*|_)(?=\S)/g, '$1')
  const withoutEmphasis = withoutOpeningEmphasis.replace(/(\S)(?:\*\*|__|\*|_)(?=\s|$)/g, '$1')
  return truncateLabel(withoutEmphasis.trim())
}

export const parseMarkdownChecklist = (text: string): ChecklistProgress => {
  const items: Array<{ checked: boolean; text: string }> = []
  let fence: { marker: '`' | '~'; width: number } | undefined

  for (const line of stripBom(text).split(/\r?\n/)) {
    const fenceMatch = CHECKLIST_FENCE_LINE.exec(line)
    if (fenceMatch !== null) {
      const delimiter = fenceMatch[1]
      if (delimiter !== undefined) {
        const marker = delimiter[0]
        if (fence === undefined && (marker === '`' || marker === '~')) {
          fence = { marker, width: delimiter.length }
        } else if (
          fence !== undefined &&
          marker === fence.marker &&
          delimiter.length >= fence.width &&
          (fenceMatch[2] ?? '').trim() === ''
        ) {
          fence = undefined
        }
      }
      continue
    }
    if (fence !== undefined) continue

    const match = CHECKLIST_LINE.exec(line)
    if (match === null || match[1] === undefined || match[2] === undefined) continue
    items.push({
      checked: match[1] === 'x' || match[1] === 'X',
      text: checklistLabel(match[2]),
    })
  }

  const next = items.find(item => !item.checked)?.text
  return {
    completed: items.filter(item => item.checked).length,
    total: items.length,
    ...(next === undefined ? {} : { next }),
  }
}

// The plan band shows only while some task is still open.
export const isPlanVisible = (tasks: readonly PlanTask[]): boolean =>
  tasks.length > 0 && tasks.some(task => task.status !== 'completed')

export const planProgressSegments = (tasks: readonly PlanTask[], columns: number | undefined): Segment[][] => {
  const completed = tasks.filter(task => task.status === 'completed').length
  const active = tasks.find(task => task.status === 'in_progress')
  const lines: Segment[][] = [[
    { text: 'Plan', color: 'claude', bold: true },
    { text: ' · ', color: 'subtle' },
    { text: `${completed}/${tasks.length}`, color: 'text', bold: true },
    { text: ' tasks', color: 'subtle' },
  ]]

  lines.push([
    ...barSegments({ completed, total: tasks.length, hasInProgress: active !== undefined }, columns),
    ...(active === undefined
      ? []
      : [{ text: ` · ▶ ${truncateLabel(active.activeForm ?? active.subject)}`, color: 'warning' as const }]),
  ])

  return lines
}

const basename = (path: string): string => {
  const normalized = path.replace(/\\/g, '/').replace(/\/+$/, '')
  return normalized.slice(normalized.lastIndexOf('/') + 1)
}

export const checklistProgressSegments = (
  path: string,
  checklist: ChecklistProgress,
  columns: number | undefined,
): Segment[][] => [[
  { text: 'Plan', color: 'claude', bold: true },
  { text: ' · ', color: 'subtle' },
  { text: basename(path), color: 'text' },
  { text: ' · ', color: 'subtle' },
  { text: `${checklist.completed}/${checklist.total}`, color: 'text', bold: true },
  { text: ' items', color: 'subtle' },
], [
  ...barSegments({
    completed: checklist.completed,
    total: checklist.total,
    hasInProgress: checklist.next !== undefined,
  }, columns),
  ...(checklist.next === undefined
    ? []
    : [{ text: ` · ▶ ${checklist.next}`, color: 'warning' as const }]),
]]

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
