import { casUpdate } from '../../state'
import type { PlanDeclaration } from '../../../../types'
import type { Segment } from '../../segment'
import { barSegments, checklistProgressSegments, normalizedPath } from '../progress'
import { createPlanCompletion } from '../planCompletion'
import { succeeded } from '../shared'
import { createRememberedChecklist } from './checklist'
import type { ProgressReadIo, ProgressSource } from './source'

const LEDGER_PATH = /(?:^|[\s"'`=(>])((?:(?:[A-Za-z]:)?\/)?[^\s"'`><;|&()]*\.superpowers\/sdd\/[^/\s"'`><;|&()]+\/progress\.md)(?=$|[\s"'`;|&()])/i
const TASK_HEADING = /^###\s+Task\s+(\d+):\s*(.*?)\s*$/gim
const TASK_COMPLETE = /^.*?Task\s+(\d+):\s*complete\b.*$/i
const TASK_STARTED = /^Task\s+(\d+):\s*(?:in progress|in-progress|started)\b.*$/i
const LEDGER_IDENTITY = /^# SDD ledger\s+(?:—|-)\s+plan:\s*(.*?)\s*$/i

type LedgerProgress = {
  completed: number
  total: number
  wip?: string
}

const absolutePath = (cwd: string, path: string): string => {
  const normalized = normalizedPath(path)
  if (normalized.startsWith('/') || /^[A-Za-z]:\//.test(normalized)) return normalized
  const root = normalizedPath(cwd)
  return root === '/' ? `/${normalized}` : `${root}/${normalized}`
}

const basename = (path: string): string => {
  const normalized = normalizedPath(path)
  return normalized.slice(normalized.lastIndexOf('/') + 1)
}

type ShellToken = {
  kind: 'word' | 'operator'
  value: string
}

type HeredocSpec = { delimiter: string; stripTabs: boolean }

// Reads the delimiter word after `<<`; returns the index just past it.
const heredocDelimiter = (command: string, from: number): { spec: HeredocSpec; end: number } => {
  let index = from
  const stripTabs = command[index] === '-'
  if (stripTabs) index += 1
  while (command[index] === ' ' || command[index] === '\t') index += 1
  let delimiter = ''
  let quote: "'" | '"' | undefined
  for (; index < command.length; index += 1) {
    const character = command[index]
    if (character === undefined) break
    if (quote !== undefined) {
      if (character === quote) quote = undefined
      else delimiter += character
    } else if (character === "'" || character === '"') {
      quote = character
    } else if (character === '\\' && command[index + 1] !== undefined) {
      index += 1
      delimiter += command[index] ?? ''
    } else if (/\s/.test(character) || '<>|&;()'.includes(character)) {
      break
    } else {
      delimiter += character
    }
  }
  return { spec: { delimiter, stripTabs }, end: index }
}

// Consumes pending heredoc bodies after the newline at `newline`; returns the index to resume from.
const skipHeredocBodies = (command: string, newline: number, pending: HeredocSpec[]): number => {
  let position = newline + 1
  for (const spec of pending.splice(0)) {
    while (position < command.length) {
      const lineEnd = command.indexOf('\n', position)
      const end = lineEnd < 0 ? command.length : lineEnd
      const line = command.slice(position, end)
      position = lineEnd < 0 ? command.length : lineEnd + 1
      if ((spec.stripTabs ? line.replace(/^\t+/, '') : line) === spec.delimiter) break
    }
  }
  return position - 1
}

const shellTokens = (command: string): ShellToken[] => {
  const tokens: ShellToken[] = []
  let word = ''
  let hasWord = false
  let quote: "'" | '"' | undefined
  const heredocs: Array<{ delimiter: string; stripTabs: boolean }> = []

  const flushWord = (): void => {
    if (!hasWord) return
    tokens.push({ kind: 'word', value: word })
    word = ''
    hasWord = false
  }

  for (let index = 0; index < command.length; index += 1) {
    const character = command[index]
    if (character === undefined) continue
    if (quote !== undefined) {
      if (character === quote) {
        quote = undefined
      } else if (character === '\\' && quote === '"' && command[index + 1] !== undefined) {
        index += 1
        word += command[index] ?? ''
      } else {
        word += character
      }
      hasWord = true
      continue
    }

    if (character === "'" || character === '"') {
      quote = character
      hasWord = true
      continue
    }
    if (character === '\\' && command[index + 1] !== undefined) {
      index += 1
      word += command[index] ?? ''
      hasWord = true
      continue
    }
    if (character === '#' && !hasWord) {
      while (command[index + 1] !== undefined && command[index + 1] !== '\n') index += 1
      continue
    }
    if (/\s/.test(character)) {
      flushWord()
      if (character === '\n') {
        tokens.push({ kind: 'operator', value: ';' })
        index = skipHeredocBodies(command, index, heredocs)
      }
      continue
    }
    if ('<>|&;'.includes(character)) {
      flushWord()
      if (character === '>' && command[index + 1] === '|') {
        tokens.push({ kind: 'operator', value: '>' })
        index += 1
        continue
      }
      if (character === '<' && command[index + 1] === '<' && command[index + 2] !== '<') {
        const heredoc = heredocDelimiter(command, index + 2)
        tokens.push({ kind: 'operator', value: '<<' })
        heredocs.push(heredoc.spec)
        index = heredoc.end - 1
        continue
      }
      const doubled = command[index + 1] === character && character !== ';'
      tokens.push({ kind: 'operator', value: doubled ? character.repeat(2) : character })
      if (doubled) index += 1
      continue
    }
    word += character
    hasWord = true
  }
  flushWord()
  return tokens
}

type BashWrite = {
  ledger?: string
  mayWrite: boolean
}

const isLedgerPath = (path: string): boolean => LEDGER_PATH.test(`/${normalizedPath(path)}`)

const SUDO_ARG_FLAGS = new Set(['-u', '-g', '-h', '-p', '-r', '-t', '-C', '-U', '-D', '-R'])

// Returns the index of the last sudo-prefix token, so the next token is read as the command.
const skipSudoPrefix = (tokens: ShellToken[], sudoIndex: number): number => {
  let index = sudoIndex
  for (;;) {
    const next = tokens[index + 1]
    if (next === undefined || next.kind !== 'word') return index
    if (next.value.startsWith('-') && next.value !== '--') {
      index += SUDO_ARG_FLAGS.has(next.value) ? 2 : 1
    } else if (next.value === '--' || /^[A-Za-z_][A-Za-z0-9_]*=/.test(next.value)) {
      index += 1
    } else {
      return index
    }
  }
}

const bashWriteFrom = (command: string): BashWrite => {
  const tokens = shellTokens(command)
  let mayWrite = false
  let expectingCommand = true

  for (let index = 0; index < tokens.length; index += 1) {
    const token = tokens[index]
    if (token === undefined) continue
    if (token.kind === 'operator') {
      if (token.value === '>' || token.value === '>>') {
        mayWrite = true
        const target = tokens[index + 1]
        if (target?.kind === 'word') {
          if (isLedgerPath(target.value)) return { ledger: target.value, mayWrite }
          index += 1
        }
      } else if (token.value === '|' || token.value === '||' || token.value === '&&' || token.value === ';') {
        expectingCommand = true
      }
      continue
    }

    if (!expectingCommand) continue
    if (/^[A-Za-z_][A-Za-z0-9_]*=/.test(token.value)) continue
    if (basename(token.value) === 'sudo') {
      index = skipSudoPrefix(tokens, index)
      continue
    }
    expectingCommand = false
    if (basename(token.value) !== 'tee') continue
    mayWrite = true

    for (let operandIndex = index + 1; operandIndex < tokens.length; operandIndex += 1) {
      const operand = tokens[operandIndex]
      if (operand === undefined || operand.kind === 'operator') break
      if (operand.value === '--' || operand.value.startsWith('-')) continue
      if (isLedgerPath(operand.value)) return { ledger: operand.value, mayWrite }
    }
  }

  return { mayWrite }
}

const ledgerPathFrom = (event: Readonly<Record<string, unknown>>): string | undefined => {
  const tool = String(event.tool)
  const candidate = tool === 'Bash' && typeof event.command === 'string'
    ? bashWriteFrom(event.command).ledger
    : (tool === 'Write' || tool === 'Edit' || tool === 'MultiEdit') && typeof event.file_path === 'string'
      ? event.file_path
      : undefined
  if (candidate === undefined) return undefined
  return isLedgerPath(candidate) ? candidate : undefined
}

const mayWriteFromBash = (command: string): boolean => bashWriteFrom(command).mayWrite

export const needsRecentLedgerDiscovery = (event: Readonly<Record<string, unknown>>): boolean =>
  event.agentId === undefined &&
  event.tool === 'Bash' &&
  typeof event.command === 'string' &&
  ledgerPathFrom(event) === undefined &&
  mayWriteFromBash(event.command)

const recentLedger = async (
  cwd: string,
  callStartedAt: number,
  io: ProgressReadIo,
): Promise<string | undefined> => {
  const sddRoot = absolutePath(cwd, '.superpowers/sdd')
  const candidates: Array<{ path: string; mtimeMs: number }> = []
  const changes = await io.list(sddRoot)
  for (const change of changes) {
    if (change.kind !== 'dir') continue
    const changePath = `${sddRoot}/${change.name}`
    try {
      const ledger = (await io.list(changePath)).find(entry => entry.kind === 'file' && entry.name === 'progress.md')
      if (ledger !== undefined && ledger.mtimeMs >= callStartedAt - 1000) {
        candidates.push({ path: `${changePath}/progress.md`, mtimeMs: ledger.mtimeMs })
      }
    } catch {
      // One unreadable change directory does not hide other recent ledgers.
    }
  }

  return candidates.sort((left, right) => right.mtimeMs - left.mtimeMs)[0]?.path
}

const identityPlan = (ledgerPath: string, ledgerText: string): string | undefined => {
  const firstLine = ledgerText.split(/\r?\n/, 1)[0]
  if (firstLine === undefined) return undefined
  const declared = LEDGER_IDENTITY.exec(firstLine)?.[1]
  if (declared === undefined || declared === '') return undefined
  if (declared.startsWith('/') || /^[A-Za-z]:\//.test(declared)) return normalizedPath(declared)

  const normalizedLedger = normalizedPath(ledgerPath)
  const marker = '/.superpowers/sdd/'
  const markerAt = normalizedLedger.indexOf(marker)
  if (markerAt < 0) return undefined
  return absolutePath(normalizedLedger.slice(0, markerAt) || '/', declared)
}

const ledgerProgress = (plan: string, ledger: string): LedgerProgress => {
  const planned = [...plan.matchAll(TASK_HEADING)].flatMap(match => {
    const id = match[1]
    const heading = match[2]
    return id === undefined || heading === undefined ? [] : [{ id, heading }]
  })
  const status = new Map<string, 'complete' | 'started'>()
  for (const line of ledger.split(/\r?\n/)) {
    const completedId = TASK_COMPLETE.exec(line)?.[1]
    if (completedId !== undefined) {
      status.set(completedId, 'complete')
      continue
    }
    const startedId = TASK_STARTED.exec(line)?.[1]
    if (startedId !== undefined) status.set(startedId, 'started')
  }
  const completed = new Set(
    [...status].flatMap(([id, value]) => value === 'complete' ? [id] : []),
  )
  const started = new Set(
    [...status].flatMap(([id, value]) => value === 'started' ? [id] : []),
  )
  const active = planned.filter(task => started.has(task.id) && !completed.has(task.id))
  const first = active[0]
  const wip = first === undefined
    ? undefined
    : `${first.heading}${active.length > 1 ? ` +${active.length - 1} in progress` : ''}`

  return {
    completed: planned.filter(task => completed.has(task.id)).length,
    total: planned.length,
    ...(wip === undefined ? {} : { wip }),
  }
}

const ledgerSegments = (
  path: string,
  progress: LedgerProgress,
  columns: number | undefined,
): Segment[][] => [[
  { text: 'Plan', color: 'claude', bold: true },
  { text: ' · ', color: 'subtle' },
  { text: basename(path), color: 'text' },
  { text: ' · ', color: 'subtle' },
  { text: `${progress.completed}/${progress.total}`, color: 'text', bold: true },
  { text: ' tasks', color: 'subtle' },
], [
  ...barSegments({ completed: progress.completed, total: progress.total, hasInProgress: progress.wip !== undefined }, columns),
  ...(progress.wip === undefined
    ? []
    : [{ text: ` · ▶ ${progress.wip}`, color: 'warning' as const }]),
]]

const declarationPlan = async (
  declaration: PlanDeclaration,
  io: ProgressReadIo,
): Promise<string | undefined> => {
  if (declaration.plan !== undefined) return declaration.plan
  return (await io.getPlanChecklist()).value?.path
}

export const createDeclaredSource = (autocloseSeconds = -1): ProgressSource => {
  const rememberedChecklist = createRememberedChecklist()
  const completion = createPlanCompletion(autocloseSeconds)
  const finishedLedgers = new Map<string, number>()

  const rememberedTotal = async (path: string, io: ProgressReadIo): Promise<number | undefined> => {
    const key = normalizedPath(path)
    const local = finishedLedgers.get(key)
    if (local !== undefined) return local
    try {
      const saved = (await io.getPlanFinishedLedgers?.())?.value?.find(ledger => ledger.path === key)
      if (saved !== undefined) finishedLedgers.set(key, saved.total)
      return saved?.total
    } catch {
      return undefined
    }
  }

  const rememberFinished = async (path: string, total: number, io: ProgressReadIo): Promise<void> => {
    const key = normalizedPath(path)
    finishedLedgers.set(key, total)
    if (io.getPlanFinishedLedgers === undefined || io.setPlanFinishedLedgers === undefined) return
    try {
      await casUpdate(
        io.getPlanFinishedLedgers,
        io.setPlanFinishedLedgers,
        current => {
          const previous = current ?? []
          const saved = previous.find(ledger => ledger.path === key)
          if (saved?.total === total) return null
          return { value: [...previous.filter(ledger => ledger.path !== key), { path: key, total }] }
        },
      )
    } catch {
      // The in-memory finished view remains usable if session state is unavailable.
    }
  }

  return {
    id: 'planDeclared',
    onToolCall: async (event, result, io) => {
      if (!succeeded(result)) return
      const tool = String(event.tool)
      if (tool !== 'Write' && tool !== 'Edit' && tool !== 'MultiEdit' && tool !== 'Bash') return
      if (event.agentId !== undefined) {
        io.invalidate()
        return
      }

      const cwd = await io.cwd()
      let ledger = ledgerPathFrom(event)
      if (ledger === undefined && needsRecentLedgerDiscovery(event)) {
        const callStartedAt = typeof event.callStartedAt === 'number' ? event.callStartedAt : await io.now()
        try {
          ledger = await recentLedger(cwd, callStartedAt, io)
        } catch {
          // A failed discovery falls back to refresh-only behavior.
        }
      }

      if (ledger === undefined) {
        io.invalidate()
        return
      }

      const ledgerPath = absolutePath(cwd, ledger)
      const selected = (await io.getPlanChecklist()).value?.path
      let plan = selected
      try {
        plan = identityPlan(ledgerPath, await io.read(ledgerPath)) ?? selected
      } catch {
        // A missing identity keeps today's checklist-plan fallback.
      }
      const declaration: PlanDeclaration = {
        ...(plan === undefined ? {} : { plan }),
        progress: 'ledger',
        ledger: ledgerPath,
      }
      await casUpdate(
        io.getPlanDeclaration,
        io.setPlanDeclaration,
        current => current?.progress === declaration.progress &&
          current.plan === declaration.plan && current.ledger === declaration.ledger
          ? null
          : { value: declaration },
      )
      io.invalidate()
    },
    lines: async (io, columns) => {
      try {
        const declaration = (await io.getPlanDeclaration()).value
        if (declaration === undefined) return undefined
        const planPath = await declarationPlan(declaration, io)
        if (planPath === undefined) return undefined
        const planText = await io.read(planPath)

        if (declaration.progress === 'checklist') {
          const view = rememberedChecklist.parse(planPath, planText)
          if (view.checklist.total === 0) return undefined
          const complete = view.checklist.completed >= view.checklist.total
          const visible = await completion.observe(normalizedPath(planPath), complete, io)
          if (complete && !visible) return null
          return checklistProgressSegments(planPath, view.checklist, columns)
        }

        let progress: LedgerProgress
        try {
          progress = ledgerProgress(planText, await io.read(declaration.ledger))
        } catch {
          const total = await rememberedTotal(declaration.ledger, io)
          if (total === undefined) return undefined
          progress = { completed: total, total }
        }
        if (progress.total === 0) return undefined
        const complete = progress.completed >= progress.total
        if (complete) await rememberFinished(declaration.ledger, progress.total, io)
        const visible = await completion.observe(normalizedPath(planPath), complete, io)
        if (complete && !visible) return null
        return ledgerSegments(planPath, progress, columns)
      } catch {
        return undefined
      }
    },
  }
}
