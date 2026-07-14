import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "api"))

from leaderboard import (
    ClanStanding,
    get_clan,
    get_leaderboard,
    get_public_availability,
    get_public_fight_summary,
    health,
    ranked_standings,
    wom_import_plan,
)


class LeaderboardTests(unittest.TestCase):
    def test_health(self):
        payload = health()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["service"], "clan-war-board-service")

    def test_leaderboard_contains_no_upcoming_intel(self):
        payload = get_leaderboard()
        self.assertEqual(payload["source"], "static-mvp")
        self.assertIn("no upcoming world/time/hotspot", payload["privacy"])
        self.assertGreaterEqual(len(payload["standings"]), 1)
        self.assertNotIn("nextWorld", payload["standings"][0])
        self.assertNotIn("nextHotspot", payload["standings"][0])

    def test_score_ordering(self):
        rows = ranked_standings([
            ClanStanding("a", "A", True, 1, 1, 0, 0, 0, 0),
            ClanStanding("b", "B", True, 1, 0, 0, 0, 800, 0),
        ])
        self.assertEqual(rows[0]["clan_id"], "b")
        self.assertEqual(rows[0]["rank"], 1)

    def test_clan_lookup_normalizes_spaces(self):
        clan = get_clan("Example Rivals")
        self.assertIsNotNone(clan)
        self.assertEqual(clan["clan_id"], "example-rivals")

    def test_wom_import_contract_is_privacy_limited(self):
        plan = wom_import_plan(123)
        self.assertEqual(plan["source"], "Wise Old Man Groups API")
        self.assertIn("member list", plan["allowedData"])
        self.assertIn("upcoming war world", plan["excludedData"])

    def test_public_availability_hides_exact_intel(self):
        payload = get_public_availability()
        row = payload["availability"][0]
        self.assertIn("exact world/location/rally notes hidden", payload["privacy"])
        self.assertNotIn("world", row)
        self.assertNotIn("hotspot", row)
        self.assertNotIn("rallyNotes", row)

    def test_public_fight_summary_is_completed_only(self):
        summary = get_public_fight_summary("fight-static-example")
        self.assertIsNotNone(summary)
        self.assertEqual(summary["status"], "published")
        self.assertIn("completed sanitized", summary["privacy"])
        self.assertNotIn("nextWorld", summary)
        self.assertIsNone(get_public_fight_summary("missing"))


if __name__ == "__main__":
    unittest.main()
