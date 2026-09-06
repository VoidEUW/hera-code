# The terminal

The design language of `apps/cli/src/hera_code/tui`: what it feels like, what it is made of, and
how a turn is put on screen.

This is a **conversion** of hera's [`docs/frontend.md`](https://github.com/VoidEUW/hera/blob/main/docs/frontend.md),
which is 675 lines of settled argument about what that project should feel like. What carries over
is the *reasoning*; what changes is that a terminal has no fonts, no background it owns, and a
scrollback buffer that belongs to the person. Where this document departs from the source, it says
so and says why — a conversion that silently drops a decision is a conversion nobody can check.

**Status:** written before the build. Treat the *direction* as settled and the *values* as
proposals. Nothing here is built yet; the terminal is v0.1.0 M3, and what that milestone deliberately
defers is listed in [`docs/versions/v0.1.0.md`](versions/v0.1.0.md).

---

## The brief, inherited

hera's brief, condensed, with the parts that survive a terminal:

- The aesthetic reference is **Anthropic's Claude interface** — and for hera-code, specifically
  **Claude Code**. It is warm. Muscle memory is the feature.
- **Openness.** Using a skill or a tool must be visible. The interface should give as much
  feedback as possible.
- **The feeling of power.** Keyboard-first. Restraint is what makes capability feel like control
  instead of noise.
- All of it *imitated but with our own design principles, so it gives a special feeling*.

And the tie-breaker, in the maintainer's words: *"my own version of my ideal wish of Claude —
something that reminds me of it but feels like my own."* Where a choice is between **familiar**
and **clever**, familiar wins. Where it is between **borrowed** and **ours**, ours wins.

## The three qualities

Unchanged from the source, because they are about the application rather than the medium.

**Familiarity.** You already know how to use it. The layout is borrowed on purpose and no
interaction here is novel for its own sake. Sentence case everywhere, nothing to learn before the
first message.

**Openness.** Two senses. It is open about *what it is doing* — every skill it was given and why,
every tool it called, every permission it wanted, every failure it hit, none of it hidden behind a
summary. And the system is open: servers come from a JSON file you wrote, skills are Markdown
directories, the todo list is a file you can edit mid-run, and there is nothing in `~/.hera` or
`.hera/` you cannot open in an editor. **The terminal should never be the only way to see
something** — which in a terminal is easier to keep than anywhere, and this document leans on it.

**The feeling of power.** Keyboard-first, parallel tool calls landing at once and visibly, any MCP
server in the world attachable in four lines of JSON. Power reads as calm here. Nothing flickers.

## What we take, and what has to be ours

The structural patterns are free to adopt and we adopt them wholesale, because they are simply
good: a transcript you scroll, a composer that stays put, tool activity as quiet collapsed rows
above the prose, a reading measure narrower than the window.

Two things cannot be borrowed:

- **The mark.** The orange starburst is Anthropic's trademark. hera-code has a better one
  available and it already exists — see *The signature*.
- **The palette.** Not the accents, which were never in danger. Brass, laurel and pomegranate
  together are nobody's but hers.

## The signature

**The ocellus** — a single peacock eye — is inherited whole, and it converts to a terminal better
than it has any right to. Argus Panoptes had a hundred eyes and never slept; when he was killed,
Hera set his eyes into the tail of the peacock, so that she would still see everything. An
interface whose strongest functional requirement is *show me everything you did* is not decorated
with peacock eyes — it **is** the hundred eyes.

`apps/core/web/static/favicon.svg` is four concentric circles: ground, brass ring, laurel iris,
punched pupil. In a terminal that is one glyph.

```
   ◉        the mark        header, and the first eye of every turn
   ◌◍◎◉     the beat        thinking — four frames on a 2.4 s cycle
   ┆◉       the gutter      one eye per tool call, skill and permission event
```

The third is the important one. A turn with six tool calls draws six eyes down its left gutter,
joined by a hairline. Activity becomes a **column of eyes** that you read at a glance — how much
it did, and where.

**Nothing else in the terminal may use a ringed glyph.** That is the rule the mark earns its
meaning from, and it is the one visual rule in this document that is absolute.

Where the source had three pixel sizes, this has one glyph and three *colours*: brass in the
header, laurel while something is running, `--text-muted` once it has finished. Size was the
source's variable and it is not available here; colour is, and it happens to carry more.

## Colour

The three accents are inherited unchanged, and they are **not interchangeable**. Each one means
something, and using the wrong one is a bug in the same way a wrong `if` is.

| Token | Means | Used for |
|---|---|---|
| `brass` | **authority** | The mark, skills, permission cards, emphasis |
| `laurel` | **attention** | Thinking, a tool running, the ocellus iris, live state |
| `pomegranate` | **it** | The agent's own name, and the send action. Nothing else |
| `danger` | **a refusal or a failure** | Deliberately *not* harmonised with the crimson |

If a colour appears somewhere and you cannot say which of those four sentences it is saying, it
does not belong there.

### Dark terminals

```
--brass             #D9AE52
--laurel            #7FB069
--pomegranate       #DE4E64
--danger            #E0685E
--text-muted        the terminal's foreground, dimmed
```

### Light terminals

```
--brass             #8A6A1C
--laurel            #3F6B32
--pomegranate       #A82A45
--danger            #B03A2E
```

### The ground is dropped, and this is the one place the conversion refuses the source

hera spends four paragraphs getting its ground right — off cream, onto rose plaster, onto a
saturated gold — and the reasoning is sound: the **neutrals** are what a person recognises from
across a room before they have read a word.

**hera-code paints no background at all.** The terminal's background belongs to the person. They
chose it, every other tool in the terminal respects it, and an application that paints over it is
the one that looks broken next to the rest of their session. Only foregrounds, plus `dim` for
`--text-muted`.

What is lost is real: the ground was the part that was *about her*, and without it the palette is
three accents on somebody else's paper. What is gained is that hera-code looks like it belongs in
a terminal, which is the whole medium.

**Light or dark is detected, not assumed.** `COLORFGBG` first, an OSC 11 query second, and
`appearance = "dark"` in `~/.hera/code/config.toml` overrides both. Getting it wrong means brass
on a light terminal, which is unreadable — so the config key exists precisely because detection
cannot be relied on and a person should not have to argue with it.

`NO_COLOR` is honoured absolutely. With it set, the meaning that colour carried moves into the
words: a failed row reads *failed* rather than being red.

## Typography, which does not exist here

hera picks four typefaces and gives a reason for each. A terminal has one face and it is the
person's. What survives is the *distinction* the typefaces were making, in the only three
variables available:

| hera | Here |
|---|---|
| Source Serif 4 for prose — warm, generous, unhurried | The terminal's own face, default weight, with generous vertical spacing. Air is what is left of *unhurried* |
| Figtree for chrome — get out of the way | `dim`. Labels, timestamps, metadata, collapsed activity |
| IBM Plex Mono for code | The terminal's own face inside a hairline box on no background |
| Fraunces for display — the greeting, the wordmark | **Bold**, used almost nowhere: the greeting and nothing else |

**The 68-column measure survives, and it is the most important thing this section keeps.** Her
prose wraps at 68 columns in a 200-column terminal. A reading column that runs the width of a
monitor is the fastest way to make a text interface tiring, and every wide terminal is a monitor's
width. Code blocks, tables and diffs are **not prose** and use the full width — capping those
would be the version of this rule that looks broken.

### How prose is set

Markdown, typeset rather than shown as source, through `rich`. Headings, fenced blocks in the mono
face inside a hairline, tables that scroll rather than widen, and syntax highlighting on a fence
with a language tag.

`---` is a hairline with air on both sides: a separator when it meant a break in the argument. It
is never a heading — Markdown's setext form would promote the sentence *above* it, which is the
opposite of what was meant.

**TeX is dropped.** hera's ADR 11 typesets formulae with KaTeX so they read as part of the
sentence. A terminal cannot do that, and a fake is worse than the source: `$x^2$` is rendered as
what it is, and a person who wanted the formula has the characters to paste somewhere that can set
them. Being honest about a limit beats approximating past it.

## Motion

Ox-eyed: wide, calm, unhurried. Nothing flickers and nothing slides in from off-screen.

**The thinking indicator** is the one piece of choreography, and it is the ocellus. Four frames —
`◌ ◍ ◎ ◉` — over a 2.4-second beat, in laurel, in the dock's status row. Slow enough to read as
attention rather than as a spinner. A terminal cannot do the source's eight-feather burst and
should not try; what the burst was *for* was saying *she is looking*, and a four-frame eye opening
says it.

Everything else is a repaint of the dock. There are no transitions, because there is no compositor
to run them on and a repaint that pretends to be one is a flicker.

**Motion is off entirely** when any of these hold, and each is a real case rather than a
completeness exercise:

| | |
|---|---|
| `NO_COLOR` | A person who turned off colour did not ask for animation either |
| `HERA_CODE_MOTION=off` | The explicit control |
| stdout is not a TTY | `hera-code -p "…" \| cat` — the failure mode this design is most exposed to |
| `TERM=dumb` | An editor's embedded terminal, a CI log |

With motion off the mark is still, the dock is drawn once, and the terminal must be **completely
usable and completely legible**. That is the source's `prefers-reduced-motion` rule and it is
inherited without softening.

---

## The screen

### The arrangement

The transcript is printed into the terminal's **real scrollback** — the terminal scrolls it, the
mouse selects it, `| less` works, and it is still there after the process exits. The dock is
pinned at the bottom, redrawn in place, and never scrolls away.
[ADR 3](adr/0003-the-transcript-lives-in-scrollback.md) is why, including why not Textual.

```
  ◉  hera-code 0.1.0    ~/dev/myrepo  main ✱3                     coding

› add rate limiting to the api

┆◉ thought     read TODOS.md, 3 open                                    Show
┆▤ skill       fastapi                                        skill · pinned
┆◍ graph       api.routes → limiter                                  8 nodes
┆✎ todo        4 items written                                          12 ms

I'll add a token-bucket limiter in `app/middleware/limit.py`. Three steps,
and the second is the one worth looking at.

╭─────────────────────────────────────────────────────────────╮
│  ⬡  Run code__edit?                                         │
│     app/middleware/limit.py   +34 −0                        │
│     Writes inside the working tree.                         │
│                                                             │
│              [ Allow once ]  [ Always allow ]  [ Deny ]     │
╰─────────────────────────────────────────────────────────────╯

──────────────────────────────────────────────────────────────────────────
 ┆ TODOS  1/4   ▸ a2  add the token bucket                        ^T all
 ›  _
   ＋ coding                          ⏎ send   ⇧⏎ newline   ^C stop
──────────────────────────────────────────────────────────────────────────
```

### The dock

Three rows, always visible.

**1 — the todo strip.** Progress, and the one item in progress. `^T` expands the whole list in
place; the dock grows and the transcript scrolls up, which is what the terminal does anyway. This
row is why the todo list is a feature rather than a printout —
[ADR 8](adr/0008-the-todo-list-is-a-file-and-the-intake-is-a-conversation.md).

```
 ┆ TODOS  1/4   ▸ a2  add the token bucket                        ^T all
```

Blocked items are brass and counted separately: `1/4 · 1 blocked`. An item nobody could decide is
visibly different from an item nobody started, and collapsing the two is how a stalled run looks
like a slow one.

**2 — the composer.** Multi-line. `⏎` sends, `⇧⏎` newline, `/` opens the command menu, `@`
completes a path from the working tree, `↑` recalls. Focused on load, because the first thing a
person does is type.

**3 — the status line.** Profile, branch and dirty count, session token usage, and the keys that
apply right now. While a turn is running it carries the thinking eye and `^C stop`.

Below 80 columns the dock drops to two rows — the todo strip shortens to `1/4 ▸ a2` and joins the
status line. Nothing is removed, only the resting state is quieter. That is the source's mobile
rule, kept: *nothing is removed, only the resting state is quieter*.

### Overlays

`^K` opens the command palette. The todo board, the session picker and settings are `Float`s in
the same layout — **not** a second full-screen mode, because switching buffers is exactly the
thing [ADR 3](adr/0003-the-transcript-lives-in-scrollback.md) declined.

| | |
|---|---|
| `^T` | The todo board — the whole list, editable in place |
| `^K` | Command palette |
| `^O` | Expand the activity row under the cursor |
| `^C` | Stop the turn. Twice quickly: quit |
| `^D` | Quit on an empty composer |

---

## A turn, rendered

This is the part that matters, because it is where the design meets the data. A turn is **a list
of events**, and the terminal renders one component per variant. It never parses the model's text
— that rule is not a style preference, it is the single largest source of bugs in hera's previous
generation and it is designed out.

| Event | Renders as |
|---|---|
| `text_delta` | Prose, at 68 columns, streamed in |
| `thinking_delta` | The reasoning channel — collapsed, one gutter row per **block** |
| `tool_call_started` | The gutter row appears, with no result yet. Never persisted |
| `tool_call_ready` | The same row, keyed on the call id, now with arguments |
| `tool_result` | The same row again, with its outcome and duration |
| `skill_selected` | A gutter row carrying **why**: pinned, slash or retrieved |
| `permission_required` | A **permission card**, inline where the call would have happened |
| `answer_required` | A **question card**, inline where it was asked |
| `turn_closed` | Ends the turn. `cancelled` marks it visibly as interrupted |

**The started row and the ready row are the same row.** A reloaded turn has strictly fewer events
than the live one had — `tool_call_started` is never persisted — and the renderer must produce the
same rows from both. Keying on the call id is what makes that true.

**An unknown variant degrades visibly**, never silently. A row saying `? unknown event: <type>` in
`--text-muted` is information; nothing at all is a bug that hides itself.

### The activity gutter

Everything done before speaking stacks above the prose as collapsed rows, each with its ocellus on
a hairline. Quiet, dimmed, expandable with `^O`. A row carries the verb, the target, and how long
it took.

```
┆◉  thought    61 words                                                  Show
┆▤  skill      fastapi                                         skill · pinned
┆◍  graph      api.routes → limiter                                   8 nodes
┆✎  note       app/middleware/limit.py                                  12 ms
┆⌨  bash       pytest tests/test_limit.py                          2.1 s  ✓
┆🔧 called     Docker mcp find                                          210 ms
```

**Its own tools name what they did; everybody else's name where they came from.** The mark has
already said whose tool it is, so *called code graph* spends half a short row repeating it — where
a reader wants *which* symbol. A foreign tool is the opposite: the server is the most important
thing about `mcp-find`, so it keeps *called **Docker** mcp find* and its wrench. The mapping from
a tool name to a mark reads `code__*` only; a table that learned somebody else's server would make
one you have not configured look broken beside one you have.

**A shut block still shows the last two lines of it.** A collapsed row saying *thought · 213 words
· Show* is a receipt: it tells you something happened and nothing about what. The tail is anchored
to the *bottom* of a two-line box, so what you are looking at is the most recent thing it wrote,
with the cut above it dimmed rather than chopped.

**The gutter is in event order, and reasoning comes in blocks.** It thinks, calls something, reads
the result and thinks again — so that is two rows with the call between them, not one row that
grew. Folding a turn's reasoning into a single row at the top puts the second half of the thinking
above the call that caused it. The rule for where a block ends is the server's coalescing rule
(`hera_chats.coalesce`): anything between two fragments stops the merge, so the live view and a
resumed session cannot disagree about how many rows there are.

**Skills say why they are there.** hera's ADR 5 selects them in code — pinned, `/slash`, or
retrieved by similarity — and the row shows which of the three it was. A person needs to be able
to tell "it always has this" from "it went and found this", and it is the only feedback loop that
reveals retrieval picking the wrong thing.

### The question card

`code__ask` stops the turn and puts a question on screen, inline where it was asked. Drawn from
`answer_required` rather than from the call — the call, the card and the synthesised result are
all about the same question, and drawing three of them would be machinery pretending to be
conversation.

```
╭───────────────────────────────────────────────────────╮
│  ?  it needs you to choose                            │
│     Redis or an in-process bucket?                    │
│                                                       │
│     ›                                                 │
│                                    ⏎ to send          │
╰───────────────────────────────────────────────────────╯
```

**Laurel, not brass.** Brass is authority — *this needs a decision*. A question is the agent
turning towards you, and drawing it in the permission colour would make being asked feel like
being stopped.

`kind` is a **closed set of three** and the label is the *person's* wording, not the tool's:

| `kind` | Reads | Colour |
|---|---|---|
| `unsure` | it is unsure | `--text-muted` |
| `blocked` | it cannot go on | `brass` |
| `choice` | it needs you to choose | `--text-muted` |

Only `blocked` is set apart, because it is the one of the three where the turn is genuinely
stopped on the reply. **Nothing here may be the danger colour: no question it can ask is an
error.** A kind this build does not recognise renders as nothing rather than as the raw word.

This is also the card the **intake conversation** is made of — the questions asked before the todo
list is written. Several in a row is the normal case there, and they are drawn as one card per
question rather than a form, because a form is a thing you fill in and a question is a thing you
answer.

### The permission card

The one moment the terminal blocks. An `ask` outcome from `hera_permissions` stops the turn and
puts the decision in front of a person, inline where the call would have happened.

```
╭─────────────────────────────────────────────────────────────╮
│  ⬡  Run code__bash?                                         │
│     pytest tests/test_limit.py -x                           │
│     Runs a command in the working tree.                     │
│                                                             │
│              [ Allow once ]  [ Always allow ]  [ Deny ]     │
╰─────────────────────────────────────────────────────────────╯
```

Brass edge — this is authority. The second line is the arguments; the third is `Outcome.reason`
from the deciding rule, and filling that field in is why it exists: *why am I being asked this*
should not be a question only a configuration file can answer. **Always allow** writes a rule and
says so afterwards, because a person should never wonder whether a decision stuck.

`←`/`→` move between the three, `⏎` chooses, `Esc` denies. Denying is the safe default and
therefore the one a mistyped key should reach.

**A coding agent asks more than a chat agent does**, and that is deliberate: writes, edits and
shell all `ask` by default, and anything outside the working tree is denied outright
([ADR 4](adr/0004-mcp-is-the-tool-layer.md)). A person who finds it noisy has **Always allow** and
a rules file. A person who finds it quiet has no recourse at all, which is why the default is the
loud one.

### An edit, shown

The one place hera-code needs a component hera has no equivalent for. A `code__edit` or
`code__write` call renders its diff in the permission card *before* it runs and in the gutter row
*after*:

```
┆✎  edit       app/middleware/limit.py                        +34 −0  12 ms
   │  32   class TokenBucket:
   │  33 +     def __init__(self, rate: float, burst: int) -> None:
   │  34 +         self.rate = rate
```

Green and red are the two colours in this document that are **not** from the palette, and they are
not negotiable: every diff a person has ever read uses them, and a diff in brass and laurel would
be a diff nobody can skim. Familiar wins over ours, which is the tie-breaker doing its job. In
`NO_COLOR` the `+`/`−` markers carry it, as they always have.

Long diffs collapse to a header and expand with `^O`.

### When something fails

`hera_tools` never raises past the registry — a failed call is a `ToolResult` with a `Failure`,
which means each of these is a *render*, not an error boundary.

| `Failure` | Row reads | Tone |
|---|---|---|
| `denied` | "not allowed — <reason>" | `danger` |
| `unknown_tool` | "no such tool" | muted; it is correcting itself and that is fine |
| `unavailable` | "<server> is not running" | `danger`, with the server's failure reason |
| `timeout` | "gave up after 60s" | `danger` |
| `tool_error` | The tool's own message | muted; the tool worked and said no |
| `repeated` | "already called this — try different words" | muted |

The distinction between the muted three and the loud three is deliberate. `unknown_tool`,
`tool_error` and `repeated` are the system behaving correctly; alarming a person about them
teaches them to ignore the colour that matters.

Tool results carry content blocks, not just text, so a result can be an image or a resource link.
The expanded row renders what it can and names what it cannot; it does not flatten everything to a
string.

### At `turn_closed`

The turn is re-rendered once from the persisted, coalesced event list. Live view and a resumed
session therefore cannot disagree — which is worth more than it sounds, because it is what makes
every optimistic state above safe to be wrong about for a second.

**In scrollback this is a re-print, not a repaint.** What was streamed above stays where it is;
the finished turn is what the *next* read of the session shows. The consequence is that streaming
output has to be correct as it goes rather than fixed up later, which is a constraint worth
knowing before writing a renderer that assumes it can go back.

---

## Voice

Terminal strings are **English**. Sentence case. Active voice. A control says what happens:
**Send**, not *Submit*. An action keeps its name all the way through — the button that says
**Always allow** produces a confirmation that says *Always allowed*. Name things by what a person
controls: **Servers**, not *MCP client configuration*.

Failures explain what happened and what to do, and they do not apologise. *"filesystem is not
running — check the command in mcp.json"* beats *"Sorry, something went wrong."* Empty states are
invitations: an empty todo list says what one is for and offers to build it with you.

The agent's own voice — anything written as it rather than about it — is warm and direct and never
coy, and in a terminal it is also **short**. A coding agent that writes three paragraphs before a
diff is one a person scrolls past.

## Constraints the design cannot negotiate with

- **No parser in the terminal.** It renders event variants it is handed. A new thing the model can
  do is a new variant, never a new regular expression. Typesetting Markdown is not an exception
  and may not become one: it draws text as what it is and reads no meaning back out of it.
- **Every event variant needs a renderer**, including ones that arrive unknown — degrade visibly,
  never silently.
- **The persisted render is authoritative** at `turn_closed`.
- **The transcript belongs to the terminal.** Never take the alternate screen buffer. Never repaint
  above the dock. `| cat` must produce plain text.
- **Prose caps at 68 columns; code does not.**
- **Nothing else uses a ringed glyph.**
- **Keyboard first**, and every action reachable without a mouse.
- **`NO_COLOR`, `TERM=dumb` and a pipe each produce something completely legible.**

## Open

1. **The wordmark.** `◉ hera-code` in the header, or something drawn? The source asks the same
   question about its own and leaves it open.
2. **Syntax highlighting palette.** `rich` ships themes; none of them is brass and laurel. Worth a
   pass of its own, and it is the one place the accent palette could plausibly extend.
3. **Where thinking lives** — a gutter row that expands in place, as drawn, or its own region
   above the composer? The source leaves this open too, and the answer may differ here because a
   coding agent thinks more.
4. **How much of a diff is too much** before the card is unreadable and the answer should be a
   file path and a count.
5. **Whether the dock should show the session's cost**, and whether that is a number a person
   steers by or one they only worry about.

Everything in this document is provisional until there is a build to argue with. When there is,
this gets rewritten rather than amended — and the rewrite should be driven by looking at it, not
by reading this.
