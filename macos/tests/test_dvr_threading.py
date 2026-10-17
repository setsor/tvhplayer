"""Static safety checks guarding against regressions in DVR HTTP threading."""

import ast
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CLIENT = PROJECT_ROOT / "tvhplayer" / "tvhplayer.py"
WORKER = PROJECT_ROOT / "tvhplayer" / "recording_poll.py"


def function_text(source, cls, method):
    module = ast.parse(source)
    classes = [node for node in module.body if isinstance(node, ast.ClassDef)
               and node.name == cls]
    if len(classes) != 1:
        raise AssertionError(f"Missing class {cls}")
    methods = [node for node in classes[0].body
               if isinstance(node, ast.FunctionDef) and node.name == method]
    if len(methods) != 1:
        raise AssertionError(f"Missing method {cls}.{method}")
    return ast.get_source_segment(source, methods[0])


class DVRThreadSafetyTests(unittest.TestCase):
    def test_dialog_never_makes_http_requests(self):
        source = CLIENT.read_text(encoding="utf-8")
        tree = ast.parse(source)
        dialog = next(node for node in tree.body
                      if isinstance(node, ast.ClassDef)
                      and node.name == "DVRStatusDialog")
        body = ast.get_source_segment(source, dialog)
        self.assertNotIn("requests.get(", body)
        self.assertNotIn("requests.post(", body)
        self.assertNotIn("update_timer.start(5000)", body)

    def test_single_serialized_pool(self):
        source = CLIENT.read_text(encoding="utf-8")
        self.assertIn("self._dvr_pool.setMaxThreadCount(1)", source)
        self.assertIn("self._dvr_pool.start(self._recordings_worker)", source)
        self.assertIn("self._dvr_pool.start(self._dvr_stop_worker)", source)
        self.assertNotIn("QThreadPool.globalInstance().start(self._recordings_worker)", source)

    def test_stop_is_only_implemented_by_one_background_worker(self):
        source = WORKER.read_text(encoding="utf-8")
        self.assertEqual(source.count('/api/dvr/entry/stop'), 1)
        method = function_text(source, "RecordingStopWorker", "run")
        self.assertIn("data={", method)
        self.assertIn('"uuid": self.uuid', method)
        self.assertNotIn("for recording in", method)

    def test_timeouts_disable_auto_retries(self):
        source = CLIENT.read_text(encoding="utf-8")
        handler = function_text(source, "TVHeadendClient", "_on_stop_result")
        self.assertIn('outcome == "unknown"', handler)
        self.assertIn("self._dvr_read_suspended = True", handler)
        self.assertIn("self._uncertain_stop_uuids.add(uuid)", handler)
        self.assertNotIn("self._start_pending_stop()", handler)


if __name__ == "__main__":
    unittest.main()
