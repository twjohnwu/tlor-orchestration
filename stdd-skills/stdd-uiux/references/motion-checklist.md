# Motion checklist — distilled

Bundled reference for `stdd-uiux` Step 5's `Motion & feedback` section and
Step 7 items 11–13. Distilled from
[emilkowalski/skills](https://github.com/emilkowalski/skills) (MIT,
Copyright (c) 2026 Emil Kowalski). Only design-level rules are kept — the
ones a `design-ux.md` can state before any code exists. CSS, animation
library, and platform-specific implementation techniques belong to the build
phase and are deliberately left out. Like the anti-pattern checklist, this is
a floor, not a taste ceiling.

## 1. Should it animate? (frequency gate first, then purpose)

1. **Frequency gate** — how often does a user trigger this interaction?

   | Frequency | Motion budget |
   |---|---|
   | 100+ times a day (typing, list navigation, command palette) | none |
   | tens of times a day (hover, list add/remove) | remove, or reduce to a short fade |
   | occasional (modal, drawer, toast) | standard motion |
   | rare or first-time (onboarding, celebration) | room for delight |

   Common mistake: a lovely 300ms transition on the action the user repeats
   all day, which reads as lag by the tenth time.
2. **Keyboard-initiated actions do not animate.** Common mistake: animating
   a shortcut-driven list selection, so keyboard users wait on the mouse
   users' polish.
3. **Name the purpose** — one of: spatial continuity (where did it come
   from / go), state indication, explanation, feedback, or softening an
   otherwise jarring change. Common mistake: the only honest purpose is
   "looks nice" on a frequent interaction — cut it.

## 2. Timing budget

| Interaction | Duration |
|---|---|
| Press feedback | 100–160ms |
| Tooltip, small popover | 125–200ms |
| Dropdown, select | 150–250ms |
| Modal, drawer | 200–500ms |

- Keep ordinary UI motion under 300ms; the modal/drawer range is the
  exception, not the norm.
- Exits are faster than entrances. Be slow only where the user is deciding
  (e.g. a hold-to-confirm), fast where the system responds.
- Common mistake: one global 300ms for everything, so small elements feel
  sluggish and large ones feel abrupt.

## 3. Easing decision

| Motion | Easing |
|---|---|
| Entering or leaving the screen | ease-out (the default) |
| Moving within the screen | ease-in-out |
| Hover, color change | ease |
| Constant motion (progress, spinner) | linear |

- Never ease-in for UI motion: it starts slow exactly when the user is
  watching for a response.
- Common mistake: five hand-typed curves that almost match — declare the
  curves once as tokens and reference them.

## 4. Interaction feel

- **Press state** — pressable elements give immediate feedback on press
  (a slight scale-down, about 0.95–0.98), responding on pointer-down, not
  on release.
- **Nothing appears from nothing** — entering elements start near full size
  (about 0.9–0.97) with opacity 0, never from scale 0.
- **Origin-aware** — popovers and menus grow from their trigger; centered
  modals are the exception.
- **Interruptible** — a user can reverse or redirect any motion mid-flight
  (close a drawer while it is opening) without waiting for it to finish.
- **Personality fit** — bounce and playfulness match the product; a
  finance or admin tool rarely wants bounce at all.
- **Stagger is decorative** — a staggered list entrance (30–80ms steps)
  never blocks interaction with items already visible.

## 5. Accessibility

- **Reduced motion means less, not none.** Under `prefers-reduced-motion`,
  drop movement and scaling, keep short opacity/color transitions so state
  changes stay perceivable. Common mistake: switching every transition off,
  so a panel pops in with no cue at all.
- **Reduced motion ships with the motion**, in the same design section and
  the same change — never a follow-up ticket.
- **Hover-only affordances need a touch and keyboard equivalent.** Common
  mistake: actions revealed only on hover, invisible on a phone and
  unreachable by keyboard.
