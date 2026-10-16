import { casUpdate } from '../../state'
import type { PlanDeclaration } from '../../../../types'
import type { Segment } from '../../segment'
import { barSegments, checklistProgressSegments, normalizedPath } from '../progress'
import { createPlanCompletion } from '../planCompletion'
import { succeeded } from '../shared'
import { createRememberedChecklist } from './checklist'
import type { ProgressReadIo, ProgressSource } from './source'

const LEDGER_PATH = /(?:^|[\/\s"'`=(])(\.superpowers\/sdd\/[^/\s"'`]+\/progress\.md)(?=$|[\s"'`;|&()])/i
const TASK_HEADING = /^###\s+Task\s+(\d+):/gim
const TASK_COMPLETE = /^.*?Task\s+(\d+):\s*complete\b.*$/gim

const absolutePath = (cwd: string, path: string): string => {
  const normalized = normalizedPath(path)
  if (normalized.startsWith('/') || /^[A-Za-z]:\//.test(normalized)) return normalized
  return `${normalizedPath(cwd)}/${normalized}`
}

const basename = (path: string): string => {
  const normalized = normalizedPath(path)
  return normalized.slice(normalized.lastIndexOf('/') + 1)
}

const ledgerPathFrom = (event: Readonly<Record<string, unknown>>): string | undefined => {
  const tool = String(event.tool)
  const candidate = tool === 'Bash' && typeof event.command === 'string'
    ? LEDGER_PATH.exec(event.command.replace(/\\/g, '/'))?.[1]
    : (tool === 'Write' || tool === 'Edit' || tool === 'MultiEdit') && typeof event.file_path === 'string'
      ? event.file_path
      : undefined
  if (candidate === undefined) return undefined
  return LEDGER_PATH.test(`/${normalizedPath(candidate)}`) ? candidate : undefined
}

const ledgerProgress = (plan: string, ledger: string): { completed: number; total: number } => {
  const planned = [...plan.matchAll(TASK_HEADING)].map(match => match[1]).filter((id): id is string => id !== undefined)
  const completed = new Set(
    [...ledger.matchAll(TASK_COMPLETE)].map(match => match[1]).filter((id): id is string => id !== undefined),
  )
  return { completed: planned.filter(id => completed.has(id)).length, total: planned.length }
}

const ledgerSegments = (
  path: string,
  progress: { completed: number; total: number },
  columns: number | undefined,
): Segment[][] => [[
  { text: 'Plan', color: 'claude', bold: true },
  { text: ' · ', color: 'subtle' },
  { text: basename(path), color: 'text' },
  { text: ' · ', color: 'subtle' },
  { text: `${progress.completed}/${progress.total}`, color: 'text', bold: true },
  { text: ' tasks', color: 'subtle' },
], [
  ...barSegments({ completed: progress.completed, total: progress.total, hasInProgress: false }, columns),
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

  return {
    id: 'planDeclared',
    onToolCall: async (event, result, io) => {
      if (!succeeded(result)) return
      const ledger = ledgerPathFrom(event)
      if (ledger === undefined) {
        if (event.tool === 'Write' || event.tool === 'Edit' || event.tool === 'MultiEdit' || event.tool === 'Bash') {
          io.invalidate()
        }
        return
      }

      const cwd = await io.cwd()
      const selected = (await io.getPlanChecklist()).value?.path
      const declaration: PlanDeclaration = {
        ...(selected === undefined ? {} : { plan: selected }),
        progress: 'ledger',
        ledger: absolutePath(cwd, ledger),
      }
      const didUpdate = await casUpdate(
        io.getPlanDeclaration,
        io.setPlanDeclaration,
        current => current?.progress === declaration.progress &&
          current.plan === declaration.plan && current.ledger === declaration.ledger
          ? null
          : { value: declaration },
      )
      if (didUpdate) io.invalidate()
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

        const progress = ledgerProgress(planText, await io.read(declaration.ledger))
        if (progress.total === 0) return undefined
        const complete = progress.completed >= progress.total
        const visible = await completion.observe(normalizedPath(planPath), complete, io)
        if (complete && !visible) return null
        return ledgerSegments(planPath, progress, columns)
      } catch {
        return undefined
      }
    },
  }
}
