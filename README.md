# Kabar Saham V6.0 — GitHub Actions Free Edition

Auto scanner corporate action berbasis core V5.4.

## Start
Baca **`MULAI_DI_SINI_GITHUB.txt`**.

## Required GitHub Secrets
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_IDS`

## Scheduled scan
Workflow: `.github/workflows/kabar_saham_v6.yml`

Approx. every 10 minutes at minutes:
`07, 17, 27, 37, 47, 57`.

## Persistent state
`state/github_state.json` contains article hashes/timestamps only.

**Never commit `.env`, Telegram credentials, or the old SQLite database.**
