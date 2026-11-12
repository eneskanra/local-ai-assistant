"""
Uygulama yapılandırması.

Bağlantı bilgileri .env dosyasından okunur.
Örnek değerler için .env.example dosyasına bakın.
"""

import os

from dotenv import load_dotenv

load_dotenv()


def _require(name: str) -> str:
    value = os.getenv(name)

    if not value:
        raise RuntimeError(
            f"{name} ortam değişkeni tanımlı değil. "
            ".env.example dosyasını .env olarak kopyalayıp doldurun."
        )

    return value


DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = os.getenv("DB_PORT", "5433")
DB_NAME = os.getenv("DB_NAME", "salesdb")

# Salt okunur AI kullanıcısı (SQL sorguları için)
READER_USER = os.getenv("READER_USER", "ai_reader")
READER_PASSWORD = _require("READER_PASSWORD")

DB_URL = (
    f"postgresql+psycopg://{READER_USER}:{READER_PASSWORD}"
    f"@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)
