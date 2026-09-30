# Anti-pattern checklist — distilled

Bundled reference for `stdd-uiux` Step 7's mechanical self-review, distilled
from [pbakaus/impeccable](https://github.com/pbakaus/impeccable)
(Apache-2.0); items 11–13 come from `motion-checklist.md` (MIT, see that
file). This is a floor, not a taste ceiling: passing
every item means known common mistakes were avoided, not that the design
"looks good."

1. **Text/background contrast** — qualitative WCAG AA check. Common mistake:
   light-gray text on a white card that reads fine to the designer's eye but
   fails contrast for body copy.
2. **Touch target size** — mobile tappable area. Common mistake: icon-only
   buttons sized to the icon's visual bounds instead of a ≥44px tap area.
3. **Empty state** — explicitly defined. Common mistake: assuming "it'll
   just be an empty list" with no copy, illustration, or next action.
4. **Error state** — explicitly defined. Common mistake: a failed fetch
   silently rendering a blank section with no user-visible signal.
5. **Loading state** — explicitly defined. Common mistake: a generic spinner
   used everywhere instead of a skeleton that matches the eventual layout.
6. **Generic "AI-default" design** — gratuitous gradient cards, meaningless
   nested cards. Common mistake: wrapping every section in its own shadowed
   card "because it looks structured," with no information-architecture
   reason for the nesting.
7. **Design-token-backed spacing/alignment** — not ad-hoc numbers. Common
   mistake: one-off `margin: 13px` values sprinkled through a spec instead of
   referencing a defined spacing scale.
8. **Semantic color usage** — not decorative misuse. Common mistake: using
   the brand's error-red color for a merely decorative accent, so it no
   longer reliably signals "error" elsewhere.
9. **Typographic hierarchy** — consistent heading/body/caption distinction.
   Common mistake: two heading levels that render at visually identical
   sizes, so the hierarchy only exists in the markup, not on screen.
10. **Interaction states listed** — hover/focus/active/pressed/disabled at
    least named. Common mistake: only describing the default and hover
    states, leaving focus (keyboard) and disabled states undefined.
11. **Motion earns its place** — every animated interaction passes the
    frequency gate and names a purpose. Common mistake: animating the action
    users repeat all day, which reads as lag.
12. **Reduced motion defined** — drop movement, keep short fades. Common
    mistake: turning all motion off, so state changes lose their only cue.
13. **Motion from tokens** — durations and easings reference motion tokens.
    Common mistake: a different hand-typed duration on every component.
