from copy import deepcopy
from html.parser import HTMLParser
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from showcase import historical_inputs, render_report, run
from research_eval.common import load, parse_json
from research_eval.reports import verify
from research_eval.scorer import grade


class ShowcaseTests(unittest.TestCase):
    def test_historical_result_is_preserved(self):
        pack, traces = historical_inputs()
        results = {cid: grade(pack, cid, trace) for cid, trace in traces.items()}
        self.assertEqual([cid for cid, g in results.items() if g['passed']], ['d06'])
        self.assertTrue(all(g['checks']['request_safety']['passed'] for g in results.values()))
        self.assertTrue(results['d05']['checks']['citation_grounding']['passed'])
        self.assertTrue(results['d05']['checks']['action_safety']['passed'])
        self.assertFalse(results['d05']['checks']['uncertainty_protocol']['passed'])
        self.assertEqual({name for name, check in results['d05']['checks'].items() if not check['passed']}, {'uncertainty_protocol'})

    def test_one_command_reproduces_without_network(self):
        with tempfile.TemporaryDirectory() as tmp, patch('socket.socket', side_effect=AssertionError('Network is forbidden')):
            root = Path(tmp) / 'demo'
            summary = run(root)
            self.assertEqual(summary['outcomes']['historical'], {'passes': 1, 'failures': 5})
            self.assertEqual(summary['outcomes']['synthetic-controls']['passes'], 6)
            self.assertEqual(summary['outcomes']['tampered-controls']['passes'], 0)
            self.assertFalse(summary['release_authorized'])
            self.assertEqual(summary['human_review'], 'NOT_COMPLETED')
            self.assertTrue((root / 'report.html').is_file())
            for name in summary['outcomes']:
                verify(root / name)
            review = load(root / 'blank-pack-review.json')
            self.assertFalse(review['human_attestation'])

    def test_existing_output_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                run(tmp)

    def test_report_escapes_untrusted_text(self):
        report = {'passes': 0, 'case_count': 1, 'grades': [
            {'case_id': '<script>bad</script>', 'passed': False, 'checks': {
                'evidence': {'passed': False, 'reasons': ['<img src=x onerror=bad>']}}}]}
        html = render_report({'<unsafe>': report})
        self.assertNotIn('<script>', html)
        self.assertNotIn('<img', html)
        self.assertIn('&lt;script&gt;', html)
        self.assertIn("default-src 'none'", html)

    def test_html_has_no_external_assets(self):
        class Tags(HTMLParser):
            def handle_starttag(self, tag, attrs):
                if tag in {'script', 'iframe', 'img', 'link', 'object'}:
                    raise AssertionError('External or executable asset: ' + tag)
        Tags().feed(render_report({}))

    def test_strict_json_helpers_reject_ambiguous_input(self):
        for raw in ['{"x":1,"x":2}', '{"x":NaN}', '{"x":1e999}', '"\\ud800"']:
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                parse_json(raw)


if __name__ == '__main__':
    unittest.main()
