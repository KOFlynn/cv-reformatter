# 12: The retry prompt in RealLabeller

**What to build:** the labeller can be asked for a retry. The `Labeller` type gains an optional feedback argument, and a call without it is the first attempt, so the oracles still work. With feedback, `RealLabeller` sends the retry prompt and asks for the `Additions` schema. The retry prompt is given every block, its first answer and the **Feedback** text (the unplaced runs and the unlocatable quotes). The retry prompt and the additions schema each get an entry in the versions record, with hashes, checked at import like the existing two. The graph does not use this yet (ticket 14).

**Blocked by:** 11

**Status:** ready-for-agent

- [ ] Over a fake chat model: no feedback → the first prompt and `Labelling`; feedback → the retry prompt and `Additions`, with the blocks, the first answer and the feedback text in the messages (tested)
- [ ] Changing the retry prompt or the additions schema without a version bump fails at import with `VersionMismatch` naming the fix (tested)
- [ ] The labeller's content hash covers both new artefacts (so the eval cache keys change; the PR notes that the next eval is uncached)
- [ ] A retry's answer goes through the same failure classification as ticket 03's (once 03 has landed) and fills its own `LabelRun`
- [ ] The oracle labellers and every existing labeller test pass unchanged
