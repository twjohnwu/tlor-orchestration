import type { RenderChildren } from 'claude-code'

const isElement = (node: unknown): node is { type?: unknown, children?: unknown, props?: { children?: unknown } } =>
  typeof node === 'object' && node !== null && !Array.isArray(node)

// All text a node shows, concatenated: strings, numbers, and every nested element's children.
const shownText = (node: unknown): string => {
  if (typeof node === 'string') return node
  if (typeof node === 'number') return String(node)
  if (Array.isArray(node)) return node.map(shownText).join('')
  if (!isElement(node)) return ''

  return shownText(node.children ?? node.props?.children)
}

// One entry per drawn line: each Text element is a line, a Box or list contributes its children's
// lines, and a bare string is a line of its own. Empty values (null, undefined, booleans) draw nothing.
export const renderedTextLines = (node: RenderChildren): string[] => {
  if (typeof node === 'string' || typeof node === 'number') return [String(node)]
  if (Array.isArray(node)) return node.flatMap(child => renderedTextLines(child))
  if (!isElement(node)) return []
  if (node.type === 'Text') return [shownText(node)]

  return renderedTextLines((node.children ?? node.props?.children) as RenderChildren)
}
