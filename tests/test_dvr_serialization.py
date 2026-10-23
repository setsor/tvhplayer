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
        self.assertIn("self.stop_server_entry(task[\"entry\"])", method_source)
        self.assertIn('gate.submit(host.get_backend(), "stop"', method("TasksPanel", "stop_server_entry"))
        self.assertNotIn(".stop_dvr_entry(", method_source)
        self.assertNotIn(".cancel_dvr_entry(", method_source)

    def test_polling_is_async(self):
        refresh = method("TasksPanel", "refresh")
        self.assertIn('gate.submit(host.get_backend(), "read"', refresh)
        self.assertNotIn(".list_dvr_entries(", refresh)

    def test_main_stop_only_on_playing_channel(self):
        stop = method("TVHeadendClient", "stop_recording")
        self.assertIn("self._playing_channel()", stop)
        self.assertIn("entry.matches_channel(channel)", stop)
        self.assertIn("len(matching) != 1", stop)
        self.assertIn("pane.stop_server_entry(matching[0])", stop)
        self.assertNotIn("pane.selected_task()", stop)
        self.assertNotIn("gate.submit(", stop)

    def test_start_also_uses_playing_channel(self):
        start = method("TVHeadendClient", "start_recording")
        self.assertIn("channel = self._playing_channel()", start)
        self.assertNotIn("channel = self.selected_channel()", start)

    def test_channel_status_combines_playback_and_rec(self):
        row = method("TVHeadendClient", "_set_channel_row_playing")
        self.assertIn('"Playing / " + rec_label', row)
        self.assertIn('"REC " + ",".join(', row)
        self.assertIn("job.matches_channel(channel)", row)
        self.assertIn("enumerate(active, start=1)", row)
        self.assertIn("job.start or 0", row)
        refresh = method("TasksPanel", "_server_read_done")
        self.assertIn("host._mark_playing_channel()", refresh)

    def test_unknown_stop_tracks_exact_uuid(self):
        completed = method("_DvrGate", "_completed")
        self.assertIn("self.uncertain_uuid =", completed)
        submit = method("_DvrGate", "submit")
        self.assertIn('getattr(entry, "uuid", None)', submit)

    def test_fresh_snapshot_resolves_only_finished_uuid(self):
        completed = method("TasksPanel", "_server_read_done")
        self.assertIn('item.uuid == gate.uncertain_uuid', completed)
        self.assertIn('item.category() == "recording"', completed)
        self.assertIn("if not still_recording:", completed)
        self.assertIn("gate.uncertain = False", completed)
        self.assertNotIn('stop_dvr_entry(', completed)

    def test_epg_scheduled_rec_button(self):
        render = method("EPGDialog", "refresh_recording_buttons")
        self.assertIn('job.category() not in ("upcoming", "recording")', render)
        self.assertIn("job.matches_channel(self.channel)", render)
        self.assertIn('button.setText("Scheduled")', render)
        self.assertIn("button.setEnabled(False)", render)
        self.assertIn('button.setText("Rec")', render)
        self.assertIn("button.setEnabled(True)", render)
        self.assertNotIn("list_dvr_entries(", render)
        refresh = method("TasksPanel", "_server_read_done")
        self.assertIn("dialog.refresh_recording_buttons()", refresh)

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
