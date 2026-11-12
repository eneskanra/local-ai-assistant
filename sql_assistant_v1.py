
import re

import sqlglot
from sqlglot import exp

from sqlalchemy import create_engine, text
from langchain_community.utilities import SQLDatabase
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from config import DB_URL

# 1. Veritabanı bağlantısı
engine = create_engine(DB_URL)

db = SQLDatabase(
    engine,
    include_tables=[
        "customers",
        "products",
        "orders",
        "order_items"
    ],
    sample_rows_in_table_info=2
)

# 2. Yerel model
llm = ChatOllama(
    model="qwen3:8b",
    temperature=0,
    reasoning=False
)

# 3. SQL üretim prompt'u
prompt = ChatPromptTemplate.from_messages([
    ("system", """
Sen uzman bir PostgreSQL geliştiricisisin.

Görevin kullanıcının sorusuna karşılık
doğru bir PostgreSQL SELECT sorgusu üretmek.

Kurallar:
- Sadece SQL sorgusu döndür.
- Markdown kullanma.
- Açıklama ekleme.
- Yalnızca verilen tablo ve sütunları kullan.
- Tablo ilişkilerini doğru kur.
- Satış tutarı = quantity * unit_price.
- Kullanıcı belirtmedikçe tarih filtresi ekleme.
- INSERT, UPDATE, DELETE, DROP gibi
  veri değiştiren işlemler üretme.
- Detay sorgularını en fazla 50 satırla sınırla.
- Toplam satış veya benzeri metrikler
    hesaplandığında, kullanıcı aksini istemedikçe
    sonuçları ilgili metriğe göre azalan sırada sırala.

Veritabanı şeması:
{schema}
"""),
    ("human", "{question}")
])

# 4. LangChain zinciri
chain = prompt | llm | StrOutputParser()


def generate_sql(question):
    schema = db.get_table_info()

    sql = chain.invoke({
        "schema": schema,
        "question": question
    })

    # Modelin olası Markdown biçimlendirmesini temizle
    sql = re.sub(
        r"^```(?:sql)?\s*|\s*```$",
        "",
        sql.strip(),
        flags=re.IGNORECASE
    ).strip()

    return sql


def validate_sql(sql):
    """Basit eğitim senaryosu için SQL kontrolü."""

    statements = sqlglot.parse(sql, read="postgres")

    if len(statements) != 1 or statements[0] is None:
        raise ValueError("Yalnızca tek SQL sorgusu kabul edilir.")

    ast = statements[0]

    if not isinstance(ast, exp.Select):
        raise ValueError("Yalnızca SELECT sorguları kabul edilir.")

    # Bu eğitim sürümünde CTE, alt sorgu ve
    # karmaşık SQL yapıları kullanılmayacak.
    if ast.find(exp.With, exp.Subquery, exp.Union):
        raise ValueError("Karmaşık sorgular henüz desteklenmiyor.")

    forbidden = (
        exp.Insert, exp.Update, exp.Delete,
        exp.Drop, exp.Create, exp.Alter,
        exp.Command, exp.Copy
    )

    for node in ast.walk():
        if isinstance(node, forbidden):
            raise ValueError("İzin verilmeyen SQL işlemi.")

    allowed_tables = {
        "customers", "products",
        "orders", "order_items"
    }

    for table in ast.find_all(exp.Table):
        if table.name not in allowed_tables or table.db:
            raise ValueError("İzin verilmeyen tablo.")

    # Satır sayısı sınırı
    limit = ast.args.get("limit")

    if limit is None:
        ast = ast.limit(50)

    return ast.sql(dialect="postgres")


def execute_sql(sql):
    # Veritabanı düzeyinde read-only işlem
    with engine.connect() as conn:
        with conn.begin():
            conn.execute(
                text("SET TRANSACTION READ ONLY")
            )

            result = conn.execute(text(sql))
            rows = result.mappings().fetchmany(50)

            return [dict(row) for row in rows]


def main():
    print("Local AI Database Assistant")
    print("Çıkış için q yazın.\n")

    while True:
        question = input("Sorunuz: ").strip()

        if question.lower() == "q":
            break

        if not question:
            continue

        try:
            sql = generate_sql(question)
            print("\nÜretilen SQL:\n", sql)

            safe_sql = validate_sql(sql)
            print("\nKontrol edilen SQL:\n", safe_sql)

            approval = input(
                "\nSorgu çalıştırılsın mı? (e/h): "
            ).strip().lower()

            if approval != "e":
                print("Sorgu iptal edildi.\n")
                continue

            rows = execute_sql(safe_sql)

            print("\nSonuçlar:")
            for row in rows:
                print(row)

            print(f"\nGösterilen kayıt sayısı: {len(rows)}\n")

        except Exception as error:
            print(f"\nHata: {error}\n")


if __name__ == "__main__":
    main()
