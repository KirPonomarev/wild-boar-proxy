# Repair Plan

1. Keep the repair inside the sandbox owner helper boundary.
2. Normalize auth kind from `type` or legacy `auth_mode`, with a narrow fallback to `apikey` when `OPENAI_API_KEY` is present.
3. Reuse the existing field requirements for `codex` and `apikey`; do not change reserve-first onboarding semantics.
4. Prove compatibility with targeted helper-lane tests and a live read-only admissibility check on the current sandbox auth file.
