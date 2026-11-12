
from sqlalchemy import create_engine, text
from langchain_community.utilities import SQLDatabase

from config import DB_URL

# 1. SQLAlchemy bağlantısı
engine = create_engine(DB_URL)

with engine.connect() as conn:
    result = conn.execute(
        text("SELECT COUNT(*) FROM orders")
    )
    print("Sipariş sayısı:", result.scalar())

# 2. LangChain SQLDatabase bağlantısı
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

print("\nTablolar:")
print(db.get_usable_table_names())

print("\nOrders tablo şeması:")
print(db.get_table_info(["orders"]))
