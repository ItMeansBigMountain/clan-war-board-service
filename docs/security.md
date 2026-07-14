# Security Plan

Clan War Board will be a public PvP/clan service, so assume hostile traffic from day one.

## Threat model

Likely attacks:

- fake clan/leader submissions
- spam war creation
- leaderboard manipulation
- scraping sensitive upcoming war intel
- API flooding to burn free-tier quotas
- request payload abuse
- automated account/clan impersonation
- noisy logs causing Azure cost spikes

## Security principles

0. **Do not pretend RuneLite traffic can be perfectly proven**

   The service is RuneLite-plugin-oriented, but any public Java client can be reverse engineered. Do not rely on an embedded static secret. Use install registration, short-lived tokens, leader/rank checks, rate limits, corroboration, and anomaly detection.

1. **No public upcoming intel by default**

   Public APIs must not expose exact upcoming world, hotspot, rally notes, fallback worlds, or leader notes.

2. **Completed summaries only for public leaderboard**

   Leaderboards rank clans using completed/sanitized summaries, not live or upcoming locations.

3. **Explicit online-sync disclosure**

   The RuneLite plugin must clearly warn users before sending player name, clan name, observed rank, and war actions.

4. **Rate limits before popularity**

   Add API-level throttling before any public launch. Free-tier abuse can become a cost problem.

5. **Input validation everywhere**

   Validate clan names, player names, world IDs, timestamps, hotspot IDs, and string lengths.

6. **Append-only audit trail for war actions**

   Proposal/accept/cancel/complete actions should be auditable. Do not silently overwrite leader actions.

7. **Terms hash for agreement**

   Leader acceptance must bind to exact terms. If terms change, force re-confirmation.

8. **Website is read-only**

   The public website must use read-only public endpoints or static JSON snapshots. It must not receive tokens capable of creating fights, accepting applications, or submitting telemetry.

9. **Telemetry is evidence, not truth**

   Fight statistics are derived from multiple observations. Single-client claims should be weighted cautiously and can be rejected or marked low confidence.

## MVP access model

V1 is community-trust based:

- RuneLite plugin observes current clan/rank locally.
- Backend stores action source as plugin-submitted.
- Clan remains unverified until a later claim/verification flow exists.
- Public UI labels unverified clans clearly.

V2 stronger model:

- clan claiming
- Discord OAuth/bot role verification
- verified leader accounts
- abuse/report handling

## Azure hardening checklist

- HTTPS only.
- TLS 1.2 minimum.
- Storage account public blob access disabled.
- No secrets in repo.
- Managed identity preferred over connection strings when practical.
- Cosmos DB free tier with shared throughput <= 1000 RU/s.
- Budget alerts at $5 and $10.
- Application Insights sampling low or disabled.
- No full request/response body logging.
- API payload size limits.
- Cache public leaderboard responses.

## Plugin Hub privacy warning draft

```text
Online Sync sends your player name, clan name, observed clan rank, plugin version, and war board actions to the Clan War Board service. This is used to share war schedules, leader confirmations, and completed-war leaderboard summaries. Upcoming exact world, hotspot, and rally notes are clan/member-only by default and are not published to the public leaderboard.
```
