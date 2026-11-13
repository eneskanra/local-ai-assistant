"""
Konuşma yönetimi (6.8)

agent_memory DB'sindeki LangGraph checkpoint'lerinden konuşma
listesini çıkarır ve konuşma silme işlemini sağlar.

Grafın kendi checkpointer'ını (PostgresSaver) kullanır; ayrı
bağlantı açmaz.
"""

from dataclasses import dataclass

from psycopg.rows import dict_row


# Listede gösterilecek en fazla konuşma sayısı
MAX_CONVERSATIONS = 50

# Başlık için ilk sorudan alınan karakter sayısı
TITLE_MAX_LENGTH = 60

# Ana graf checkpoint'leri boş namespace ile kaydedilir
ROOT_NAMESPACE = ""

LIST_THREADS_SQL = """
    SELECT thread_id,
           MAX(checkpoint ->> 'ts') AS updated_at
    FROM checkpoints
    WHERE checkpoint_ns = %s
    GROUP BY thread_id
    ORDER BY updated_at DESC
    LIMIT %s
"""


@dataclass
class Conversation:
    thread_id: str
    title: str
    updated_at: str
    message_count: int
    awaiting_approval: bool


def make_title(question: str) -> str:
    """Soruyu tek satırlık kısa bir başlığa çevirir."""
    title = " ".join(question.split())

    if not title:
        return "(boş konuşma)"

    if len(title) > TITLE_MAX_LENGTH:
        title = title[:TITLE_MAX_LENGTH - 1] + "…"

    return title


def _thread_config(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id}}


def list_conversations(
    graph,
    limit: int = MAX_CONVERSATIONS
) -> list[Conversation]:
    """Konuşmaları son güncellenen en üstte olacak şekilde döndürür."""
    pool = graph.checkpointer.conn

    with pool.connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(LIST_THREADS_SQL, (ROOT_NAMESPACE, limit))
            rows = cur.fetchall()

    conversations = []

    for row in rows:
        snapshot = graph.get_state(_thread_config(row["thread_id"]))
        values = snapshot.values or {}
        history = values.get("history", [])

        # Başlık: ilk başarılı soru, yoksa son sorulan soru
        first_question = (
            history[0]["question"] if history
            else values.get("question", "")
        )

        conversations.append(Conversation(
            thread_id=row["thread_id"],
            title=make_title(first_question),
            updated_at=row["updated_at"] or "",
            message_count=len(history),
            awaiting_approval=bool(snapshot.interrupts),
        ))

    return conversations


def delete_conversation(graph, thread_id: str) -> None:
    """Konuşmanın tüm checkpoint'lerini kalıcı olarak siler."""
    graph.checkpointer.delete_thread(thread_id)
