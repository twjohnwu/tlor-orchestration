import type { Register } from 'claude-code'

import { register as registerFellowship } from './fellowship/register'
import { register as registerStddProgress } from './stdd-progress/register'

export const register: Register = (on, options) => {
  if (options.fellowship !== 'off') registerFellowship(on, options)
  if (options.stdd_progress !== 'off' || options.plan_progress === 'on' || options.plan_reminder === 'on') registerStddProgress(on, options)
}
