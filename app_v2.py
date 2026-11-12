import uuid
import json
import pandas as pd
import streamlit as st
from langgraph.types import Command
from observability import monitor

st.set_page_config(
    page_title="Local SQL Assistant",
    page_icon="🗄️",
    layout="wide"
)


@st.cache_resource
def load_graph():
    from sql_agent_v5 import create_graph
    return create_graph()


graph = load_graph()


def new_conversation():
    """Yeni konuşma = yeni sabit thread_id."""
    thread_id = str(uuid.uuid4())

    st.session_state["thread_id"] = thread_id
    st.session_state["config"] = {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": 30,
    }
    st.session_state.pop("agent_state", None)
    st.session_state.pop("interrupts", None)


def refresh_state():
    """Checkpoint'teki güncel state'i session'a aktarır."""
    snapshot = graph.get_state(st.session_state["config"])

    st.session_state["agent_state"] = dict(snapshot.values)
    st.session_state["interrupts"] = snapshot.interrupts


def stream_graph(input_data):
    for event in graph.stream(
        input_data,
        config=st.session_state["config"],
        stream_mode="updates"
    ):
        for node_name in event:
            if node_name == "__interrupt__":
                continue

            st.write(f"Tamamlanan node: {node_name}")

    refresh_state()


def start_agent(question):
    # Aynı thread'e yeni tur; start_turn node'u
    # tur alanlarını sıfırlar, history korunur.
    stream_graph({"question": question})


def resume_agent(approved: bool):
    stream_graph(Command(resume=approved))


if "thread_id" not in st.session_state:
    new_conversation()

st.title("🗄️ Local SQL Assistant")
st.caption("LangGraph + Ollama Qwen3 + PostgreSQL")

with st.sidebar:
    st.header("⚙️ Sistem")

    st.write("LLM: Qwen3 8B")
    st.write("Agent: LangGraph v5")
    st.write("Database: PostgreSQL")

    st.divider()

    st.caption("Aktif konuşma (thread):")
    st.code(st.session_state["thread_id"])

    if st.button("➕ Yeni Konuşma", use_container_width=True):
        new_conversation()
        st.rerun()

st.divider()

st.subheader("Veritabanına soru sor")

question = st.text_area(
    "Sorunuz",
    placeholder="Örn: En fazla satış yapan 3 müşteriyi getir.",
    height=100,
)

# Onay bekleyen bir sorgu varken yeni soru gönderilemez
awaiting_approval = bool(st.session_state.get("interrupts"))

if awaiting_approval:
    st.info("Önce bekleyen SQL'i onaylayın veya reddedin.")

if st.button(
    "SQL Oluştur",
    type="primary",
    disabled=awaiting_approval
):

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

        approval_placeholder = st.empty()

        with approval_placeholder.container():

            st.warning(
                "SQL doğrulandı ve kullanıcı onayı bekleniyor."
            )

            col_approve, col_reject = st.columns(2)

            with col_approve:
                approve_clicked = st.button(
                    "✅ SQL'i Onayla",
                    type="primary",
                    use_container_width=True
                )

            with col_reject:
                reject_clicked = st.button(
                    "❌ SQL'i Reddet",
                    use_container_width=True
                )

        if approve_clicked or reject_clicked:

            approved = approve_clicked

            # Eski onay arayüzünü hemen kaldır
            approval_placeholder.empty()

            with st.status(
                "Agent işlemi sürdürüyor...",
                expanded=True
            ) as status:

                try:
                    resume_agent(approved)

                    status.update(
                        label="Agent işlemi tamamlandı.",
                        state="complete",
                        expanded=False
                    )

                except Exception as e:
                    status.update(
                        label="Agent hatası oluştu.",
                        state="error"
                    )
                    st.error(str(e))
                    st.stop()

            st.rerun()


    
    # SQL execution tamamlandıysa sonuçları göster
    if not st.session_state.get("interrupts"):

        st.divider()

        if state.get("execution_success"):

            st.success("SQL başarıyla çalıştırıldı.")

            rows = state.get("rows", [])

            st.subheader("📊 Sorgu Sonuçları")

            if rows:
                df = pd.DataFrame(rows)
                st.dataframe(
                    df,
                    width='stretch',
                    hide_index=True
                )
            else:
                st.info("Sorgu sonucunda kayıt bulunamadı.")

            st.subheader("🤖 Qwen3 Yanıtı")
            st.write(
                state.get("answer")
                or "AI yanıtı oluşturulamadı."
            )

        elif state.get("execution_error"):
            st.error(
                "SQL çalıştırılamadı: "
                + state["execution_error"]
            )

        elif state.get("validated_sql") and not state.get("approved"):
            st.warning(
                "SQL kullanıcı tarafından reddedildi. "
                "Sorgu çalıştırılmadı."
            )

        elif state.get("error"):
            st.error(
                "SQL doğrulama hatası: "
                + state["error"]
            )



if "thread_id" in st.session_state:

    thread_id = st.session_state["thread_id"]
    events = monitor.get_events(thread_id)


    if events:
        st.divider()
        st.header("📈 Agent Observability")

        df_events = pd.DataFrame(events)

        total_duration = df_events["duration"].sum()

        state = st.session_state.get("agent_state", {})
        attempts = state.get("attempts", 0)
        retries = max(0, attempts - 1)

        col1, col2, col3 = st.columns(3)

        col1.metric(
            "Toplam Node Süresi",
            f"{total_duration:.2f} sn"
        )

        col2.metric(
            "SQL Denemesi",
            attempts
        )

        col3.metric(
            "Retry Sayısı",
            retries
        )

        st.subheader("Node Çalışma Süreleri")

        duration_by_node = (
            df_events.groupby("node")["duration"]
            .sum()
            .sort_values(ascending=False)
        )

        st.bar_chart(duration_by_node)

        st.subheader("Execution Timeline")

        for event in events:
            status = event["status"]
            node = event["node"]
            duration = event["duration"]

            
            if status == "success":
                st.write(
                    f"✅ {node} — {duration:.3f} sn"
                )

            elif status == "interrupted":
                st.write(
                    f"⏸️ {node} — kullanıcı onayı bekleniyor"
                )

            else:
                st.write(
                    f"❌ {node} — {duration:.3f} sn"
                )


        with st.expander("Detaylı Trace Verileri"):
            st.dataframe(
                df_events,
                width='stretch',
                hide_index=True
            )


st.divider()
st.subheader("💬 Conversation Memory")

# Geçmiş artık checkpoint'teki state'ten gelir (kalıcı)
history = st.session_state.get(
    "agent_state", {}
).get("history", [])

if not history:
    st.info("Henüz tamamlanmış bir sorgu bulunmuyor.")
else:
    st.caption(
        f"Toplam {len(history)} başarılı etkileşim"
    )

    for i, item in enumerate(history, start=1):
        with st.expander(
            f"{i}. {item['question']}",
            expanded=False
        ):
            st.markdown("**Üretilen SQL**")
            st.code(item["sql"], language="sql")

            st.markdown("**AI Yanıtı**")
            st.write(item["answer"])




