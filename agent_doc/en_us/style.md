# style.md — positive English writing craft

Lazy-load reference for the article-writer role's writing mode. This file is
positive craft only — for the AI-tell ban/detection list, see `patterns.md`
in this same directory.

Sources: Strunk & White's *Elements of Style* (elementary rules of usage +
elementary principles of composition), a short pick of commonly misused
words, and the `writing-coach` skill (inverted pyramid, technical-writing
conventions).

## Core composition principles

### Omit needless words
Every word should earn its place. Cut filler before it ships.
Before: "the fact that he had not succeeded" → After: "his failure"

### Use the active voice
Active is more direct and usually shorter; keep the passive for the rare case where the object matters more than the actor.
Before: "The fix was deployed by the team." → After: "The team deployed the fix."

### Put statements in positive form
State what is, not what isn't. A string of "not"s reads as evasive.
Before: "He did not think studying Latin was much use." → After: "He thought studying Latin was useless."

### Use definite, specific, concrete language
Prefer the image to the abstraction — it's what holds a reader's attention.
Before: "Performance improved significantly." → After: "Latency dropped from 200ms to 50ms."

### One paragraph, one topic
Each paragraph gets a topic sentence and stays on it; a new paragraph signals a new step in the argument.
Before: a paragraph that opens on rollout timing and drifts into a tangent about the team's history → After: split into a rollout paragraph and a separate history paragraph, each with its own topic sentence.

### Avoid a run of same-shaped sentences
Two clauses joined by "and" or "but," repeated sentence after sentence, turns monotonous fast. Vary the construction.
Before: "The concert was given, and the audience was large. The soloist played, and the orchestra performed. The interest was gratifying, and another series is planned." → After: "The concert drew a large audience. The soloist and orchestra both delivered — enough that a second series is now planned."

### Express coordinate ideas in parallel form
Items that do the same job in a sentence should look alike; mismatched forms read as timid or careless.
Before: "It was both a long ceremony and very tedious." → After: "The ceremony was both long and tedious."

### Keep related words together
Put the subject next to its verb, and a modifier next to what it modifies — a stray phrase between them forces the reader to hold the sentence in suspension.
Before: "He only found two mistakes." → After: "He found only two mistakes."

### Place the emphatic word at the end
The position a reader's attention lands on hardest is the end of the sentence — put the point there, not a throwaway clause.
Before: "This steel is principally used for making razors, because of its hardness." → After: "Because of its hardness, this steel is used mainly for razors."

## Ten commonly misused words

- **Due to** — not a substitute for "because of" in an adverbial phrase. "He lost, due to carelessness" → "He lost because of carelessness."
- **Less / fewer** — less is quantity, fewer is count. "Less men" → "fewer men."
- **Like / as** — like governs nouns; as introduces a clause. "He thought like I did" → "He thought as I did."
- **Factor** — usually padding. "Training was the great factor in his win" → "He won by training harder."
- **Case** — usually unnecessary. "In many cases the rooms were poorly ventilated" → "Many rooms were poorly ventilated."
- **He is a man who** — redundant construction. "He is a man who is ambitious" → "He is ambitious."
- **Different than** — not standard. Use "different from."
- **Very** — use sparingly; reach for a word that's already strong instead.
- **Nature / character** — often pure filler. "Acts of a hostile nature" → "Hostile acts."
- **Whom** — don't use it as the subject of a following verb. "His brother, whom he said would send the money" → "his brother, who he said would send the money."

## Structural craft (writing-coach)

- **Inverted pyramid.** Lead with the conclusion; put supporting detail after, not before.
- **Short paragraphs.** Three to five sentences, one point each.
- **Scannable structure.** Headings and lists break up dense text — but see patterns.md #16 on not overusing bolded list-labels.
- **Logical transitions.** Each paragraph should connect to the next; don't just juxtapose.
- **Cut ruthlessly.** A sentence that adds nothing gets removed, not softened.
- **Consistent terminology.** Pick one term per concept and keep it; don't cycle synonyms (see patterns.md #11).
- **One example beats a paragraph of abstraction.** For any non-obvious technical claim, show a concrete instance.
- **Numbered steps, one action each.** For procedures, no compound steps.

## Priority when principles conflict

Clarity beats elegance. If following parallel structure or emphatic word
order would obscure the meaning, drop the rule and say the thing plainly.

## Plain-language techniques (ISO 24495 English layer)

Numeric proxies below are tripwires for a second look, not hard caps — this
project's own working thresholds, not clauses of the standard.

- Sentence length ~20 words. Longer is fine when the sentence carries one
  idea cleanly; two ideas in one sentence is the real violation.
- Paragraph length ~5 sentences as a tripwire.
- Use a list once an enumeration hits 3+ parallel items; keep list items
  grammatically parallel.

Self-check before returning any rewritten text:
1. Can the named reader say, after one reading, what this text wants them
   to know or do?
2. Is the main point in the first two lines?
3. Does any sentence carry two ideas, or any paragraph two topics?
4. Is any term used under two names, or any jargon left undefined?
5. Did every fact, number, condition, and honest hedge survive the rewrite?
