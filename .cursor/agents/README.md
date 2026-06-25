# Cursor agents index

Role cards for background/agent tasks. Each maps to a skill + LLM prompt + schema.

| Agent | Model | Skill | Prompt |
|-------|-------|-------|--------|
| [Orchestrator](orchestrator.md) | claude-opus-4-8 | `.cursor/skills/orchestrator/` | `agents/orchestrator.md` |
| [News Digestor](news-digestor.md) | claude-sonnet-4-6 | `.cursor/skills/news-digestor/` | `agents/subagents.md` §1 |
| [Market Structure](market-structure.md) | claude-sonnet-4-6 | `.cursor/skills/market-structure/` | `agents/subagents.md` §2 |
| [Derivatives & Flow](derivatives-flow.md) | claude-sonnet-4-6 | `.cursor/skills/derivatives-flow/` | `agents/subagents.md` §3 |
| [Whale / Smart-Money](whale-smart-money.md) | claude-sonnet-4-6 | `.cursor/skills/whale-smart-money/` | `agents/subagents.md` §4 |
| [Fundamentals / Fragility](fundamentals-fragility.md) | claude-sonnet-4-6 | `.cursor/skills/fundamentals-fragility/` | `agents/subagents.md` §5 |

Shared skills:

- **Phase builder** — `.cursor/skills/phase-builder/` (execute BUILD.md phases)
- **Claude ↔ Cursor handoff** — `.cursor/skills/claude-cursor-handoff/` (`status.md`, `handoff.md`)

Governance: `.cursor/rules/000-project.mdc` (always apply) + scoped rules 100–500.

**Market voice:** `agents/trading_engine_compact.md` + rule `730-trading-engine-tone.mdc`. Never load full `trading_engine_essence.md` into LLM prompts.
