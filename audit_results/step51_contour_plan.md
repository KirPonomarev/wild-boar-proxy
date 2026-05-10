# Step51 Contour Plan

- Contour:
  - `PRIMARY_BLOCKER_RECLASSIFICATION_FROM_CLEAN_OWNER_SNAPSHOT`
- Goal:
  - select one primary blocker from the clean `step50` owner snapshot basis
- Mode:
  - read-only classification
- Allowed:
  - blocker-domain mapping
  - blocker ranking
  - one bounded reread of one unstable signal only
- Forbidden:
  - any live mutation
  - onboarding retry
  - reserve recovery mutation
  - stage advance
  - UI work
