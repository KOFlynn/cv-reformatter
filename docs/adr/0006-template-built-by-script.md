# The output template is built by a script, never hand-edited in Word

The brief says the template is "designed in Word". We build it instead with a committed python-docx script (`templates/build_template.py`) that writes `templates/fictitious_recruitment.docx` with its docxtpl tags, and the generated file is committed alongside it. The rule is: never hand-edit the output; change the script and regenerate.

**Why:** Word silently splits `{{ }}` and `{%p %}` tags across runs when you type them, which breaks docxtpl in ways that only show at render time and are invisible in the document. A script guarantees each tag sits in one run, makes the template diffable and reproducible, and keeps branding as code. The cost is a plainer design; branding is deliberately modest (a text wordmark, one accent colour, one font, no logo image) because nothing on the gap list is evidenced by a prettier template. The red review-appendix banner is the one visual element that matters for the demo.

**Amendment (Phase 0, ticket 06):** the script lives at `src/cvr/template/build.py` and runs as `python -m cvr.template.build`, not at `templates/build_template.py`, because the Phase 0 spec makes `cvr` the one import root and keeps `templates/` for data only. The output path and the never-hand-edit rule are unchanged.
