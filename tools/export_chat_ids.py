import argparse
import sqlite3
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Ambil Telegram Chat ID dari database "
            "Kabar Saham V5.4 lama."
        )
    )
    parser.add_argument(
        "database",
        nargs="?",
        default="ma_alert.db",
    )
    args = parser.parse_args()

    path = Path(args.database)

    if not path.exists():
        raise SystemExit(
            f"Database tidak ditemukan: {path}"
        )

    conn = sqlite3.connect(path)

    try:
        rows = conn.execute(
            "SELECT chat_id FROM subscribers "
            "ORDER BY created_at"
        ).fetchall()
    except sqlite3.Error as exc:
        raise SystemExit(
            f"Tabel subscribers tidak dapat dibaca: {exc}"
        )
    finally:
        conn.close()

    ids = [
        str(row[0])
        for row in rows
    ]

    if not ids:
        raise SystemExit(
            "Tidak ada Chat ID di database. "
            "Jalankan /start pada bot V5.4 terlebih dahulu."
        )

    print(",".join(ids))


if __name__ == "__main__":
    main()
