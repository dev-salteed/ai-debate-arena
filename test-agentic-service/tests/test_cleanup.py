import sys
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
APP_DIR = ROOT_DIR / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


class LegacyCleanupTests(unittest.TestCase):
    def test_no_legacy_domain_tokens_remain_in_app_code(self):
        forbidden = [
            "travel" + "_theme",
            "travel" + "_days",
            "departure" + "_city",
            "recommended" + "_cities",
            "selected" + "_city",
            "flight" + "_info",
            "flight" + "_search",
            "city" + "_recommender",
        ]
        roots = [ROOT_DIR / "app"]

        for root in roots:
            for path in root.rglob("*.py"):
                if "__pycache__" in path.parts:
                    continue
                text = path.read_text(encoding="utf-8")
                for token in forbidden:
                    self.assertNotIn(token, text, msg=f"{token} found in {path}")


if __name__ == "__main__":
    unittest.main()
