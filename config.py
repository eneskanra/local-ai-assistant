"""
Uygulama yapılandırması.

Bağlantı bilgileri .env dosyasından okunur.
Örnek değerler için .env.example dosyasına bakın.
"""

import os
from urllib.parse import quote_plus

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

# 6.7 — Konuşma hafızası (LangGraph checkpoint) için ayrı DB ve yazma kullanıcısı
MEMORY_USER = os.getenv("MEMORY_USER", "ai_memory")
MEMORY_DB_NAME = os.getenv("MEMORY_DB_NAME", "agent_memory")


def get_memory_db_url() -> str:
    """
    Checkpoint bağlantı adresini döndürür.

    Fonksiyon olarak tutuldu; böylece MEMORY_PASSWORD yalnızca
    v5 agent kullanıldığında zorunlu olur, v4/app.py etkilenmez.
    """
    password = quote_plus(_require("MEMORY_PASSWORD"))

    return (
        f"postgresql://{MEMORY_USER}:{password}"
        f"@{DB_HOST}:{DB_PORT}/{MEMORY_DB_NAME}"
    )
