import sys
import time
import unittest
from datetime import datetime, timezone
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
    register_plugin,
    normalize_fight_terms,
    terms_hash,
    apply_challenge_action,
    authorize_write,
    create_availability,
    create_challenge,
    get_challenges,
    get_my_player_metrics,
    update_challenge,
    rotate_installation_session,
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
        leaderboard.INSTALL_SESSIONS.clear()
        leaderboard.AVAILABILITY.clear()
        leaderboard.CHALLENGES.clear()
        leaderboard.TELEMETRY_EVENTS.clear()

    def test_health(self):
        payload = health()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["service"], "clan-war-board-service")
        self.assertEqual(payload["storage"], "memory-local-only")
        self.assertFalse(payload["productionReadyStorage"])

    def test_plugin_registration_creates_real_clan_and_respects_private_player_default(self):
        result = register_plugin({
            "installId": "11111111-1111-4111-8111-111111111111",
            "playerName": "Oyama",
            "clanName": "TRAPISTAN",
            "clanRank": 126,
            "pluginVersion": "1.0.0",
            "publicStats": False,
        })
        self.assertTrue(result["ok"])
        self.assertEqual(result["clanId"], "trapistan")
        clan = get_clan("trapistan")
        self.assertNotIn("Oyama", str(clan.get("members")))
        self.assertNotIn("installHash", str(clan))
        self.assertEqual(get_clans()["clans"][0]["member_count"], 1)

    def test_plugin_registration_rejects_invalid_install_or_missing_clan(self):
        self.assertFalse(register_plugin({"installId": "bad", "clanName": "TRAPISTAN"})["ok"])
        self.assertFalse(register_plugin({"installId": "11111111-1111-4111-8111-111111111111", "clanName": ""})["ok"])

    def test_plugin_registration_is_idempotent_per_installation(self):
        payload = {"installId": "11111111-1111-4111-8111-111111111111", "playerName": "Oyama", "clanName": "TRAPISTAN", "clanRank": 126, "pluginVersion": "1.0.0", "publicStats": True}
        register_plugin(payload)
        register_plugin(payload)
        self.assertEqual(get_clans()["clans"][0]["member_count"], 1)

    def test_registration_issues_hashed_scoped_installation_session(self):
        result = register_plugin({"installId": "11111111-1111-4111-8111-111111111111", "playerName": "Oyama", "clanName": "TRAPISTAN", "clanRank": 100, "pluginVersion": "1.0.0"})
        self.assertTrue(result["ok"])
        self.assertGreaterEqual(len(result["sessionToken"]), 40)
        self.assertIn("leader:write", result["capabilities"])
        self.assertNotIn(result["sessionToken"], str(leaderboard.INSTALL_SESSIONS))

    def test_member_session_cannot_use_leader_write_capability(self):
        result = register_plugin({"installId": "22222222-2222-4222-8222-222222222222", "playerName": "Member", "clanName": "TRAPISTAN", "clanRank": 1})
        denied = create_availability({"startsAt": "2026-07-20T20:00:00Z", "durationMinutes": 30}, self.auth_headers(result["sessionToken"]))
        self.assertFalse(denied["ok"])
        self.assertEqual(denied["error"], "capability_denied")

    def test_authenticated_write_rejects_replayed_nonce(self):
        result = register_plugin({"installId": "33333333-3333-4333-8333-333333333333", "playerName": "Leader", "clanName": "TRAPISTAN", "clanRank": 100})
        headers = self.auth_headers(result["sessionToken"], "44444444-4444-4444-8444-444444444444")
        self.assertTrue(authorize_write(headers, "leader:write")["ok"])
        replay = authorize_write(headers, "leader:write")
        self.assertFalse(replay["ok"])
        self.assertEqual(replay["error"], "replayed_request")

    def test_rotation_revokes_old_session_and_returns_new_token(self):
        result = register_plugin({"installId": "55555555-5555-4555-8555-555555555555", "playerName": "Leader", "clanName": "TRAPISTAN", "clanRank": 100})
        rotated = rotate_installation_session(self.auth_headers(result["sessionToken"]))
        self.assertTrue(rotated["ok"])
        self.assertNotEqual(rotated["sessionToken"], result["sessionToken"])
        self.assertEqual(authorize_write(self.auth_headers(result["sessionToken"]), "leader:write")["error"], "invalid_session")

    def test_leader_can_create_availability_and_challenge_with_canonical_terms(self):
        result = register_plugin({"installId": "66666666-6666-4666-8666-666666666666", "playerName": "Leader", "clanName": "TRAPISTAN", "clanRank": 100})
        availability = create_availability({"startsAt": "2026-07-20T20:00:00Z", "durationMinutes": 30, "combatMin": 70, "combatMax": 126, "notes": "GMT"}, self.auth_headers(result["sessionToken"]))
        self.assertTrue(availability["ok"])
        public = get_public_availability()["availability"]
        self.assertEqual(len(public), 1)
        self.assertEqual(public[0]["creatorClanId"], "trapistan")
        self.assertNotIn("session", str(public).lower())
        challenge = create_challenge({"opponentClanId": "Rivals", "terms": {"location": "Chaos Temple", "world": 303, "startsAt": "2026-07-20T20:00:00Z", "combatMin": 70, "combatMax": 126, "durationMinutes": 30, "rules": "No overheads"}}, self.auth_headers(result["sessionToken"]))
        self.assertTrue(challenge["ok"])
        self.assertEqual(challenge["challenge"]["creatorClanId"], "trapistan")
        self.assertEqual(challenge["challenge"]["acceptedBy"], ["trapistan"])
        self.assertEqual(len(challenge["challenge"]["termsHash"]), 64)

    def test_only_challenge_participants_can_accept_terms(self):
        creator = register_plugin({"installId": "77777777-7777-4777-8777-777777777777", "playerName": "Alpha", "clanName": "Alpha", "clanRank": 100})
        created = create_challenge({"opponentClanId": "Bravo", "terms": {"location": "Chaos Temple", "world": 303, "startsAt": "2026-07-20T20:00:00Z", "combatMin": 70, "combatMax": 126, "durationMinutes": 30, "rules": ""}}, self.auth_headers(creator["sessionToken"]))
        outsider = register_plugin({"installId": "88888888-8888-4888-8888-888888888888", "playerName": "Other", "clanName": "Outsider", "clanRank": 100})
        denied = update_challenge(created["challenge"]["id"], {"action": "accept"}, self.auth_headers(outsider["sessionToken"]))
        self.assertFalse(denied["ok"])
        self.assertEqual(denied["error"], "challenge_forbidden")
        bravo = register_plugin({"installId": "99999999-9999-4999-8999-999999999999", "playerName": "Bravo", "clanName": "Bravo", "clanRank": 100})
        accepted = update_challenge(created["challenge"]["id"], {"action": "accept"}, self.auth_headers(bravo["sessionToken"]))
        self.assertTrue(accepted["ok"])
        self.assertEqual(accepted["challenge"]["status"], "confirmed")
        inbox = get_challenges(self.auth_headers(bravo["sessionToken"]))
        self.assertTrue(inbox["ok"])
        self.assertEqual([created["challenge"]["id"]], [item["id"] for item in inbox["challenges"]])
        public = get_public_availability()
        self.assertEqual(len(public["scheduled"]), 1)
        self.assertNotIn("world", str(public["scheduled"]).lower())
        self.assertNotIn("location", str(public["scheduled"]).lower())

    def test_write_proofs_enforce_clock_skew_and_rate_limit(self):
        result = register_plugin({"installId": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa", "playerName": "Leader", "clanName": "Alpha", "clanRank": 100})
        now = int(time.time())
        stale = self.auth_headers(result["sessionToken"])
        stale["X-CWB-Timestamp"] = str(now - leaderboard.WRITE_CLOCK_SKEW_SECONDS - 1)
        self.assertEqual(authorize_write(stale, "leader:write", now)["error"], "stale_request")
        for _ in range(leaderboard.WRITE_RATE_LIMIT):
            self.assertTrue(authorize_write(self.auth_headers(result["sessionToken"]), "leader:write", now)["ok"])
        limited = authorize_write(self.auth_headers(result["sessionToken"]), "leader:write", now)
        self.assertEqual(limited["error"], "rate_limited")

    @staticmethod
    def auth_headers(token, nonce=None):
        return {"Authorization": "Bearer " + token, "X-CWB-Timestamp": str(int(time.time())), "X-CWB-Nonce": nonce or str(__import__("uuid").uuid4())}

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

    def test_match_terms_hash_and_two_party_acceptance(self):
        terms = normalize_fight_terms({
            "location": "Chaos Temple",
            "world": 303,
            "startsAt": "2026-07-20T20:00:00Z",
            "combatMin": 70,
            "combatMax": 126,
            "durationMinutes": 30,
            "rules": "No overheads",
        })
        first_hash = terms_hash(terms)
        self.assertEqual(first_hash, terms_hash(dict(reversed(list(terms.items())))))
        challenge = {"status": "proposed", "terms": terms, "termsHash": first_hash, "acceptedBy": []}
        challenge = apply_challenge_action(challenge, "accept", "alpha")
        self.assertEqual(challenge["status"], "proposed")
        challenge = apply_challenge_action(challenge, "accept", "bravo")
        self.assertEqual(challenge["status"], "confirmed")

    def test_terms_change_requires_both_clans_to_reconfirm(self):
        terms = normalize_fight_terms({"location": "Chaos Temple", "world": 303, "startsAt": "2026-07-20T20:00:00Z", "combatMin": 70, "combatMax": 126, "durationMinutes": 30, "rules": ""})
        challenge = {"status": "confirmed", "terms": terms, "termsHash": terms_hash(terms), "acceptedBy": ["alpha", "bravo"]}
        changed = dict(terms)
        changed["world"] = 304
        challenge = apply_challenge_action(challenge, "counter", "alpha", changed)
        self.assertEqual(challenge["status"], "reconfirm_required")
        self.assertEqual(challenge["acceptedBy"], ["alpha"])
        self.assertNotEqual(challenge["termsHash"], terms_hash(terms))

    def test_match_terms_reject_invalid_world_range_and_duration(self):
        with self.assertRaises(ValueError):
            normalize_fight_terms({"location": "x", "world": 1, "startsAt": "bad", "combatMin": 100, "combatMax": 70, "durationMinutes": 0})

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
        registered = register_plugin({"installId": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb", "playerName": "Oyama", "clanName": "TRAPISTAN", "clanRank": 1})
        events = {"events": [
            {"type": "damage_dealt", "playerName": "Oyama", "clanName": "TRAPISTAN", "opponentName": "Enemy", "amount": 31, "world": 330, "tick": 10, "timestamp": 123, "playerPublic": False},
            {"type": "heartbeat", "playerName": "PublicGuy", "clanName": "TRAPISTAN", "world": 330, "tick": 11, "timestamp": 124, "playerPublic": True},
        ]}
        self.assertEqual(submit_telemetry_batch(events, {})["error"], "missing_session")
        payload = submit_telemetry_batch(events, self.auth_headers(registered["sessionToken"]))
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["accepted"], 0)
        self.assertEqual(payload["rejected"], 2)
        self.assertTrue(payload["policy"]["worldIsPublic"])
        self.assertTrue(payload["policy"]["playerWebsiteTrackingDefaultsPrivate"])
        self.assertEqual(payload["maxBatch"], 50)

    def test_confirmed_war_telemetry_is_persisted_and_aggregated_for_authenticated_player(self):
        registered = register_plugin({"installId": "cccccccc-cccc-4ccc-8ccc-cccccccccccc", "playerName": "Oyama", "clanName": "TRAPISTAN", "clanRank": 1})
        now_ms = int(time.time() * 1000)
        starts_at = datetime.fromtimestamp((now_ms / 1000) - 60, timezone.utc).isoformat().replace("+00:00", "Z")
        leaderboard.CHALLENGES.append({
            "id": "fight-1", "docType": "challenge", "clanPairKey": "rivals|trapistan",
            "creatorClanId": "trapistan", "opponentClanId": "rivals", "status": "confirmed",
            "terms": {"world": 330, "startsAt": starts_at, "durationMinutes": 30},
        })
        events = {"events": [
            {"type": "damage_dealt", "clanName": "TRAPISTAN", "amount": 31, "world": 330, "tick": 10, "timestamp": now_ms},
            {"type": "friendly_fire_damage", "clanName": "TRAPISTAN", "amount": 4, "world": 330, "tick": 10, "timestamp": now_ms + 1},
            {"type": "damage_taken", "clanName": "TRAPISTAN", "amount": 18, "world": 330, "tick": 11, "timestamp": now_ms + 2},
            {"type": "kill_candidate", "clanName": "TRAPISTAN", "amount": 1, "world": 330, "tick": 12, "timestamp": now_ms + 2},
            {"type": "death", "clanName": "TRAPISTAN", "amount": 1, "world": 330, "tick": 13, "timestamp": now_ms + 3},
            {"type": "return", "clanName": "TRAPISTAN", "amount": 1, "world": 330, "tick": 14, "timestamp": now_ms + 4},
            {"type": "heartbeat", "clanName": "TRAPISTAN", "amount": 0, "world": 330, "tick": 15, "timestamp": now_ms + 5},
            {"type": "third_party_damage", "clanName": "TRAPISTAN", "amount": 7, "world": 330, "tick": 16, "timestamp": now_ms + 6},
            {"type": "damage_dealt", "clanName": "TRAPISTAN", "amount": 99, "world": 330, "tick": 17, "timestamp": now_ms - 3600000},
        ]}
        stored = submit_telemetry_batch(events, self.auth_headers(registered["sessionToken"]))
        self.assertEqual(stored["accepted"], 8)
        self.assertEqual(stored["rejected"], 1)
        self.assertEqual(stored["stored"], "cosmos" if leaderboard.storage_backend() == "cosmos" else "memory-local-only")
        result = get_my_player_metrics(self.auth_headers(registered["sessionToken"]))
        self.assertTrue(result["ok"])
        self.assertEqual(result["metrics"]["fightsObserved"], 1)
        self.assertEqual(result["metrics"]["observedKills"], 1)
        self.assertEqual(result["metrics"]["deaths"], 1)
        self.assertEqual(result["metrics"]["returns"], 1)
        self.assertEqual(result["metrics"]["opponentDamage"], 31)
        self.assertEqual(result["metrics"]["friendlyFireDamage"], 4)
        self.assertEqual(result["metrics"]["damageInflicted"], 35)
        self.assertEqual(result["metrics"]["damageReceived"], 18)
        self.assertEqual(result["metrics"]["thirdPartyDamage"], 7)
        self.assertEqual(result["metrics"]["activitySamples"], 1)
        self.assertEqual(result["metrics"]["eventsTracked"], 8)

        reinstalled = register_plugin({
            "installId": "22222222-2222-4222-8222-222222222222",
            "playerName": "  oyama  ",
            "clanName": "TRAPISTAN",
            "clanRank": 1,
        })
        reinstalled_metrics = get_my_player_metrics(self.auth_headers(reinstalled["sessionToken"]))
        self.assertEqual(reinstalled_metrics["metrics"], result["metrics"])


if __name__ == "__main__":
    unittest.main()
