import type { Register } from 'claude-code'

import type { FellowshipAgent } from '../../../types'
import { casUpdate } from '../state'
import {
  recordStepTokens,
  completeAgent,
  hasRunning,
  iconFor,
  isKnown,
  isRoleName,
  parseMaxRows,
  parseFrontmatter,
  register as registerAgent,
  rowSegments,
  selectPaneRows,
  statusOf,
  update,
} from './fellowship'

const PANE = 'tlor-fellowship'
const TITLE = 'Fellowship'
const agents = { plugin: 'tlor', key: 'agents' } as const

export const register: Register = (on, options) => {
  const opensAutomatically = options.fellowship === 'auto'
  const maxRows = parseMaxRows(options.fellowship_max_rows)
  let isOpened = false
  let ticker: { cancel: () => void } | undefined
  // role type -> its pinned frontmatter, read once per type
  const pinned = new Map<string, { model?: string; effort?: string }>()
  // agents whose effort the first turn.step already settled
  const stepped = new Set<string>()

  on('session.start', async ($, e, next) => {
    try {
      await $.command.register({
        name: 'fellowship',
        description: 'Open the Fellowship pane listing this session\'s subagents',
      })
      if (await $.store.get('fellowshipNoticeShown') === undefined) {
        $.ui.toast('Fellowship pane: /fellowship')
        await $.store.set('fellowshipNoticeShown', true)
      }
    } catch {
      // The observer is optional; session startup must continue.
    }

    return next(e)
  })

  on('command.run', { command: 'fellowship' }, async $ => {
    isOpened = true
    await $.ui.open({ id: PANE, title: TITLE })

    return { text: 'Fellowship pane opened.' }
  })

  on('agent.spawn', async ($, e, next) => {
    const result = await next(e)
    const id = result.agentId

    if (id !== undefined) {
      try {
        const now = await $.clock.now()
        let found = pinned.get(e.subagentType)
        if (found === undefined) {
          found = {}
          try {
            if (isRoleName(e.subagentType)) {
              const cwd = await $.session.cwd()
              const home = await $.env.get('HOME')
              const paths = [`${cwd}/.claude/agents/${e.subagentType}.md`]
              if (home !== undefined) paths.push(`${home}/.claude/agents/${e.subagentType}.md`)
              for (const path of paths) {
                if (await $.fs.exists(path)) {
                  found = parseFrontmatter(await $.fs.read(path))
                  break
                }
              }
            }
          } catch {
            // no readable role file: model and effort stay unknown
          }
          pinned.set(e.subagentType, found)
        }
        const model = e.model ?? result.model ?? found.model
        await casUpdate(
          () => $.state.get(agents),
          (value, version) => $.state.set(agents, value, { ifVersion: version }),
          value => ({
            value: registerAgent(value ?? [], {
              id,
              type: e.subagentType,
              description: e.description,
              status: 'running',
              startedAt: now,
              endedAt: null,
              tokens: 0,
              tools: 0,
              model,
              effort: found.effort,
            }),
          }),
        )

        if (opensAutomatically && !isOpened) {
          isOpened = true
          await $.ui.open({ id: PANE, title: TITLE })
        }

        if (ticker === undefined) {
          ticker = $.clock.every(1000, () => {
            void (async () => {
              try {
                const { value = [] } = await $.state.get(agents)
                if (hasRunning(value)) {
                  $.ui.invalidate('ui.render')
                } else {
                  ticker?.cancel()
                  ticker = undefined
                }
              } catch {
                ticker?.cancel()
                ticker = undefined
              }
            })()
          })
        }
      } catch {
        // observing only: never break the spawn
      }
    }

    return result
  }).catch(($, e, next) => next(e))

  on('tool.call', async ($, e, next) => {
    if (e.agentId !== undefined) {
      try {
        const id = e.agentId
        await casUpdate(
          () => $.state.get(agents),
          (value, version) => $.state.set(agents, value, { ifVersion: version }),
          value => ({ value: update(value ?? [], id, one => ({ ...one, tools: one.tools + 1 })) }),
        )
      } catch {
        // observing only: never break the call
      }
    }

    return next(e)
  }).catch(($, e, next) => next(e))

  on('turn.step', async function* ($, e, next) {
    const result = yield* next(e)
    const id = e.agentId
    if (id !== undefined) {
      try {
        const shouldFillDetails = !stepped.has(id)
        const didStep = await casUpdate(
          () => $.state.get(agents),
          (value, version) => $.state.set(agents, value, { ifVersion: version }),
          value => {
            const current = value ?? []
            if (!isKnown(current, id)) return null
            const withTokens = recordStepTokens(current, id, result.usage)
            const list = shouldFillDetails
              ? update(withTokens, id, one => ({
                  ...one,
                  model: one.model ?? e.model,
                  effort: e.effort === undefined ? one.effort : String(e.effort),
                }))
              : withTokens

            return { value: list }
          },
        )
        if (didStep && shouldFillDetails) stepped.add(id)
      } catch {
        // observing only: never break the response
      }
    }

    return result
  })

  on('turn.complete', async ($, e, next) => {
    if (e.agentId !== undefined) {
      try {
        const id = e.agentId
        const now = await $.clock.now()
        await casUpdate(
          () => $.state.get(agents),
          (value, version) => $.state.set(agents, value, { ifVersion: version }),
          value => ({ value: completeAgent(value ?? [], id, statusOf(e.reason), now) }),
        )
      } catch {
        // observing only: never break the turn
      }
    }

    return next(e)
  })

  // Prefix the Agent row with the role icon by rewriting the row's description; the engine still draws the row.
  on('ui.render', { component: 'ToolUse', props: { tool: 'Agent' } }, ($, e, next) => {
    const input = e.props.input as { subagent_type?: string; description?: string } | null
    if (input === null || typeof input !== 'object' || typeof input.description !== 'string') {
      return next(e)
    }
    const icon = iconFor(input.subagent_type)

    return next({
      ...e,
      props: { ...e.props, input: { ...input, description: `${icon} ${input.description}` } },
    })
  })

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const { Box, Text } = $.ui.resolve(e)
    const { value: list = [] } = await $.state.get(agents)
    const now = await $.clock.now()
    const room = Math.max(0, (e.viewport?.rows ?? 24) - 4)
    const selection = selectPaneRows(list, maxRows, room)

    return (
      <Box flexDirection="column">
        {selection.running.length === 0 && selection.completed.length === 0 &&
          selection.hiddenRunning === 0 && selection.hiddenCompleted === 0 && <Text dimColor>No subagents yet.</Text>}
        {selection.running.map(agent => (
          <Box flexDirection="row">
            {rowSegments(agent, now).map(segment => (
              <Text color={segment.color} bold={segment.bold} dimColor={segment.dim}>{segment.text}</Text>
            ))}
          </Box>
        ))}
        {selection.hiddenRunning > 0 && <Text color="warning" dimColor>+{selection.hiddenRunning} running</Text>}
        {selection.completed.map(agent => (
          <Box flexDirection="row">
            {rowSegments(agent, now).map(segment => (
              <Text color={segment.color} bold={segment.bold} dimColor={segment.dim}>{segment.text}</Text>
            ))}
          </Box>
        ))}
      </Box>
    )
  })
}
