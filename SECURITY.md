# Security

Jangan pernah commit:
- `.env`
- Telegram Bot Token
- Telegram Chat ID
- database V5.4
- password / private key

GitHub Secrets yang dibutuhkan:
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_IDS`

Repository publik membuat **source code terlihat publik**, tetapi GitHub Secrets
tidak disimpan di source code dan tidak boleh dicetak ke log.

Workflow paket ini tidak dijalankan pada `pull_request`, sehingga secrets tidak
dibutuhkan untuk kode dari fork/pull request.
