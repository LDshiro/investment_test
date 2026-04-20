# Secrets Handling v1

This repo does not need real broker secrets for current shadow-only work.

- `.env.example` is a template only and must contain placeholders, not real values.
- Future broker secrets must live outside git in the user environment or a local secret manager.
- Do not print secret values in logs, reports, screenshots, or AI prompts.
- Do not store API passwords, tokens, private keys, or account identifiers in committed files.
- If a real secret is exposed locally, rotate it outside this repo and treat the event as an incident.

## Current allowed practice

- Shadow and dry-run workflows may run without broker secrets.
- Broker candidate research and null-adapter dry-run do not authorize credential entry.
- Any future paper/live secret workflow requires a separate human-reviewed design step.
