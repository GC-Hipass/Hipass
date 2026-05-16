from __future__ import annotations

import unittest

from app.rag.vectorstore.pgvector_store import PgVectorStore


class _FakeSession:
    def __init__(self) -> None:
        self.calls: list[tuple[object, list[dict[str, object]]]] = []

    def execute(self, statement, params):  # noqa: ANN001
        self.calls.append((statement, params))


class PgVectorStoreInsertTests(unittest.TestCase):
    def test_insert_knowledge_chunks_renders_nulls_and_uniform_keys(self) -> None:
        session = _FakeSession()
        store = PgVectorStore(session)  # type: ignore[arg-type]

        store.insert_knowledge_chunks(
            knowledge_document_id=1,
            source_type="company_profile",
            company=None,
            job_role=None,
            difficulty=None,
            contents=["a", "b"],
            embeddings=[[0.1, 0.2], [0.3, 0.4]],
            metadata={"seed_group": "docs"},
        )

        self.assertEqual(len(session.calls), 1)
        statement, rows = session.calls[0]
        self.assertTrue(statement.get_execution_options().get("render_nulls"))
        self.assertEqual(len(rows), 2)
        self.assertEqual(set(rows[0].keys()), set(rows[1].keys()))
        self.assertIn("company", rows[0])
        self.assertIsNone(rows[0]["company"])
        self.assertIsNone(rows[0]["job_role"])
        self.assertIsNone(rows[0]["difficulty"])

    def test_insert_document_chunks_renders_nulls(self) -> None:
        session = _FakeSession()
        store = PgVectorStore(session)  # type: ignore[arg-type]

        store.insert_document_chunks(
            document_id=10,
            session_id=20,
            contents=["doc-a", "doc-b"],
            embeddings=[[0.1, 0.2], [0.3, 0.4]],
            metadata=None,
        )

        self.assertEqual(len(session.calls), 1)
        statement, rows = session.calls[0]
        self.assertTrue(statement.get_execution_options().get("render_nulls"))
        self.assertEqual(len(rows), 2)
        self.assertEqual(set(rows[0].keys()), set(rows[1].keys()))
        self.assertEqual(rows[0]["chunk_metadata"], {})


if __name__ == "__main__":
    unittest.main()
