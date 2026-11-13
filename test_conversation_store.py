"""
conversation_store testleri (6.8).

Canlı agent_memory DB'sini kullanır (docker container açık olmalı).
LLM/SQL çağrıları mock'lanır; test konuşmaları sonunda silinir.

Çalıştırma: .venv/bin/python -m unittest test_conversation_store
"""

import unittest
from unittest.mock import patch

from langgraph.types import Command

import sql_agent_v5 as agent
from conversation_store import (
    TITLE_MAX_LENGTH,
    make_title,
    list_conversations,
    delete_conversation,
)


class MakeTitleTest(unittest.TestCase):

    def test_whitespace_collapsed(self):
        self.assertEqual(make_title("  en çok\n satan  ürün "), "en çok satan ürün")

    def test_long_title_truncated(self):
        title = make_title("x" * 200)
        self.assertEqual(len(title), TITLE_MAX_LENGTH)
        self.assertTrue(title.endswith("…"))

    def test_empty(self):
        self.assertEqual(make_title("   "), "(boş konuşma)")


class ConversationStoreLiveTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.graph = agent.create_graph()

    def setUp(self):
        patches = [
            patch.object(agent, "generate_sql", lambda q: "SELECT 1"),
            patch.object(agent, "validate_sql", lambda s: s),
            patch.object(agent, "execute_sql", lambda s: [{"x": 1}]),
            patch.object(agent, "generate_answer", lambda q, s, r: "ok"),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

        self.thread_ids = []

    def tearDown(self):
        for thread_id in self.thread_ids:
            delete_conversation(self.graph, thread_id)

    def new_thread(self):
        config = agent.new_thread_config()
        self.thread_ids.append(config["configurable"]["thread_id"])
        return config

    def ask(self, config, question, approve=True):
        agent.run_turn(self.graph, {"question": question}, config)
        if approve is not None:
            agent.run_turn(self.graph, Command(resume=approve), config)

    def find(self, thread_id):
        for conv in list_conversations(self.graph):
            if conv.thread_id == thread_id:
                return conv
        return None

    def test_lists_with_title_count_and_order(self):
        older = self.new_thread()
        self.ask(older, "eski konuşma")

        newer = self.new_thread()
        self.ask(newer, "yeni konuşma ilk soru")
        self.ask(newer, "yeni konuşma ikinci soru")

        ids = [c.thread_id for c in list_conversations(self.graph)]
        newer_id = newer["configurable"]["thread_id"]
        older_id = older["configurable"]["thread_id"]

        # Son güncellenen önce gelir
        self.assertLess(ids.index(newer_id), ids.index(older_id))

        conv = self.find(newer_id)
        self.assertEqual(conv.title, "yeni konuşma ilk soru")
        self.assertEqual(conv.message_count, 2)
        self.assertFalse(conv.awaiting_approval)

    def test_awaiting_approval_flag(self):
        config = self.new_thread()
        self.ask(config, "onay bekleyen soru", approve=None)

        conv = self.find(config["configurable"]["thread_id"])
        self.assertTrue(conv.awaiting_approval)
        # Henüz başarılı tur yok; başlık güncel sorudan gelir
        self.assertEqual(conv.title, "onay bekleyen soru")
        self.assertEqual(conv.message_count, 0)

    def test_delete_removes_conversation(self):
        config = self.new_thread()
        self.ask(config, "silinecek soru")
        thread_id = config["configurable"]["thread_id"]

        delete_conversation(self.graph, thread_id)

        self.assertIsNone(self.find(thread_id))
        self.assertEqual(self.graph.get_state(config).values, {})


if __name__ == "__main__":
    unittest.main()
