import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.data import SeedRepository, load_seed  # noqa: E402


class SeedDataTests(unittest.TestCase):
    def setUp(self):
        self.repository = SeedRepository(load_seed())

    def test_relationships_and_four_review_states(self):
        applications = self.repository.list_applications()
        self.assertEqual(len(applications), 4)
        self.assertEqual(
            self.repository.get_application("APP-DEMO-001").enterprise.enterprise_id,
            self.repository.get_application("APP-DEMO-004").enterprise.enterprise_id,
        )

        evidenced = self.repository.get_application("APP-DEMO-001")
        item = evidenced.reports[0].items[0]
        self.assertEqual(item.evidence[0].material_id, evidenced.materials[0].material_id)
        self.assertIsNotNone(item.knowledge_ref)

        insufficient = self.repository.get_application("APP-DEMO-002")
        self.assertEqual(insufficient.reports[0].items[0].match_status, "insufficient_evidence")

        failed = self.repository.get_application("APP-DEMO-003")
        self.assertEqual(failed.reports[0].analysis_status, "failed")
        self.assertTrue(failed.reports[0].error_message)

        no_report = self.repository.get_application("APP-DEMO-004")
        self.assertEqual(no_report.reports, [])
        self.assertIsNone(self.repository.get_application("APP-UNKNOWN"))

    def test_rejects_evidence_from_another_application(self):
        data = load_seed()
        data.reports[0].items[0].evidence[0].material_id = "MAT-DEMO-003"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid-seed.json"
            path.write_text(data.model_dump_json(), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Invalid material reference"):
                load_seed(path)


if __name__ == "__main__":
    unittest.main()
