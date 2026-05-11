Contour `OWNER_SURFACE_SEQUENCE_ADMISSION_DIAGNOSIS_CONTOUR` closed read-only.

Observed result:
- the repeated mismatch between `sync --json` and `launch smoke --json` is
  factual and preserved
- owner-surface review shows the two commands own different truth lanes
- no repo-owned contradiction is yet proven strongly enough to skip the
  composite proof sequence

Decision:
- do not reopen blind `sync-only` or `launch-smoke-only` loops
- the next lawful contour is an explicitly admitted bounded composite proof
  contour:
  `sync --json -> launch smoke --json`
- if that contour fails to produce simultaneous green runtime truth and green
  rotation evidence, open `OWNER_SURFACE_CONTRADICTION_REPAIR_CONTOUR`
