# .docx input only for the first build

PDF input roughly doubles the parsing work (layout recovery, reading order, no structural markers) and evidences nothing on the project's gap list. The first build accepts `.docx` only and produces `.docx` only. PDF is a possible later phase, and the parse node boundary is where it would slot in.
