#!/bin/bash
# LangGraph checkpoint'leri için ayrı veritabanı ve yazma kullanıcısı.
# ai_reader read-only olduğu için hafıza ayrı bir kullanıcıyla yazılır.
# Şifre, docker-compose üzerinden gelen MEMORY_PASSWORD değişkeninden okunur.
#
# Mevcut (daha önce init edilmiş) volume için elle bir kez çalıştırın:
#   docker exec -i local-ai-postgres bash < db/03_create_memory.sh
set -e

psql -v ON_ERROR_STOP=1 \
     -v memory_password="$MEMORY_PASSWORD" \
     --username "$POSTGRES_USER" \
     --dbname "$POSTGRES_DB" <<-'EOSQL'
    CREATE ROLE ai_memory LOGIN PASSWORD :'memory_password';
    CREATE DATABASE agent_memory OWNER ai_memory;

    -- Satış verisine erişimi yok
    REVOKE CONNECT ON DATABASE agent_memory FROM PUBLIC;
EOSQL
