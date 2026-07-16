import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "api"))

import leaderboard
from leaderboard import (
    get_challenge_system,
    get_clan,
    get_clans,
    get_competitive_leaderboard,
    get_fight_setup_schema,
    get_leaderboard,
    get_past_battles,
    get_public_availability,
    get_public_fight_summary,
    get_theme_assets,
    get_win_judging_system,
    health,
    plugin_clan_profile,
    search_clans,
    submit_telemetry_batch,
)

PLUGIN_CLAN = {
    "clan_id": "trapistan",
    "clan_name": "TRAPISTAN",
    "clan_type": "Main Clan",
    "member_count": 42,
    "wins": 3,
    "losses": 1,
    "draws": 1,
    "kills": 88,
    "deaths": 61,
    "returns": 37,
    "damageDealt": 14000,
    "damageTaken": 11000,
    "members": [{"displayName": "Private", "public": False}],
    "pastBattles": [{"fightId": "lava-1", "result": "win"}],
}


def fake_cached_json(url, ttl=300):
    if "oldschool.runescape.wiki" in url:
        return {"query": {"pages": {"1": {"thumbnail": {"source": "https://oldschool.runescape.wiki/images/thumb/Wilderness.png/900px-Wilderness.png"}}}}}
    raise AssertionError(url)


class LeaderboardTests(unittest.TestCase):
    def setUp(self):
        leaderboard.PLUGIN_CLANS.clear()

    def test_health(self):
        payload = health()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["service"], "clan-war-board-service")
        self.assertIn("plugin-registered", payload["storage"])

    def test_clans_are_empty_until_plugin_registration(self):
        payload = get_clans()
        self.assertEqual(payload["source"], "Clan War Board plugin")
        self.assertEqual(payload["clans"], [])
        self.assertIn("No clans have registered", payload["emptyState"])

    def test_plugin_clan_profile_is_fight_history_first(self):
        profile = plugin_clan_profile(PLUGIN_CLAN, rank=1)
        self.assertEqual(profile["clan_name"], "TRAPISTAN")
        self.assertEqual(profile["dataSource"], "Clan War Board plugin")
        self.assertEqual(profile["member_count"], 42)
        self.assertEqual(profile["stats"]["wins"], 3)
        self.assertEqual(profile["stats"]["kills"], 88)
        self.assertEqual(profile["rank"], 1)

    def test_registered_plugin_clan_search_and_lookup(self):
        leaderboard.PLUGIN_CLANS.append(PLUGIN_CLAN)
        payload = search_clans("trap")
        self.assertEqual(len(payload["results"]), 1)
        clan = get_clan("trapistan")
        self.assertIsNotNone(clan)
        self.assertEqual(clan["clanWarBoardData"]["status"], "plugin_registered")
        self.assertEqual(len(clan["pastBattles"]), 1)

    def test_leaderboard_uses_plugin_clans_only(self):
        leaderboard.PLUGIN_CLANS.append(PLUGIN_CLAN)
        payload = get_leaderboard()
        self.assertIn("no external", payload["privacy"])
        self.assertEqual(payload["standings"][0]["clan_name"], "TRAPISTAN")
        self.assertEqual(payload["standings"][0]["dataSource"], "Clan War Board plugin")

    @patch("leaderboard.cached_json", side_effect=fake_cached_json)
    def test_theme_assets_use_wiki_api_only_for_assets(self, _):
        assets = get_theme_assets()
        self.assertEqual(assets["source"], "OSRS Wiki MediaWiki API")
        self.assertGreaterEqual(len(assets["images"]), 1)
        self.assertIn("charcoal", assets["theme"]["colors"])

    def test_public_availability_is_empty_until_real_plugin_posts(self):
        payload = get_public_availability()
        self.assertEqual(payload["availability"], [])
        self.assertIn("RuneLite leader submissions", payload["emptyState"])
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

    def test_judging_system_defines_winner_signals(self):
        system = get_win_judging_system()
        names = {row["name"] for row in system["winnerSignals"]}
        self.assertTrue({"kills", "deaths", "returns", "durationControl", "damagePressure"}.issubset(names))
        self.assertIn("leader", " ".join(system["requiredBeforeFight"]))

    def test_challenge_system_has_direct_challenge(self):
        system = get_challenge_system()
        actions = " ".join(row["name"] for row in system["leaderActions"])
        self.assertIn("Direct challenge", actions)
        self.assertGreaterEqual(len(system["directChallengeRequiredFields"]), 5)

    def test_competitive_leaderboard_is_unrated_until_results(self):
        leaderboard.PLUGIN_CLANS.append(PLUGIN_CLAN)
        payload = get_competitive_leaderboard()
        self.assertIn("plugin completed fight", payload["source"])
        self.assertEqual(payload["standings"][0]["rating"], None)
        self.assertEqual(payload["standings"][0]["record"]["wins"], 0)

    def test_telemetry_batch_privacy_and_public_world_policy(self):
        payload = submit_telemetry_batch({"events": [
            {"type": "damage_dealt", "playerName": "Oyama", "clanName": "TRAPISTAN", "opponentName": "Enemy", "amount": 31, "world": 330, "tick": 10, "timestamp": 123, "playerPublic": False},
            {"type": "heartbeat", "playerName": "PublicGuy", "clanName": "TRAPISTAN", "world": 330, "tick": 11, "timestamp": 124, "playerPublic": True},
        ]})
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["accepted"], 2)
        self.assertTrue(payload["policy"]["worldIsPublic"])
        self.assertTrue(payload["policy"]["playerWebsiteTrackingDefaultsPrivate"])
        self.assertEqual(payload["maxBatch"], 50)


if __name__ == "__main__":
    unittest.main()
