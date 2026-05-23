# Recommended Next Contour

## Verdict

`desktop_official_wrapper_rejected_needs_custom_bundle`

## Next Contour

`CODEX_CUSTOM_APP_DRY_RUN_ISOLATION_PASS`

## Why

The official installed `Codex.app` wrapper path is not safe enough for the next
experiment. It has fixed identity `com.openai.codex`, fixed `codex` URL scheme,
single-instance behavior, and prior evidence of touching default
`com.openai.codex` storage even with a separate `CODEX_HOME` and
`--user-data-dir`.

The next practical experiment should be a dry-run only:

- no prompt,
- no WBP request,
- no provider/auth use beyond optional redacted config path presence,
- no persistent registration,
- no official bundle mutation,
- no current Codex mutation.

## Required Shape

Build or stage a disposable copied/renamed `Codex Custom.app` candidate in a lab
directory, with:

- distinct bundle id, for example `local.wbp.codex-custom.lab`;
- distinct display/name, for example `Codex Custom Lab`;
- removed or distinct URL scheme;
- distinct Electron userData/cache root;
- temp `CODEX_HOME`;
- explicit launcher log path under temp/lab dir;
- no prompt until isolation is proven.

## Required Proof

- screenshot or window/process proof only after launch;
- `ps` process tree;
- `lsof` open-file sample for the custom process;
- pre/post stat or hash for current `~/.codex` config/auth;
- pre/post check for default Codex storage paths;
- no socket/process collision with current Codex;
- cleanup proof.

## Stop Conditions

- custom/copy app opens the existing current Codex window;
- custom/copy app touches default `~/Library/Application Support/Codex`;
- custom/copy app touches default `~/Library/Caches/com.openai.codex`;
- custom/copy app touches default `~/Library/HTTPStorages/com.openai.codex`;
- current `~/.codex` changes;
- LaunchServices or URL scheme registration mutates official `codex` handling;
- any prompt/API request is needed before isolation proof.
