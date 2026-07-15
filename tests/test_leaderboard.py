import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "api"))

from leaderboard import (
    ClanStanding,
    get_clan,
    get_fight_setup_schema,
    get_leaderboard,
    get_past_battles,
    get_public_availability,
    get_public_fight_summary,
    health,
    ranked_standings,
    search_clans,
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
        self.assertIn("clan_type", payload["standings"][0])

    def test_score_ordering(self):
        rows = ranked_standings([
            ClanStanding("a", "A", True, "Pure Clan", "50-88", "Wild", "A", 1, 1, 0, 0, 0, 0, 10, 8),
            ClanStanding("b", "B", True, "Main Clan", "100-126", "Wild", "B", 1, 0, 0, 0, 800, 0, 10, 8),
        ])
        self.assertEqual(rows[0]["clan_id"], "b")
        self.assertEqual(rows[0]["rank"], 1)

    def test_clan_lookup_normalizes_spaces_and_includes_members(self):
        clan = get_clan("Example Rivals")
        self.assertIsNotNone(clan)
        self.assertEqual(clan["clan_id"], "example-rivals")
        self.assertEqual(clan["clan_type"], "Pure Clan")
        self.assertGreater(len(clan["members"]), 0)
        self.assertEqual(clan["wiseOldMan"]["source"], "Wise Old Man Groups API")

    def test_clan_search_can_find_pure_clans(self):
        payload = search_clans("pure")
        self.assertGreaterEqual(len(payload["results"]), 1)
        self.assertEqual(payload["results"][0]["clan_type"], "Pure Clan")

    def test_wom_import_contract_is_privacy_limited(self):
        plan = wom_import_plan(123)
        self.assertEqual(plan["source"], "Wise Old Man Groups API")
        self.assertIn("member list", plan["allowedData"])
        self.assertIn("upcoming war world", plan["excludedData"])

    def test_public_availability_requires_fight_setup_terms(self):
        payload = get_public_availability()
        row = payload["availability"][0]
        self.assertIn("exact accepted world", payload["privacy"])
        self.assertIn("publicWorldPolicy", row)
        self.assertIn("durationMinutes", row)
        self.assertIn("combatLevelRange", row)
        self.assertIn("location", " ".join(row["requiredAgreementFields"]))
        self.assertIn("world", " ".join(row["requiredAgreementFields"]))
        self.assertNotIn("rallyNotes", row)

    def test_past_battles_and_public_summary_are_completed_only(self):
        battles = get_past_battles()
        self.assertGreaterEqual(len(battles["battles"]), 1)
        summary = get_public_fight_summary("fight-static-example")
        self.assertIsNotNone(summary)
        self.assertEqual(summary["status"], "published")
        self.assertIn("completed sanitized", summary["privacy"])
        self.assertIn("combatLevelRange", summary)
        self.assertIn("durationMinutes", summary)
        self.assertNotIn("nextWorld", summary)
        self.assertIsNone(get_public_fight_summary("missing"))

    def test_fight_setup_schema_names_required_fields(self):
        payload = get_fight_setup_schema()
        names = {row["name"] for row in payload["requiredFields"]}
        self.assertTrue({"location", "world", "scheduledTime", "combatLevelRange", "durationMinutes"}.issubset(names))


if __name__ == "__main__":
    unittest.main()
