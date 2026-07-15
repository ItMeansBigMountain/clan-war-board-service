import json

try:
    import azure.functions as func
except ImportError:  # Allows unit tests/imports without Azure Functions installed.
    func = None

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
    search_clans,
    submit_telemetry_batch,
)


if func is not None:
    app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

    @app.route(route="health", methods=["GET"])
    def health_route(req):
        return json_response(health())

    @app.route(route="leaderboard", methods=["GET"])
    def leaderboard_route(req):
        return json_response(get_competitive_leaderboard())

    @app.route(route="challenge-system", methods=["GET"])
    def challenge_system_route(req):
        return json_response(get_challenge_system())

    @app.route(route="judging-system", methods=["GET"])
    def judging_system_route(req):
        return json_response(get_win_judging_system())

    @app.route(route="clans", methods=["GET"])
    def clans_route(req):
        query = req.params.get("q") if req.params else None
        if query:
            return json_response(search_clans(query))
        return json_response(get_clans())

    @app.route(route="clans/{clanId}", methods=["GET"])
    def clan_route(req):
        clan_id = req.route_params.get("clanId", "")
        clan = get_clan(clan_id)
        if clan is None:
            return json_response({"error": "clan_not_found"}, status_code=404)
        return json_response(clan)

    @app.route(route="public/availability", methods=["GET"])
    def availability_route(req):
        return json_response(get_public_availability())

    @app.route(route="public/battles", methods=["GET"])
    def battles_route(req):
        return json_response(get_past_battles())

    @app.route(route="public/fights/{fightId}/summary", methods=["GET"])
    def fight_summary_route(req):
        fight_id = req.route_params.get("fightId", "")
        summary = get_public_fight_summary(fight_id)
        if summary is None:
            return json_response({"error": "fight_not_found"}, status_code=404)
        return json_response(summary)

    @app.route(route="fight-setup/schema", methods=["GET"])
    def fight_setup_schema_route(req):
        return json_response(get_fight_setup_schema())

    @app.route(route="theme/assets", methods=["GET"])
    def theme_assets_route(req):
        return json_response(get_theme_assets())

    @app.route(route="plugin/events/batch", methods=["POST"])
    def telemetry_batch_route(req):
        try:
            payload = req.get_json()
        except Exception:
            payload = None
        result = submit_telemetry_batch(payload, dict(req.headers or {}))
        return json_response(result, status_code=202 if result.get("ok") else 400)


def json_response(payload: dict, status_code: int = 200):
    if func is None:
        return json.dumps(payload, sort_keys=True)
    return func.HttpResponse(
        json.dumps(payload, sort_keys=True),
        status_code=status_code,
        mimetype="application/json",
        headers={
            "Cache-Control": "public, max-age=60",
            "X-Content-Type-Options": "nosniff",
        },
    )
