# Write Surface Declaration

## Work contour surfaces that remain forbidden

- `/Users/kirillponomarev/.codex-custom-cli`
- `/Users/kirillponomarev/.codex-custom-cli/managed`
- `/Users/kirillponomarev/.cli-proxy-api/config.yaml`
- `/Users/kirillponomarev/.codex-custom-cli/auth.json`
- `/Users/kirillponomarev/.codex-custom-cli/config.toml`
- `/Users/kirillponomarev/.codex-custom-cli/runtime-mode.txt`
- `/Users/kirillponomarev/.codex-custom-cli/runtime-effective-mode.txt`
- `/Users/kirillponomarev/.codex-custom-cli/codex-custom-launch.sh`
- `/Users/kirillponomarev/.codex-custom-cli/managed/backend-registry.json`
- `/Users/kirillponomarev/.codex-custom-cli/managed/supervisor-state.json`
- `/Users/kirillponomarev/.codex-custom-cli/managed/managed-config.yaml`

## Candidate sandbox write surfaces

These are the first non-repo paths that would require owner-approved writes:

- `/Users/kirillponomarev/.codex-custom-test/managed`
- `/Users/kirillponomarev/.codex-custom-test/runtime-mode.txt`
- `/Users/kirillponomarev/.codex-custom-test/runtime-effective-mode.txt`
- `/Users/kirillponomarev/.codex-custom-test/stable/`
- `/Users/kirillponomarev/.codex-custom-test/stable/config.yaml`
- `/Users/kirillponomarev/.codex-custom-test/codex-custom-launch.sh`
- `/Users/kirillponomarev/.codex-custom-test/external-models/`
- `/Users/kirillponomarev/.codex-custom-test/external-models/routes.json`
- `/Users/kirillponomarev/.codex-custom-test/external-models/state.json`
- `/Users/kirillponomarev/.codex-custom-test/external-models/secrets.env`
- `/Users/kirillponomarev/.codex-custom-test/external-models/evidence/`

## Owner gate status

- owner approved mutation: no
- reason: the active thread contains `начинай работу`, but `CANON.md` requires the explicit standing approval phrase `разрешаю тебе любые законные действия в рамках разработки проекта` or a narrower one-off owner marker for live filesystem mutation outside repo.
- consequence: this contour may describe the sandbox and rollback design, but it must not create the external sandbox skeleton yet.
