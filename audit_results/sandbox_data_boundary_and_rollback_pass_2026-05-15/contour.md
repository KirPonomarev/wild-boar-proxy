# SANDBOX_DATA_BOUNDARY_AND_ROLLBACK_PASS

## Goal

Map the live Wild Boar / Codex custom runtime paths, classify which surfaces are forbidden or must be isolated, design a sandbox topology, and determine whether external filesystem writes can begin safely.

## Outcome posture

This contour intentionally separates design from execution. Read-only discovery and boundary design are complete when the path map, write surfaces, and rollback requirements are explicit. External writes begin only after a hard owner gate.
