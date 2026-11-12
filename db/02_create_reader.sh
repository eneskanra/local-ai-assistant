#!/bin/bash
# AI uygulaması için salt okunur kullanıcıyı oluşturur.
# Şifre, docker-compose üzerinden gelen READER_PASSWORD
# ortam değişkeninden okunur (init.sql env okuyamadığı için).
set -e

psql -v ON_ERROR_STOP=1 \
     -v reader_password="$READER_PASSWORD" \
     --username "$POSTGRES_USER" \
     --dbname "$POSTGRES_DB" <<-'EOSQL'
    CREATE ROLE ai_reader LOGIN PASSWORD :'reader_password';

    GRANT CONNECT ON DATABASE salesdb TO ai_reader;
    GRANT USAGE ON SCHEMA public TO ai_reader;
    GRANT SELECT ON ALL TABLES IN SCHEMA public TO ai_reader;

    -- Gelecekte oluşturulacak tablolar için
    ALTER DEFAULT PRIVILEGES FOR ROLE admin IN SCHEMA public
    GRANT SELECT ON TABLES TO ai_reader;

    -- Ek güvenlik: oturumları varsayılan olarak read-only yap
    ALTER ROLE ai_reader SET default_transaction_read_only = on;
    ALTER ROLE ai_reader SET statement_timeout = '10s';
EOSQL
