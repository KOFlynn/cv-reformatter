# 20: Provider comparison and verdict

**What to build:** the provider is chosen by numbers, following the **Model comparison** method from Phase 1.5. Three eval runs of gpt-5.4 (Data Zone EU) are set against three of Sonnet 5.5 at `medium`, on the same prompt and schema versions and the same golden set, retry included. The maintainer runs them locally with `az login`. The comparison is committed as a dated record beside the earlier one, and ADR-0015 records the verdict, its numbers, the Anthropic path's lack of an EU-only processing guarantee, and the rule that the comparison is re-run whenever the prompt, a schema or either model changes. The brief's §8 is amended: the gate runs the deployed provider, and the comparison record is where the other provider is judged.

**Blocked by:** 15, 17, 18

**Status:** ready-for-agent

- [ ] The Sonnet side reuses existing runs only if they are on the same prompt and schema versions; otherwise three new runs, and the record says which
- [ ] The record holds per-run gate results, metrics, retries, cost and wall time for both sides
- [ ] ADR-0015 written; the brief's §8 amended and its §10 comparison box ticked
- [ ] If Azure wins, ticket 21 is marked ready; if not, it is closed as not needed, with the reason
