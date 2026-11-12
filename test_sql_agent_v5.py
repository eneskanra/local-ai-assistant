"""
sql_agent_v5 için çok turlu konuşma testleri.

LLM ve veritabanı çağrıları mock'lanır; checkpointer olarak
InMemorySaver kullanılır (agent_memory DB'si gerekmez).

Çalıştırma: .venv/bin/python -m unittest test_sql_agent_v5
"""

import unittest
from unittest.mock import patch, MagicMock

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

import sql_agent_v5 as agent


class MultiTurnMemoryTest(unittest.TestCase):

    def setUp(self):
        self.prompts = []

        def fake_generate_sql(question):
            self.prompts.append(question)
            return "SELECT 1"

        patches = [
            patch.object(agent, "db", MagicMock(
                get_table_info=lambda: "schema"
            )),
            patch.object(agent, "generate_sql", fake_generate_sql),
            patch.object(agent, "validate_sql", lambda sql: sql),
            patch.object(agent, "execute_sql", lambda sql: [{"x": 1}]),
            patch.object(
                agent, "generate_answer",
                lambda q, sql, rows: f"cevap: {q}"
            ),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

        self.graph = agent.create_graph(InMemorySaver())
        self.config = agent.new_thread_config()

    def ask(self, question, approve=True):
        result = agent.run_turn(
            self.graph, {"question": question}, self.config
        )
        self.assertIn("__interrupt__", result)

        return agent.run_turn(
            self.graph, Command(resume=approve), self.config
        )

    def test_history_accumulates_on_same_thread(self):
        self.ask("ilk soru")
        result = self.ask("ikinci soru")

        self.assertEqual(
            [h["question"] for h in result["history"]],
            ["ilk soru", "ikinci soru"]
        )
        # İkinci turun SQL isteminde önceki etkileşim bağlam olarak var
        self.assertIn("ilk soru", self.prompts[-1])
        self.assertIn("GÜNCEL KULLANICI SORUSU", self.prompts[-1])

    def test_turn_fields_reset_but_history_kept(self):
        self.ask("ilk soru")
        result = self.ask("ikinci soru", approve=False)

        self.assertFalse(result["approved"])
        self.assertEqual(result["answer"], "")
        self.assertEqual(result["rows"], [])
        self.assertEqual(result["attempts"], 1)
        # Reddedilen tur geçmişe eklenmez
        self.assertEqual(len(result["history"]), 1)

    def test_first_turn_has_no_context(self):
        self.ask("tek soru")
        self.assertEqual(self.prompts[0], "tek soru")

    def test_history_window_limits_context(self):
        for i in range(agent.HISTORY_WINDOW + 2):
            self.ask(f"soru-{i}")

        last_prompt = self.prompts[-1]
        self.assertNotIn("soru-0\n", last_prompt)
        self.assertIn(f"soru-{agent.HISTORY_WINDOW}", last_prompt)


if __name__ == "__main__":
    unittest.main()
