# 09: Full-text mode

**What to build:** one visible setting, `structure` (the default) or `full`, decides whether a trace also carries candidate text: the blocks, the rendered prompt messages, the raw answer and the rejections' quotes. Full mode is set only for the CI eval and local runs, which use synthetic fixtures; the deployed app never sets it. The two modes differ only in the payload function's output, which keeps them on one code path and makes the generation count the same in both.

**Blocked by:** 07

**Status:** ready-for-agent

- [ ] The setting defaults to `structure`; an unknown value fails at startup with a named error (tested)
- [ ] Positive control: in full mode, canaries from a built document appear in the exported generation and spans
- [ ] Full mode exports the same spans and the same number of generations as structure mode (no double counting)
- [ ] The CI eval job sets `full`; the deploy configuration does not (the workflow's static tests assert both)
- [ ] The setting is documented
