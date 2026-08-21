# patterns.md — AI-writing-tell catalog (English)

Lazy-load reference for the article-writer role. Use as a BANNED LIST while
drafting (avoid every pattern below from the start) and as a DETECTION LIST
while editing (scan finished text for these before calling it done).

Source: humanizer skill (`~/.claude/skills/humanizer/SKILL.md`), based on
Wikipedia's "Signs of AI writing." The source catalog runs to 29 numbered
items, not 26 — carried through as-is rather than trimmed to match. Excludes
Markup, Citations, and Voice/Personality (shared core doc covers those).
Three native-English adaptations of patterns proven in the Chinese catalogs
are appended at the end.

## Content patterns

### 1. Undue emphasis on significance and legacy
Puffing up an ordinary fact by claiming it "marks a pivotal moment" or "reflects broader trends."
Before: "This marked a pivotal moment in regional statistics." → After: "This was the first regional statistics office independent of the national one."

### 2. Undue emphasis on notability and media coverage
Listing outlets or follower counts as proof of importance instead of using a specific citation.
Before: "Cited in the NYT, BBC, and FT. 500,000 followers." → After: "In a 2024 NYT interview, she argued regulation should focus on outcomes."

### 3. Superficial -ing analyses
Tacking a present-participle clause onto a sentence to fake depth.
Before: "...resonates with the region's beauty, symbolizing its heritage." → After: "The architect said the colors reference the local coastline."

### 4. Promotional/advertisement-like language
Travel-brochure adjectives (vibrant, stunning, nestled) replacing plain description.
Before: "Nestled in breathtaking Gonder, a vibrant town with rich heritage." → After: "A town in the Gonder region, known for its weekly market."

### 5. Vague attributions and weasel words
Citing "experts" or "observers" without naming a source.
Before: "Experts believe it plays a crucial ecological role." → After: "A 2019 Academy of Sciences survey found several endemic fish species."

### 6. Formulaic "Challenges and Future Prospects" sections
A boilerplate obstacles-then-optimism close.
Before: "Despite challenges, the town continues to thrive as it grows." → After: "Traffic congestion rose after three IT parks opened in 2015."

## Language and grammar patterns

### 7. Overused AI vocabulary
Words like delve, crucial, tapestry, landscape, underscore, showcase clustering together.
Before: "Additionally, an enduring testament to influence is showcased in the landscape." → After: "Pasta dishes, introduced during colonization, remain common."

### 8. Copula avoidance
Swapping "is/are" for "serves as," "stands as," "boasts."
Before: "The gallery serves as the space and boasts 3,000 square feet." → After: "The gallery is the space; it has 3,000 square feet."

### 9. Negative parallelisms and tailing negations
"Not just X, it's Y" constructions, or a fragment tacked on ending in a negation.
Before: "It's not just a song, it's a statement. No guessing required." → After: "The heavy beat sets the tone, and users see the source item directly."

### 10. Rule-of-three overuse
Forcing every list into exactly three items for false comprehensiveness.
Before: "Expect innovation, inspiration, and industry insights." → After: "There's also time for informal networking between sessions."

### 11. Elegant variation (synonym cycling)
Swapping in a new synonym each time to avoid repeating a noun.
Before: "The protagonist faces challenges. The main character overcomes them. The hero returns." → After: "The protagonist faces challenges but eventually returns home."

### 12. False ranges
"From X to Y" phrasing where X and Y aren't on any real scale.
Before: "From the Big Bang to the cosmic web, from stars to dark matter." → After: "The book covers the Big Bang, star formation, and dark matter."

### 13. Passive voice and subjectless fragments
Dropping the actor: "No configuration needed."
Before: "No configuration file needed. Results are preserved automatically." → After: "You don't need a config file; the system saves results automatically."

## Style patterns

### 14. Em dash overuse
Using em dashes where a comma or period reads more naturally.
Before: "Promoted by institutions—not by the people themselves." → After: "Promoted by institutions, not by the people themselves."

### 15. Overuse of boldface
Bolding phrases mechanically instead of for real emphasis.
Before: "It blends **OKRs** and **KPIs** with the **Business Model Canvas**." → After: "It blends OKRs, KPIs, and tools like the Business Model Canvas."

### 16. Inline-header vertical lists
Bulleted lists where each item opens with a bolded label and colon.
Before: "- **Performance:** Performance has been enhanced." → After: "The update speeds up load times through optimized algorithms."

### 17. Title case in headings
Capitalizing every main word in a heading.
Before: "## Strategic Negotiations And Global Partnerships" → After: "## Strategic negotiations and global partnerships"

### 18. Emojis
Decorating headings or bullets with emoji.
Before: "🚀 **Launch:** ships in Q3" → After: "The product launches in Q3."

### 19. Curly quotation marks
Using typographic quotes where the rest of the document uses straight ones.
Before: "He said "on track" but others disagreed." → After: 'He said "on track" but others disagreed.'

## Communication patterns

### 20. Collaborative-communication artifacts
Chatbot phrases like "I hope this helps!" or "Let me know" leaking into content.
Before: "Here is an overview. I hope this helps! Let me know if you want more." → After: "The revolution began in 1789 amid financial crisis and food shortages."

### 21. Knowledge-cutoff disclaimers
Hedging about incomplete training data instead of stating what's known.
Before: "While specific details are limited, it appears the company started in the 1990s." → After: "The company was founded in 1994, per its registration filing."

### 22. Sycophantic/servile tone
Praising the reader's question before answering it.
Before: "Great question! You're absolutely right that this is complex." → After: "The economic factors you mentioned matter here."

## Filler and hedging

### 23. Filler phrases
Wordy stock phrases that add no meaning.
Before: "In order to achieve this goal, due to the fact that it was raining" → After: "To achieve this, because it was raining"

### 24. Excessive hedging
Stacking qualifiers until the claim disappears.
Before: "It could potentially possibly be argued that it might have some effect." → After: "The policy may affect outcomes."

### 25. Generic positive conclusions
A vague upbeat close with no content.
Before: "The future looks bright. Exciting times lie ahead." → After: "The company plans to open two more locations next year."

### 26. Hyphenated word-pair overuse
Hyphenating common compounds with mechanical consistency.
Before: "The cross-functional, data-driven, client-facing report." → After: "The cross functional, data driven, client facing report."

### 27. Persuasive authority tropes
"The real question is," "at its core" — false cutting-through-noise framing.
Before: "The real question is whether teams can adapt. At its core, what matters is readiness." → After: "The question is whether teams can adapt, which depends on whether they're ready to change habits."

### 28. Signposting and announcements
Announcing what you're about to do instead of doing it.
Before: "Let's dive into how caching works. Here's what you need to know." → After: "Next.js caches data at the request, data, and router layers."

### 29. Fragmented headers
A heading followed by a throwaway one-line restatement before the real content.
Before: "## Performance\n\nSpeed matters.\n\nWhen pages are slow, users leave." → After: "## Performance\n\nWhen pages are slow, users leave."

## Transferable adaptations (native English)

These three patterns are proven flags in the Chinese-language catalogs and
aren't named as separate items in the humanizer backbone above (its
Voice/Personality section touches two of them but lives in the shared core
doc, so they're restated here as standalone, checkable patterns).

### A. Stance vacuum
The text reports facts but never takes a position — pure neutral listing with no judgment call.
Before: "The migration took six weeks. Some teams reported friction. Others adapted well." → After: "The migration took six weeks, longer than planned, because two teams underestimated how much of their tooling depended on the old schema."

### B. Table/list misuse
Reaching for a table or bulleted list where the content is actually a few sentences of connected reasoning.
Before: "| Factor | Impact |\n| Cost | High |\n| Time | Medium |" (for a two-sentence tradeoff) → After: "Cost is the bigger constraint here; time is manageable if the team stays at three people."

### C. Uniform sentence length
Every sentence lands at roughly the same length and clause structure, producing a metronomic rhythm.
Before: "The team shipped the feature. The feature passed all tests. The tests covered edge cases. The rollout went smoothly." → After: "The team shipped the feature after the tests — which covered the tricky edge cases — came back clean. Rollout was smooth."
