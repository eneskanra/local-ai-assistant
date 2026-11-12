

from typing import TypedDict, Any
from uuid import uuid4

from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt, Command
from langgraph.checkpoint.memory import InMemorySaver

from sql_assistant import (
    db,
    generate_sql,
    validate_sql,
    execute_sql,
    generate_answer
)


class AgentState(TypedDict):
    question: str
    schema: str
    sql: str
    validated_sql: str
    error: str
    attempts: int
    approved: bool
    rows: list[dict[str, Any]]
    answer: str



def get_schema_node(state: AgentState):
    print("\n[1] Schema okunuyor...")
    return {"schema": db.get_table_info()}


def generate_sql_node(state: AgentState):
    attempt = state["attempts"] + 1
    print(f"\n[2] SQL üretiliyor (deneme {attempt})...")

    question = state["question"]

    if state["error"]:
        question += (
            "\nÖnceki denemedeki doğrulama hatası: "
            + state["error"]
            + "\nLütfen SQL'i düzelt."
        )

    sql = generate_sql(question)
    print(sql)

    return {
        "sql": sql,
        "attempts": attempt,
        "validated_sql": "",
        "error": ""
    }


def validate_sql_node(state: AgentState):
    print("\n[3] SQL doğrulanıyor...")

    try:
        safe_sql = validate_sql(state["sql"])
        return {
            "validated_sql": safe_sql,
            "error": ""
        }
    except Exception as e:
        return {
            "validated_sql": "",
            "error": str(e)
        }


def route_validation(state: AgentState):
    if state["validated_sql"]:
        return "approved_path"

    if state["attempts"] < 3:
        return "retry"

    return "failed"


def approval_node(state: AgentState):
    print("\n[4] Kullanıcı onayı bekleniyor...")

    decision = interrupt({
        "question": state["question"],
        "sql": state["validated_sql"],
        "message": "Bu SQL sorgusu çalıştırılsın mı?"
    })

    return {"approved": decision is True}


def route_approval(state: AgentState):
    return "execute" if state["approved"] else "cancel"


def execute_sql_node(state: AgentState):
    print("\n[5] PostgreSQL sorgusu çalıştırılıyor...")

    rows = execute_sql(state["validated_sql"])

    print(f"{len(rows)} kayıt döndü.")

    return {"rows": rows}


def answer_node(state: AgentState):
    print("\n[6] Qwen3 yanıt oluşturuyor...")

    answer = generate_answer(
        state["question"],
        state["validated_sql"],
        state["rows"]
    )

    return {"answer": answer}



builder = StateGraph(AgentState)

builder.add_node("get_schema", get_schema_node)
builder.add_node("generate_sql", generate_sql_node)
builder.add_node("validate_sql", validate_sql_node)
builder.add_node("approval", approval_node)
builder.add_node("execute_sql", execute_sql_node)
builder.add_node("answer", answer_node)

builder.add_edge(START, "get_schema")
builder.add_edge("get_schema", "generate_sql")
builder.add_edge("generate_sql", "validate_sql")

builder.add_conditional_edges(
    "validate_sql",
    route_validation,
    {
        "approved_path": "approval",
        "retry": "generate_sql",
        "failed": END
    }
)

builder.add_conditional_edges(
    "approval",
    route_approval,
    {
        "execute": "execute_sql",
        "cancel": END
    }
)

builder.add_edge("execute_sql", "answer")
builder.add_edge("answer", END)

# Geliştirme ortamı için bellek tabanlı checkpoint
checkpointer = InMemorySaver()

graph = builder.compile(checkpointer=checkpointer)



def main():
    question = input("Sorunuz: ").strip()

    if not question:
        return

    initial_state = {
        "question": question,
        "schema": "",
        "sql": "",
        "validated_sql": "",
        "error": "",
        "attempts": 0,
        "approved": False,
        "rows": [],
        "answer": ""
    }

    # Her çalıştırma için ayrı thread
    config = {
        "configurable": {
            "thread_id": str(uuid4())
        },
        "recursion_limit": 20
    }

    result = graph.invoke(initial_state, config=config)

    # Interrupt varsa kullanıcı onayı al
    if result.get("__interrupt__"):
        request = result["__interrupt__"][0].value

        print("\n===== ONAY İSTEĞİ =====")
        print(request["message"])
        print("\nSQL:")
        print(request["sql"])

        approval = input("\nOnaylıyor musunuz? (e/h): ")
        approved = approval.strip().lower() == "e"

        result = graph.invoke(
            Command(resume=approved),
            config=config
        )

    print("\n===== SONUÇ =====")

    if result.get("answer"):
        print(result["answer"])
    elif result.get("approved"):
        print("Onaylandı ancak yanıt oluşturulamadı.")
    elif result.get("validated_sql"):
        print("Sorgu kullanıcı tarafından iptal edildi.")
    else:
        print("SQL doğrulaması başarısız.")
        print(result.get("error"))


if __name__ == "__main__":
    main()
