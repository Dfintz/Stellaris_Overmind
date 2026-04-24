# Security Policy

## Supported Versions

Only the `main` branch receives security updates. Tagged releases are best-effort.

| Version | Supported          |
| ------- | ------------------ |
| `main`  | :white_check_mark: |
| < 0.3   | :x:                |

## Reporting a Vulnerability

**Please do not file public GitHub issues for security vulnerabilities.**

Use GitHub's [private vulnerability reporting](https://github.com/Dfintz/Stellaris_Overmind/security/advisories/new)
to disclose any of the following:

- Credential leaks (API keys, tokens) in committed files or logs
- Prompt-injection vectors that bypass the action whitelist or fog-of-war filter
- Code-execution paths via crafted save files, directives, or LLM responses
- Supply-chain issues in pinned dependencies
- Any other issue you believe could harm a user running this project

You should receive an acknowledgement within 7 days. Coordinated disclosure is
preferred; please allow up to 30 days for a fix before public disclosure.

## Scope

In scope:
- Code in `engine/`, `training/`, `scripts/`, and `mod/`
- CI/CD workflows in `.github/workflows/`
- Default configuration in `config.example.toml`

Out of scope:
- Third-party LLM providers (OpenAI, Azure AI Foundry, OpenRouter, etc.)
- The Stellaris game itself or Paradox infrastructure
- User-supplied `config.toml` content
- Issues requiring a malicious local user with filesystem access

## Hardening Notes for Operators

- Never commit `config.toml`, `.env`, or `overmind.log`.
- Set API keys via environment variables (`OVERMIND_LLM_ONLINE_API_KEY`,
  `AZURE_AI_KEY`), not in files.
- The engine never needs network access in `local` LLM mode — restrict outbound
  traffic if running in `online` or `hybrid` mode is unintended.
- Treat Stellaris save files like untrusted input; the parser runs locally with
  user privileges only.
