import type { Register } from 'claude-code'

import { register as registerFellowship, setupFellowship } from './fellowship/register'
import { register as registerStddProgress, setupPlanTrack } from './stdd-progress/register'

export const register: Register = (on, options) => {
  const fellowshipEnabled = options.fellowship !== 'off'
  const planTrackEnabled = options.plan_progress === 'on'
  // The plugin may hold one session.start hook, so both mods' startup work runs here.
  if (fellowshipEnabled || planTrackEnabled) {
    on('session.start', async ($, e, next) => {
      if (fellowshipEnabled) await setupFellowship($)
      if (planTrackEnabled) await setupPlanTrack($)

      return next(e)
    }).catch(($, e, next) => next(e))
  }
  if (fellowshipEnabled) registerFellowship(on, options)
  if (options.stdd_progress !== 'off' || planTrackEnabled || options.plan_reminder === 'on') registerStddProgress(on, options)
}
