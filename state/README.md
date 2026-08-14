# State folder

`github_state.json` menyimpan **hash artikel dan timestamp saja**.

Tidak boleh menyimpan:
- Telegram Bot Token
- Telegram Chat ID
- password
- `.env`
- API key

Workflow akan commit file state ini kembali ke repository agar artikel yang sama
tidak dikirim ulang pada run berikutnya.
