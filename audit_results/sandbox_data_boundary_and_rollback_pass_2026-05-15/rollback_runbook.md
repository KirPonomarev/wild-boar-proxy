# Rollback Runbook

## Snapshot point before first external write

Before any sandbox filesystem mutation outside repo:

1. record existence and metadata of `/Users/kirillponomarev/.codex-custom-test`
2. record non-existence or existence of the planned WBP sandbox paths under that root
3. record that no paths under `/Users/kirillponomarev/.codex-custom-cli` or `/Users/kirillponomarev/.cli-proxy-api` are modified

## Minimal approved execution shape

If owner gate is later passed, the first allowed writes should be limited to:

1. create `/Users/kirillponomarev/.codex-custom-test/managed`
2. create empty or baseline sandbox files under the candidate sandbox root only
3. create sandbox-local `stable/config.yaml`
4. create sandbox-local `external-models` skeleton

## Rollback steps

If sandbox prep writes start and must be reverted:

1. remove only sandbox-local files created under `/Users/kirillponomarev/.codex-custom-test/managed`
2. remove only sandbox-local `stable` subtree created by the contour
3. remove only sandbox-local `external-models` subtree created by the contour
4. remove only sandbox-local launcher file created by the contour
5. verify no mtimes changed under `/Users/kirillponomarev/.codex-custom-cli`
6. verify `/Users/kirillponomarev/.cli-proxy-api/config.yaml` checksum unchanged

## Residue check

After rollback or teardown, verify:

- no new WBP-managed files remain under `/Users/kirillponomarev/.codex-custom-test`
- no files under `/Users/kirillponomarev/.codex-custom-cli` changed
- no files under `/Users/kirillponomarev/.cli-proxy-api` changed

## Current contour status

Rollback design is defined, but it is not yet exercised because owner gate is not passed and execution phase never started.
