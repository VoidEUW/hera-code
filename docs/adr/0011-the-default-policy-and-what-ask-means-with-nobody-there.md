# 11. The default permission policy, and what `ask` means with nobody there

- Status: accepted
- Date: 2026-09-06

## Context

hera-code is about to get tools that change a working tree and run a shell. Two questions have to
be answered before they are wired rather than after, and they are the same question at two
distances.

**What may run without asking?** hera's `DEFAULT_POLICY` allows all of `hera__*` without a card,
and the reasoning is written down: her tools are called several times in an ordinary turn — a
scratchpad write, a memory, two searches — and a confirmation for each would teach a person to
click through cards without reading them, which is the failure that matters. Her worst tool writes
into her own scratchpad.

**Nothing about that reasoning survives `code__bash`.** A shell in a repository somebody is
mid-refactor on is not bounded, and neither is `code__edit`.

**And what happens when the card cannot be drawn?** `hera-code -p "…"` runs a turn with nobody
watching. `hera_chats` suspends on an `ask` outcome and waits; in a pipe there is nothing to wait
for. Three things could happen and only one of them is defensible.

## Decision

### The policy

Seeded on `init` as `hera_permissions` rules, editable afterwards, and every rule carries a
`reason` — that field exists so *why am I being asked this* is not a question only a configuration
file can answer, and it is what the card's third line renders.

| Pattern | | Why |
|---|---|---|
| `code__read` · `code__glob` · `code__grep` | **allow** | Reads inside the tree and changes nothing |
| `code__graph_*` | **allow** | Reads a derived index and changes nothing |
| `code__todo_*` · `code__note_*` | **allow** | Writes only into `<root>/.hera`, which is the agent's and which a person can read and revert (ADR 7) |
| `code__write` · `code__edit` | **ask** | Changes source |
| `code__bash` | **ask** | Unbounded |
| everything else | **ask** | A tool nobody has an opinion about is exactly the case a person should see once |
| anything resolving outside the working tree | **deny** | See below |

**`deny` is not "ask, but stricter".** Outside-the-tree is refused because it is outside the
contract, not because it is risky — hera-code's promise is that it works on *this* directory, and
a call that leaves it is a bug in the call rather than a decision for a person. That distinction is
load-bearing below.

**A coding agent therefore asks more than a chat agent does, and that is the decision.** Somebody
who finds it noisy has *Always allow*, which writes a rule. Somebody who finds it too quiet has no
recourse at all — they find out from a diff. Between a default that annoys and a default that
surprises, the annoying one is the one you can recover from.

### With nobody there

**The turn stops.** It closes `awaiting_permission`, the events are persisted, stderr names the
call that is waiting, and the process exits `4` — its own code, so a script can tell *it asked for
permission* from *the endpoint is down*.

**`--yes` says yes in advance**, and is documented as exactly that. It allows calls the policy
would have **asked** about. It does **not** touch `deny`: the containment guard is an invariant,
not a preference, and a flag that could switch it off would make it a preference. Every call it
allows is named on stderr, so a CI log shows what was permitted rather than only what happened.

## Alternatives, and why not

**Auto-allow in `-p` because there is nobody to ask.** This is the dangerous one, and it is
dangerous precisely because it is convenient: it makes the *absence of a person* into consent.
The failure mode is silent — a pipeline that ran a shell command nobody approved looks identical
to one that did not — and it is the single failure in this design a person could not detect from
the output.

**Refuse instead of suspending.** Turning `ask` into `deny` when non-interactive would let the
turn continue with a refusal the model can read and work around, which is tempting. It is wrong
because a refused call is *information the model acts on*: it will try something else, and what
comes out is an answer built around a restriction the person never chose. Stopping says what
actually happened.

**No `--yes` at all.** Honest, and it makes `-p` unusable for the thing `-p` is for. The flag is
the seam where a person takes responsibility explicitly, which is better than not offering it and
having somebody set every rule to `allow` in a config file to get the same effect with none of the
visibility.

## Consequences

- **`-p` is read-only by default**, and that is a useful sentence rather than an apology: without
  `--yes` it can read, search and navigate a repository and answer about it, and it cannot change
  anything. That is a genuinely good default for a scripted invocation.
- **Exit `4` is part of the contract now.** A wrapper script can retry with `--yes`, or open a
  terminal, and tell the two apart.
- **`--yes` in CI is a decision somebody has to type.** That is the point. It appears in the
  workflow file, in review, in the log.
- **The `reason` on every rule is now load-bearing twice** — once on the card, once on the line
  `--yes` prints. A rule added without one degrades both, so the seeded set has one each and the
  test suite checks it.
- **`Always allow` writes a rule and says so.** A person should never wonder whether a decision
  stuck; that was already true in `docs/tui.md` and this is the policy side of it.
- The sandbox that would let `bash` be `allow` is v0.3.0, and `docs/tooling.md` § 5 is where the
  friction this creates is recorded rather than dismissed. Until then, the card is the sandbox.
