import json

try:
    import azure.functions as func
except ImportError:  # Allows unit tests/imports without Azure Functions installed.
    func = None

from leaderboard import get_clan, get_leaderboard, get_public_availability, get_public_fight_summary, health


if func is not None:
    app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

    @app.route(route="health", methods=["GET"])
    def health_route(req):
        return json_response(health())

    @app.route(route="leaderboard", methods=["GET"])
    def leaderboard_route(req):
        return json_response(get_leaderboard())

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

    @app.route(route="public/fights/{fightId}/summary", methods=["GET"])
    def fight_summary_route(req):
        fight_id = req.route_params.get("fightId", "")
        summary = get_public_fight_summary(fight_id)
        if summary is None:
            return json_response({"error": "fight_not_found"}, status_code=404)
        return json_response(summary)


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
