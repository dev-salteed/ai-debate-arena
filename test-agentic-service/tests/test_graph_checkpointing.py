import sys
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
APP_DIR = ROOT_DIR / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from langgraph.checkpoint.memory import MemorySaver
from langgraph.store.memory import InMemoryStore
from workflow.graph import create_today_what_graph, get_graph_runtime_components


class GraphCheckpointingTests(unittest.TestCase):
    def test_graph_uses_in_memory_checkpointer_and_store(self):
        checkpointer, store = get_graph_runtime_components()
        self.assertIsInstance(checkpointer, MemorySaver)
        self.assertIsInstance(store, InMemoryStore)

        graph1 = create_today_what_graph(enable_rag=True)
        graph2 = create_today_what_graph(enable_rag=True)
        self.assertIs(graph1, graph2)

        self.assertIs(getattr(graph1, "checkpointer", None), checkpointer)
        self.assertIs(getattr(graph1, "store", None), store)


if __name__ == "__main__":
    unittest.main()
