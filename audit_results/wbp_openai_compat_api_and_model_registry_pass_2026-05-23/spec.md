# WBP_OPENAI_COMPAT_API_AND_MODEL_REGISTRY_PASS

## Goal

Prove the readonly OpenAI-compatible model registry path for Codex Custom through WBP without inference, provider calls, account rotation, session management, or token burn.

## Scope

- Add a server-side Codex Custom model registry packet.
- Expose `/api/codex/custom/models`, `/api/codex/custom/api-compat`, and `/api/codex/custom/model-dry-run`.
- Render a bounded `Codex Custom Models` web panel.
- Allow browser payload to send only server-issued `model_id`.
- Keep `route_id`, `backend_id`, provider, endpoint, path, auth, and secret fields forbidden.

## Out Of Scope

- `/v1/responses` proof.
- `/v1/chat/completions` proof.
- GPT account inference proof.
- External provider inference proof.
- Codex Custom session manager.
- Original Codex launch mutation.
- Current Codex mutation.

## Success Criteria

- `/v1/models` registry is visible as fresh truth.
- `/v1/responses` and `/v1/chat/completions` are explicitly `not_called_in_this_contour`.
- Model dry-run accepts only a server-issued model.
- Dry-run proves `inference_called=false`, `provider_called=false`, `responses_called=false`, `chat_completions_called=false`, and `token_burn=0`.
- Claim gate blocked remains degraded and is not rendered as global success.
- Browser proof captures the panel and dry-run packet.
