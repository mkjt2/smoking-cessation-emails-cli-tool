# CLAUDE.md

Single-file Python 3 CLI (`send.py`, stdlib only) that renders a newsletter template per recipient. `SPEC.md` is the source of truth for behavior; `README.md` documents usage.

- Run tests: `python3 -m unittest discover -s tests` (pytest is not installed; tests use `unittest`).
- No third-party dependencies. Keep it that way unless the spec requires otherwise.
- User-facing errors are raised as `SendError` and reported by `main()` on stderr with exit code 1. Validate all input before writing any output.
