# 06: Log Analytics retention lowered

**What to build:** `cvr-log` keeps logs for the minimum Azure allows (target 7 days, the figure found by ticket 01), set by the provisioning wizard idempotently so that a re-run is harmless. The value is recorded where ADR-0013 can cite it.

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] The wizard sets the retention found in ticket 01, and reports the current value when it is already set
- [ ] The wizard's static test covers the new step
- [ ] The maintainer runs it; the read-back value is recorded on this ticket
- [ ] CLAUDE.md's deployment entry states the retention
