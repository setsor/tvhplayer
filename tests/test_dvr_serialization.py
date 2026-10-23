"""Static regression safeguards for PyQt6 DVR stop isolation."""
import ast
import unittest
from pathlib import Path

SOURCE = (Path(__file__).resolve().parents[1] / "tvhplayer" / "tvhplayer.py").read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)

def method(klass, name):
    node = next(n for n in TREE.body if isinstance(n, ast.ClassDef) and n.name == klass)
    fn = next(n for n in node.body if isinstance(n, ast.FunctionDef) and n.name == name)
    return ast.get_source_segment(SOURCE, fn)

class DvrIsolationTests(unittest.TestCase):
    def test_single_worker_pool(self):
        constructor = method("_DvrGate", "__init__")
        self.assertIn("self.pool.setMaxThreadCount(1)", constructor)

    def test_worker_performs_backend_io(self):
        worker = method("_DvrJob", "run")
        self.assertIn("self.backend.list_dvr_entries()", worker)
        self.assertIn("self.backend.stop_dvr_entry(self.entry)", worker)

    def test_unknown_mutation_blocks_new_mutations(self):
        self.assertIn('self.uncertain and operation != "read"', method("_DvrGate", "submit"))
        self.assertIn('self.uncertain = True', method("_DvrGate", "_completed"))

    def test_tasks_stop_uses_worker(self):
        method_source = method("TasksPanel", "run_action")
        self.assertIn("gate.submit(", method_source)
        self.assertNotIn(".stop_dvr_entry(", method_source)
        self.assertNotIn(".cancel_dvr_entry(", method_source)

    def test_polling_is_async(self):
        refresh = method("TasksPanel", "refresh")
        self.assertIn('gate.submit(host.get_backend(), "read"', refresh)
        self.assertNotIn(".list_dvr_entries(", refresh)

    def test_main_stop_only_one_entry(self):
        stop = method("TVHeadendClient", "stop_recording")
        self.assertIn("pane.selected_task()", stop)
        self.assertIn("selected_uuid", stop)
        self.assertIn("len(running) == 1", stop)
        self.assertIn("Select one active recording in Tasks", stop)
        self.assertIn('gate.submit(self.get_backend(), "stop"', stop)
        self.assertNotIn(".stop_dvr_entry(", stop)

    def test_dialog_stop_is_serialized(self):
        stop = method("DVRStatusDialog", "stop_selected")
        self.assertIn('gate.submit(self.backend, "stop"', stop)
        self.assertNotIn(".stop_dvr_entry(", stop)

    def test_dialog_reads_cached_snapshot(self):
        status = method("DVRStatusDialog", "update_status")
        self.assertIn("pane._server_entries", status)
        self.assertNotIn(".list_dvr_entries(", status)

if __name__ == "__main__":
    unittest.main()
