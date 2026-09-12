# The golden set is generated from fixtures, not downloaded

The eval needs source CVs with exact expected output. Downloaded or scraped CVs would need hand-labelling, carry licensing risk, and contain real people. Instead, 12 fictional Candidates are hand-reviewed JSON under `fixtures/candidates/`, and 4 deterministic Layouts render each into a messy source `.docx`. The Candidate JSON *is* the expected answer for every layout; the generated `.docx` files are committed so eval runs never depend on rerunning the generator.

Two rules follow from "the fixture is the ground truth":

- Expected values are hand-written, never derived by the code under test. In particular each date carries an `expected` string (`"03/2021"`, `"2019"`, `"Present"`) written by hand, so a formatter bug cannot cancel itself out on both sides of the comparison.
- Content traps (typos, year-only dates, unplaceable fragments) belong to the Candidate and are identical across layouts; positional traps (PII in a footer, text boxes, scrambled order, confusable characters) belong to the Layout. The expected answer therefore never varies per layout.

**Consequence:** the golden set proves the pipeline against documents we designed. A separate source-coverage test asserts every fixture string appears in each generated document, so a generator bug cannot masquerade as a pipeline failure.
