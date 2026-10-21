# 06: Log Analytics retention lowered

**What to build:** `cvr-log` keeps logs for the minimum Azure allows (target 7 days, the figure found by ticket 01), set by the provisioning wizard idempotently so that a re-run is harmless. The value is recorded where ADR-0013 can cite it.

**Blocked by:** 01

**Status:** in-progress

- [x] The wizard sets the retention found in ticket 01, and reports the current value when it is already set
- [x] The wizard's static test covers the new step
- [ ] The maintainer runs it; the read-back value is recorded on this ticket
- [x] CLAUDE.md's deployment entry states the retention

## Comments

2026-10-21: Built. The target changed from 7 days: ticket 01 found the workspace minimum for PerGB2018 is 30 (left at 30) and the per-table minimum is 4 days, and the maintainer decided the ContainerApp tables go to 4 days, retention and total. Stage 12 of `scripts/provision-azure.sh` lists the `ContainerApp*` tables that exist (`table list`, so the `_CL` variants are included and a missing table is skipped with a note), reads `retentionInDays` and `totalRetentionInDays` of each (`table show`), updates only one that is not 4/4 (`table update --retention-time 4 --total-retention-time 4`) and reads every table back. `tests/ci/test_provision_script.py` pins it. Nothing in Azure has been changed. Still open: the maintainer runs the wizard and the read-back values are recorded here for ADR-0013.
