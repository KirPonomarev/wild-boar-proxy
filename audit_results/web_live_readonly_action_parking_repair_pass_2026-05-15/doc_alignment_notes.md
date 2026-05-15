# WEB_LIVE_READONLY_ACTION_PARKING_REPAIR_PASS Doc Alignment

- `wild_boar_proxy/web_design_ui/README.md` no longer claims a blanket
  "no action buttons" behavior.
- It now states the exact repaired phase rule:
  - mutation and support-artifact action buttons stay disabled
  - only readonly support actions remain available
- This matches the current default action phase in
  `wild_boar_proxy/web_design_live_server.py`.
