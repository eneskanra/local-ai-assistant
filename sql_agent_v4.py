

from typing import TypedDict, Any
from uuid import uuid4

from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt, Command
from langgraph.checkpoint.memory import InMemorySaver
from sqlalchemy.exc import DBAPIError

from sql_assistant import (
    db,
    generate_sql,
    validate_sql,
    execute_sql,
    generate_answer
)

from observability import trace_node


# import time
# from functools import wraps


# def trace_node(name, function):
#     @wraps(function)
#     def wrapper(state):
#         start = time.perf_counter()

#         print(f"\n[TRACE] {name} başladı")

#         try:
#             result = function(state)
#             return result

#         finally:
#             elapsed = time.perf_counter() - start

#             print(
#                 f"[TRACE] {name} tamamlandı/ayrıldı "
#                 f"({elapsed:.3f} saniye)"
#             )

#     return wrapper



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

    # Yeni alanlar
    execution_error: str
    execution_success: bool
    retryable_error: bool



def get_schema_node(state: AgentState):
    print("\n[1] Schema okunuyor...")
    return {"schema": db.get_table_info()}



def generate_sql_node(state: AgentState):
    attempt = state["attempts"] + 1

    print(f"\n[2] SQL üretiliyor (deneme {attempt})...")

    question = state["question"]

    # Önceki denemeden kalan hata bilgisi
    previous_error = (
        state.get("execution_error")
        or state.get("error")
    )

    if previous_error:
        question += f"""

        Önceki SQL sorgusu başarısız oldu.

        Önceki SQL:
        {state.get("sql", "")}

        Hata mesajı:
        {previous_error}

        Lütfen veritabanı şemasını dikkate alarak
        hatalı SQL sorgusunu düzelt.

        Yalnızca yeni PostgreSQL SELECT sorgusunu üret.
        """

    sql = generate_sql(question)


    print("Üretilen SQL:\n", sql)

    return {
        "sql": sql,
        "attempts": attempt,
        "validated_sql": "",
        "error": "",
        "execution_error": "",
        "execution_success": False,
        "retryable_error": False,
        "approved": False,
        "rows": [],
        "answer": ""
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



def route_after_execution(state: AgentState):

    # SQL başarıyla çalıştı
    if state["execution_success"]:
        return "success"

    # Düzeltilebilir SQL hatası ve deneme hakkı var
    if (
        state["retryable_error"]
        and state["attempts"] < 3
    ):
        return "retry"

    # Düzeltilemeyen hata veya deneme sınırı
    return "failed"


# PostgreSQL SQLSTATE hata kodları
RETRYABLE_SQLSTATES = {
    "42703",  # undefined_column
    "42P01",  # undefined_table
    "42702",  # ambiguous_column
    "42803",  # grouping_error
    "42883",  # undefined_function
    "42804",  # datatype_mismatch
}


def execute_sql_node(state: AgentState):
    print("\n[5] PostgreSQL sorgusu çalıştırılıyor...")

    try:
        rows = execute_sql(state["validated_sql"])

        print(f"{len(rows)} kayıt döndü.")

        return {
            "rows": rows,
            "execution_success": True,
            "execution_error": "",
            "retryable_error": False
        }

    except DBAPIError as exc:
        # SQLAlchemy üzerinden gelen PostgreSQL hata kodu
        sqlstate = getattr(exc.orig, "sqlstate", None)

        retryable = sqlstate in RETRYABLE_SQLSTATES

        # Model için kontrollü hata bilgisi
        if retryable:
            message = str(exc.orig).splitlines()[0][:300]
        else:
            message = "Veritabanı veya yetki hatası."

        print(f"\nSQL hatası: {message}")
        print(f"SQLSTATE: {sqlstate}")
        print(f"Yeniden denenebilir: {retryable}")

        return {
            "rows": [],
            "execution_success": False,
            "execution_error": message,
            "retryable_error": retryable
        }



def answer_node(state: AgentState):
    print("\n[6] Qwen3 yanıt oluşturuyor...")

    answer = generate_answer(
        state["question"],
        state["validated_sql"],
        state["rows"]
    )

    return {"answer": answer}



builder = StateGraph(AgentState)


builder.add_node(
    "get_schema",
    trace_node("get_schema", get_schema_node)
)

builder.add_node(
    "generate_sql",
    trace_node("generate_sql", generate_sql_node)
)

builder.add_node(
    "validate_sql",
    trace_node("validate_sql", validate_sql_node)
)

builder.add_node(
    "approval",
    trace_node("approval", approval_node)
)

builder.add_node(
    "execute_sql",
    trace_node("execute_sql", execute_sql_node)
)

builder.add_node(
    "answer",
    trace_node("answer", answer_node)
)


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

# builder.add_edge("execute_sql", "answer")

builder.add_conditional_edges(
    "execute_sql",
    route_after_execution,
    {
        "success": "answer",
        "retry": "generate_sql",
        "failed": END
    }
)

builder.add_edge("answer", END)

# Geliştirme ortamı için bellek tabanlı checkpoint
checkpointer = InMemorySaver()

graph = builder.compile(checkpointer=checkpointer)



def run_graph_stream(input_data, config):
    print("\n===== GRAPH STREAM =====")

    for event in graph.stream(
        input_data,
        config=config,
        stream_mode="updates"
    ):
        for node_name, update in event.items():

            if node_name == "__interrupt__":
                print("\n[STREAM] Kullanıcı onayı bekleniyor")
                continue

            print(f"\n[STREAM] Tamamlanan node: {node_name}")

            if isinstance(update, dict):
                print(
                    "[STREAM] Güncellenen alanlar:",
                    list(update.keys())
                )

    # Son checkpoint'teki State'i al
    snapshot = graph.get_state(config)

    result = dict(snapshot.values)

    # Interrupt bilgisini sonuç nesnesine ekle
    if snapshot.interrupts:
        result["__interrupt__"] = snapshot.interrupts

    return result




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
        "answer": "",
        "execution_error": "",
        "execution_success": False,
        "retryable_error": False
    }

    config = {
        "configurable": {
            "thread_id": str(uuid4())
        },
        "recursion_limit": 30
    }

    # Agent'ı başlat
    # result = graph.invoke(initial_state, config=config) // Eskisi

    result = run_graph_stream(initial_state, config)

    # Her interrupt için kullanıcıdan onay al
    while result.get("__interrupt__"):

        request = result["__interrupt__"][0].value

        print("\n===== SQL ONAY İSTEĞİ =====")
        print(request["message"])
        print("\nSQL:")
        print(request["sql"])

        approval = input(
            "\nSorguyu onaylıyor musunuz? (e/h): "
        )

        approved = approval.strip().lower() == "e"

        # Agent'ı aynı thread üzerinden devam ettir

        # result = graph.invoke(
        #     Command(resume=approved),
        #     config=config
        # ) // Eskisi

        result = run_graph_stream(
            Command(resume=approved),
            config
        )

        print("\n[DEBUG] SQL üretim denemesi:",
              result.get("attempts"))

        print("[DEBUG] Yeni interrupt:",
              bool(result.get("__interrupt__")))

    # Buraya yalnızca artık interrupt kalmadığında gelinir
    print("\n===== SONUÇ =====")

    if result.get("answer"):
        print(result["answer"])

    elif result.get("execution_error"):
        print("SQL çalıştırılamadı.")
        print("Hata:", result["execution_error"])

    elif result.get("validated_sql") and not result.get("approved"):
        print("Sorgu kullanıcı tarafından iptal edildi.")

    else:
        print("SQL doğrulaması başarısız.")
        print("Hata:", result.get("error"))

    print(
        "\nToplam SQL üretim denemesi:",
        result["attempts"]
    )



if __name__ == "__main__":
    main()
