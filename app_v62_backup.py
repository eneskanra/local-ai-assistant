
import uuid

import streamlit as st

st.set_page_config(
    page_title="Local SQL Assistant",
    page_icon="🗄️",
    layout="wide"
)


@st.cache_resource
def load_graph():
    from sql_agent_v4 import graph
    return graph


graph = load_graph()


def create_initial_state(question):
    return {
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
        "retryable_error": False,
    }


def start_agent(question):
    thread_id = str(uuid.uuid4())

    config = {
        "configurable": {
            "thread_id": thread_id
        },
        "recursion_limit": 30,
    }

    st.session_state["thread_id"] = thread_id
    st.session_state["config"] = config
    st.session_state["question"] = question

    initial_state = create_initial_state(question)

    # Agent'ı kullanıcı onayına kadar çalıştır
    for event in graph.stream(
        initial_state,
        config=config,
        stream_mode="updates"
    ):
        for node_name, update in event.items():
            if node_name == "__interrupt__":
                continue

            st.write(f"Tamamlanan node: {node_name}")

    # Checkpoint'teki güncel state
    snapshot = graph.get_state(config)

    st.session_state["agent_state"] = dict(snapshot.values)

    # Interrupt bilgisini de sakla
    st.session_state["interrupts"] = snapshot.interrupts


st.title("🗄️ Local SQL Assistant")
st.caption("LangGraph + Ollama Qwen3 + PostgreSQL")

with st.sidebar:
    st.header("⚙️ Sistem")

    st.write("LLM: Qwen3 8B")
    st.write("Agent: LangGraph v4")
    st.write("Database: PostgreSQL")

    st.divider()

    if "thread_id" in st.session_state:
        st.caption("Aktif LangGraph thread:")
        st.code(st.session_state["thread_id"])

st.divider()

st.subheader("Veritabanına soru sor")

question = st.text_area(
    "Sorunuz",
    placeholder="Örn: En fazla satış yapan 3 müşteriyi getir.",
    height=100,
)

if st.button("SQL Oluştur", type="primary"):

    if not question.strip():
        st.warning("Lütfen bir soru girin.")

    else:
        with st.spinner("Qwen3 SQL oluşturuyor..."):
            try:
                start_agent(question)
            except Exception as e:
                st.error(f"Agent hatası: {e}")
                st.stop()

        st.success("SQL üretim süreci tamamlandı.")

st.divider()

if "agent_state" in st.session_state:

    state = st.session_state["agent_state"]

    st.subheader("LangGraph Durumu")

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "SQL üretim denemesi",
        state.get("attempts", 0)
    )

    col2.metric(
        "SQL doğrulama",
        "Başarılı" if state.get("validated_sql") else "Başarısız"
    )

    col3.metric(
        "Onay bekleniyor",
        "Evet" if st.session_state.get("interrupts") else "Hayır"
    )

    st.subheader("Üretilen SQL")

    sql = state.get("validated_sql") or state.get("sql")

    if sql:
        st.code(sql, language="sql")
    else:
        st.warning("SQL üretilemedi.")

    if state.get("error"):
        st.error(state["error"])

    if st.session_state.get("interrupts"):
        st.info(
            "LangGraph kullanıcı onayını bekliyor. "
            "Bir sonraki aşamada SQL onaylama "
            "ve reddetme butonlarını ekleyeceğiz."
        )
