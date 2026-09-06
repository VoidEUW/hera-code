# 2. Any OpenAI-compatible endpoint, and no target model

- Status: accepted
- Date: 2026-09-06

## Context

hera's [ADR 2](https://github.com/VoidEUW/hera/blob/main/docs/adr/0002-qwen-only-target-model.md)
names **Qwen3.6-35B** as the only target model and leans on it: native tool calling including
parallel calls, a real reasoning channel, enough capacity for XML-tagged prompt structure. The
payoff there is that there is no text-based call grammar and no provider-specific output
normalisation — both existed in that project's previous generation purely to compensate for a
smaller model, and both cost a second parser in the frontend that had to be kept in lockstep.

hera-code inherits `hera_providers`, which already implements that as
`OpenAICompatibleProvider` plus a `QwenAdapter` on top. The adapter is the Qwen-specific part; the
provider underneath is not.

The question is whether hera-code inherits the *constraint* as well as the code. A coding agent is
a different workload from a chat: turns are longer, tool loops are deeper, and a wrong edit costs
more than a wrong sentence. It is also a workload where a person may reasonably want to point the
same tool at a local box on Monday and something else on Friday.

## Decision

hera-code targets **any OpenAI-compatible endpoint**. It does not have a target model, and no code
above `hera_providers` may assume one.

Endpoints are registered in `~/.hera/code/config.toml`; several may be registered and one is
active. `QwenAdapter` stays available and is what a local Qwen endpoint should be configured with;
it is a choice in a file rather than an assumption in the code.

What hera-code keeps from hera's ADR 2 is the part that was never about Qwen:

- **No text-based call grammar.** Tool calls arrive as tool calls or they do not arrive.
- **No provider-specific output normalisation above `hera_providers`.** One event union, and
  anything a model can newly do is a variant in that package plus one line of mapping.
- **Skill selection is code** ([ADR 5](https://github.com/VoidEUW/hera/blob/main/docs/adr/0005-deterministic-skill-routing.md),
  inherited). A capable model noticing a relevant skill does not make a mechanism that depends on
  it a good one, and the whole todo-and-graph design here assumes nothing is volunteered.

## Consequences

- **The minimum bar is native tool calling.** An endpoint without it does not work, and says so
  rather than degrading into a grammar. That is a real exclusion and it is the right one.
- **Behaviour varies by endpoint and hera-code cannot promise otherwise.** A weaker model will
  loop more and plan worse. The controls that already exist — `ChatsSettings.max_iterations`, the
  repeat-call limiter, the wrap-up round — are what keep that bounded, and they are model-agnostic
  by construction.
- **Testing stays honest.** Everything is driven against `hera_providers.FakeProvider` in CI;
  anything needing a real endpoint is marked `live` and never runs there. Not having a target
  model does not mean testing against several — it means testing against none, on purpose.
- **hera is unaffected.** Its ADR 2 stands. This record says what hera-code does, not what hera
  should do, and the shared `hera_providers` is unchanged by either.
- The reasoning channel is optional here where it was assumed there. `ThinkingDelta` simply does
  not arrive from an endpoint that has none, and the activity gutter draws what it is given.
