# Interface design rationale — 1.3

The goal is easier scanning, not manipulating perception or implying certainty.

- **Progressive disclosure:** overview shows source freshness, two separate accounts and three analysis paths. Technical narratives and documentation stay behind explicit controls. Ten modules remain available. This follows Nielsen Norman Group's recommendation to surface primary information while deferring secondary detail: https://www.nngroup.com/articles/progressive-disclosure/
- **Reflow:** mobile navigation becomes a drawer; controls wrap; settings inputs fit the viewport. Wide financial tables scroll inside their own labeled, keyboard-focusable containers instead of shrinking text or forcing the whole page sideways. WCAG distinguishes essential two-dimensional tables from the surrounding content that must reflow: https://www.w3.org/WAI/WCAG22/Understanding/reflow.html
- **Readable contrast:** neutral backgrounds, dark body text in light mode, optional dark mode, visible focus, text labels and semantic positive/negative states. Green/red are not the only indication: signs, labels and numbers remain visible. Contrast reference: https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html
- **Honest information hierarchy:** “Imported / end-of-day,” actual dates, rule scores instead of win probabilities, and scoped reconciliation separate from database integrity and cloud persistence. Blue is primarily an action/navigation cue; warning panels explain actual uncertainty rather than decorate every card.
- The system font stack avoids a remote font dependency. Themes follow the operating-system preference initially and can be changed. Header utility actions collapse into a mobile More menu. Financial numbers use tabular/monospaced styling where useful.

Research informed the redesign; local automated accessibility checks and visual review are not a claim of complete WCAG conformance or a substitute for user testing. The retained financial charts are historical views, not a new forecasting model.
