import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "api"))

from leaderboard import (
    fetch_wom_groups,
    get_clan,
    get_fight_setup_schema,
    get_leaderboard,
    get_past_battles,
    get_public_availability,
    get_public_fight_summary,
    get_theme_assets,
    health,
    infer_group_classification,
    public_group,
    search_clans,
    wom_import_plan,
)

GROUPS = [
    {
        "id": 1,
        "name": "Pure Fury",
        "clanChat": "Pure Fury",
        "description": "Pure pvp clan for wilderness fights",
        "homeworld": 308,
        "verified": True,
        "patron": False,
        "visible": True,
        "profileImage": "https://img.wiseoldman.net/example.webp",
        "bannerImage": "https://img.wiseoldman.net/banner.webp",
        "score": 100,
        "updatedAt": "2026-07-15T00:00:00.000Z",
        "memberCount": 3,
    }
]
GROUP_DETAIL = {
    **GROUPS[0],
    "memberships": [
        {"role": "owner", "player": {"displayName": "A Pure", "type": "regular", "build": "pure", "status": "active"}},
        {"role": "member", "player": {"displayName": "B Pure", "type": "regular", "build": "pure", "status": "active"}},
        {"role": "member", "player": {"displayName": "C Main", "type": "regular", "build": "main", "status": "active"}},
    ],
}


def fake_cached_json(url, ttl=300):
    if "/groups/1" in url:
        return GROUP_DETAIL
    if "/groups" in url:
        return GROUPS
    if "oldschool.runescape.wiki" in url:
        return {"query": {"pages": {"1": {"thumbnail": {"source": "https://oldschool.runescape.wiki/images/thumb/Wilderness.png/900px-Wilderness.png"}}}}}
    raise AssertionError(url)


class LeaderboardTests(unittest.TestCase):
    def test_health(self):
        payload = health()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["service"], "clan-war-board-service")
        self.assertIn("wom-live", payload["storage"])

    @patch("leaderboard.cached_json", side_effect=fake_cached_json)
    def test_leaderboard_uses_real_wom_shape(self, _):
        payload = get_leaderboard()
        self.assertEqual(payload["source"], "Wise Old Man Groups API")
        self.assertIn("real Wise Old Man", payload["privacy"])
        self.assertEqual(payload["standings"][0]["clan_name"], "Pure Fury")
        self.assertEqual(payload["standings"][0]["dataSource"], "Wise Old Man Groups API")

    def test_group_classification_uses_member_builds(self):
        classification = infer_group_classification(GROUP_DETAIL, GROUP_DETAIL["memberships"])
        self.assertEqual(classification["label"], "Pure Clan")
        self.assertEqual(classification["source"], "Wise Old Man member builds")

    @patch("leaderboard.cached_json", side_effect=fake_cached_json)
    def test_clan_lookup_includes_real_members_and_wom_status(self, _):
        clan = get_clan("1")
        self.assertIsNotNone(clan)
        self.assertEqual(clan["clan_id"], "1")
        self.assertEqual(clan["clan_type"], "Pure Clan")
        self.assertEqual(clan["wiseOldMan"]["status"], "linked_live")
        self.assertEqual(len(clan["members"]), 3)
        self.assertEqual(clan["roleCounts"]["owner"], 1)

    @patch("leaderboard.cached_json", side_effect=fake_cached_json)
    def test_clan_search(self, _):
        payload = search_clans("pure")
        self.assertEqual(len(payload["results"]), 1)
        self.assertEqual(payload["results"][0]["clan_name"], "Pure Fury")

    def test_wom_import_contract_is_privacy_limited(self):
        plan = wom_import_plan(123)
        self.assertEqual(plan["source"], "Wise Old Man Groups API")
        self.assertIn("member list", plan["allowedData"])
        self.assertIn("upcoming war world", plan["excludedData"])

    def test_public_availability_is_empty_until_real_plugin_posts(self):
        payload = get_public_availability()
        self.assertEqual(payload["availability"], [])
        self.assertIn("No real scheduled fights", payload["emptyState"])
        fields = " ".join(row["name"] for row in payload["fightSetupFields"])
        self.assertIn("world", fields)
        self.assertIn("durationMinutes", fields)

    def test_past_battles_are_empty_until_real_telemetry(self):
        battles = get_past_battles()
        self.assertEqual(battles["battles"], [])
        self.assertIn("No real completed", battles["emptyState"])
        self.assertIsNone(get_public_fight_summary("missing"))

    def test_fight_setup_schema_names_required_fields(self):
        payload = get_fight_setup_schema()
        names = {row["name"] for row in payload["requiredFields"]}
        self.assertTrue({"location", "world", "scheduledTime", "combatLevelRange", "durationMinutes"}.issubset(names))

    @patch("leaderboard.cached_json", side_effect=fake_cached_json)
    def test_theme_assets_use_wiki_api(self, _):
        assets = get_theme_assets()
        self.assertEqual(assets["source"], "OSRS Wiki MediaWiki API")
        self.assertGreaterEqual(len(assets["images"]), 1)
        self.assertIn("parchment", assets["theme"]["colors"])


if __name__ == "__main__":
    unittest.main()
