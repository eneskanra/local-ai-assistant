
from typing import TypedDict

class AgentState(TypedDict):
    question: str
    schema: str
    sql: str
    validated_sql: str
    error: str
    attempts: int



from langgraph.graph import StateGraph, START, END

from sql_assistant import (
    db,
    generate_sql,
    validate_sql
)


def get_schema_node(state: AgentState):
    print("\n[1] Veritabanı şeması alınıyor...")

    return {
        "schema": db.get_table_info()
    }


def generate_sql_node(state: AgentState):
    attempt = state["attempts"] + 1

    print(f"\n[2] SQL üretiliyor (deneme {attempt})...")

    question = state["question"]

    if state["error"]:
        question += (
            "\nÖnceki SQL doğrulama hatası: "
            + state["error"]
            + "\nLütfen kurallara uygun yeni SQL üret."
        )

    sql = generate_sql(question)

    print("Üretilen SQL:", sql)

    return {
        "sql": sql,
        "attempts": attempt,
        "error": "",
        "validated_sql": ""
    }


def validate_sql_node(state: AgentState):
    print("\n[3] SQL doğrulanıyor...")

    try:
        validated = validate_sql(state["sql"])

        print("SQL doğrulandı.")

        return {
            "validated_sql": validated,
            "error": ""
        }

    except Exception as e:
        print("Doğrulama hatası:", str(e))

        return {
            "validated_sql": "",
            "error": str(e)
        }


def route_after_validation(state: AgentState):
    if state["validated_sql"]:
        return "success"

    if state["attempts"] < 3:
        return "retry"

    return "failed"



builder = StateGraph(AgentState)

# Node'ları kaydet
builder.add_node("get_schema", get_schema_node)
builder.add_node("generate_sql", generate_sql_node)
builder.add_node("validate_sql", validate_sql_node)

# Normal geçişler
builder.add_edge(START, "get_schema")
builder.add_edge("get_schema", "generate_sql")
builder.add_edge("generate_sql", "validate_sql")

# Koşullu geçişler
builder.add_conditional_edges(
    "validate_sql",
    route_after_validation,
    {
        "success": END,
        "retry": "generate_sql",
        "failed": END
    }
)

# Grafiği derle
graph = builder.compile()


if __name__ == "__main__":
    initial_state = {
        "question": "En fazla satış yapan 3 müşteriyi getir.",
        "schema": "",
        "sql": "",
        "validated_sql": "",
        "error": "",
        "attempts": 0
    }

    result = graph.invoke(
        initial_state,
        config={"recursion_limit": 15}
    )

    print("\n===== SONUÇ =====")

    if result["validated_sql"]:
        print("Başarılı SQL:")
        print(result["validated_sql"])
    else:
        print("SQL üretilemedi.")
        print("Son hata:", result["error"])

    print("Toplam deneme:", result["attempts"])
