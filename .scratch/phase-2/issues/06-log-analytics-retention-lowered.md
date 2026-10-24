# 06: Log Analytics retention lowered

**What to build:** `cvr-log` keeps logs for the minimum Azure allows (target 7 days, the figure found by ticket 01), set by the provisioning wizard idempotently so that a re-run is harmless. The value is recorded where ADR-0013 can cite it.

**Blocked by:** 01

**Status:** done

- [x] The wizard sets the retention found in ticket 01, and reports the current value when it is already set
- [x] The wizard's static test covers the new step
- [x] The maintainer runs it; the read-back value is recorded on this ticket (non-`_CL` tables 4/4, `_CL` tables 30, the workspace floor; see the second 2026-10-21 comment)
- [x] CLAUDE.md's deployment entry states the retention

## Comments

2026-10-21: Built. The target changed from 7 days: ticket 01 found the workspace minimum for PerGB2018 is 30 (left at 30) and the per-table minimum is 4 days, and the maintainer decided the ContainerApp tables go to 4 days, retention and total. Stage 12 of `scripts/provision-azure.sh` lists the `ContainerApp*` tables that exist (`table list`, so the `_CL` variants are included and a missing table is skipped with a note), reads `retentionInDays` and `totalRetentionInDays` of each (`table show`), updates only one that is not 4/4 (`table update --retention-time 4 --total-retention-time 4`) and reads every table back. `tests/ci/test_provision_script.py` pins it. Nothing in Azure has been changed. Still open: the maintainer runs the wizard and the read-back values are recorded here for ADR-0013.

2026-10-21 (outcome, decision A): The maintainer ran the wizard. Stage 12 set `ContainerAppSystemLogs`, `ContainerAppConsoleLogs` and `ContainerAppHTTPLogs` from 30 30 to 4 4 (the wizard's own read-back confirms 4 4), then `ContainerAppSystemLogs_CL` was refused: `(InvalidParameter) Changing Classic table ContainerAppSystemLogs_CL schema by using DataCollectionRuleBased tables api is forbidden, please migrate the table first or use the appropriate classic table api.` `ContainerAppConsoleLogs_CL` would fail the same way. The maintainer's read-only query over the last 30 days: `ContainerAppSystemLogs_CL` 8,043 rows, `ContainerAppConsoleLogs_CL` 150,189 rows; the other three tables have no rows, so the environment writes only to the `_CL` tables and the three at 4/4 are empty.

Research (Microsoft Learn): the retention how-to documents only the Tables API (PATCH leaves omitted fields unchanged) and names no classic-table exception or classic API (https://learn.microsoft.com/en-us/azure/azure-monitor/logs/data-retention-configure, https://learn.microsoft.com/en-us/azure/azure-monitor/logs/manage-logs-tables). `az monitor log-analytics workspace table migrate` converts a classic table to DCR-based; the doc says a migrated table cannot be rolled back, a legacy writer must not change the schema afterwards, and it says nothing of how the Container Apps writer behaves after it (https://learn.microsoft.com/en-us/azure/azure-monitor/logs/custom-logs-migrate). With the default `log-analytics` destination the app writes `ContainerAppConsoleLogs_CL` and `ContainerAppSystemLogs_CL`; the non-`_CL` tables are the `azure-monitor` destination plus diagnostic settings (https://learn.microsoft.com/en-us/azure/container-apps/log-monitoring, https://learn.microsoft.com/en-us/azure/container-apps/log-options).

Decision (option A): accept 30 days for the `_CL` tables and record it. 30 is the PerGB2018 workspace floor, which a table without its own setting inherits; there is no documented non-migrating way to change them; migration is irreversible and its effect on the platform's writer is undocumented; the data is synthetic; and below 31 days saves nothing (31 are in the ingestion price). Stage 12 now warns by table name on a table it cannot change and goes on, so stage 13 runs. Read-back: non-`_CL` ContainerApp tables 4/4, `_CL` tables at the workspace's 30. ADR-0013, CLAUDE.md and the wizard's text say the same. Option B, switching the environment to `--logs-destination azure-monitor` with a diagnostic setting (documented, reversible, changes table names and columns and disables the portal Logs blade), is a possible later ticket, not part of this phase.
