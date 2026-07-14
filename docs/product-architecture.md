# Clan War Board Product Architecture

## Product goal

Clan War Board is a RuneLite-first competition network for OSRS clans:

1. Clan leaders publish fight availability.
2. Other clan leaders browse openings and apply/accept a fight.
3. The RuneLite plugin tracks the fight from participating clients during the agreed window.
4. The service aggregates evidence into fight statistics and winner analysis.
5. The plugin shows crucial overview metrics in a narrow RuneLite panel.
6. The website shows detailed public analytics after the fight, without allowing website users to tamper with fight data.

## Non-negotiables

- High traffic, low latency, near-free Azure hosting.
- Secure enough to expect attackers from day one.
- Website must be read-only for public analytics; it must not be able to create/alter fights.
- Upcoming fight intel is private by default.
- Write APIs are RuneLite-plugin-oriented, but we cannot cryptographically prove a Java client is unmodified. Therefore, security must combine plugin tokens, server validation, rate limiting, quorum rules, anomaly detection, and leader verification.
- RuneLite panel width must stay consistent with the user's proven working OSRS plugins: narrow side panel, vertical tabs/views, no horizontal widening.

## UX: leader availability and acceptance

### Leader posts availability

A clan leader opens the RuneLite plugin's leader view and posts:

```text
Clan: TRAPISTAN
Availability: Sunday 8 PM ET
Fight size target: 40v40 to 60v60
Duration: 60 minutes
War type: Wilderness / multi
Allowed rules: returns allowed, no rag alts, etc.
Privacy: public availability, private exact world/location until match confirmed
```

The backend stores this as an `availability_post`.

Public browsing exposes only safe fields:

```text
clan name
rough time window
size target
war type
rules summary
leader verification status
```

It does not expose exact world/hotspot/rally/fallback data unless both leaders mark it public.

### Opposing leader applies/interests

Another verified/locally-qualified clan leader browses available fights in the plugin and clicks:

```text
Interested / Apply
```

The backend creates a `fight_application`:

```text
post id
challenger clan
requested time
message/rules note
status = pending
```

The original leader sees applications in the leader tab and can:

```text
accept
counter
reject
```

### Match confirmation

A fight becomes confirmed only when:

1. both leader-side clan records exist,
2. both leaders are allowed by current access rules,
3. both sides accept the exact same terms hash,
4. the service records a confirmed `fight_id` and immutable `terms_hash`.

If terms change after acceptance:

```text
status = reconfirm_required
```

No plugin should treat it as live until reconfirmed.

## UX: member install/network effect

If clan members install the plugin, the plugin reports membership heartbeats:

```text
player name
clan name
observed rank
plugin version
world only when relevant/allowed
online/participant status
```

This lets the service understand:

- how many plugin-enabled players a clan has,
- who is eligible for fight tracking,
- who appears in the agreed fight window,
- how many independent clients corroborate events.

Members do not need leader controls. If a member opens a leader-only view, the plugin displays:

```text
Leader access required
Your current clan rank does not allow fight management.
Ask an Administrator, Deputy Owner, or Owner to manage Clan War Board fights.
```

Exact rank wording should follow the configured minimum leader rank.

## Fight lifecycle

```text
availability_posted
application_pending
terms_confirmed
pre_fight_countdown
live_tracking
aggregation_pending
completed_pending_review
published
cancelled/disputed
```

## Fight tracking model

During the confirmed time window, participating plugins submit event observations. The service aggregates evidence rather than trusting a single client.

Tracked event types:

```text
participant_seen
damage_dealt
damage_taken
kill_observed
death_observed
return_detected
world_presence
third_party_interaction
```

### Metrics to derive

Overview metrics for plugin:

- fight status and time remaining,
- participating clans,
- active plugin-confirmed members per clan,
- kills/deaths observed,
- return counts,
- third-party interference count,
- tentative winner signal,
- confidence score.

Detailed website analytics:

- timeline of kills/deaths/returns,
- peak active participants,
- unique members seen by clan,
- member return counts,
- damage dealt/taken by clan,
- third-party damaged/damaging players,
- verified vs unverified observations,
- confidence/anomaly notes,
- winner explanation.

## Winner analysis

The service should not blindly say a winner from one stat. Use a weighted analysis:

```text
winner_score =
  kill_score
+ return_score
+ presence_score
+ damage_score
- death_penalty
- third_party_noise_penalty
- low_confidence_penalty
```

The published result should include:

```text
winner: clan id or disputed
confidence: high/medium/low
explanation: why the model picked that result
major caveats: e.g. heavy third-party interference
```

If data is too noisy, publish:

```text
Result: disputed / insufficient confidence
```

## Website role

The website is detailed analytics and public presentation only.

Website can read:

- public availability listings,
- public clan pages,
- completed fight summaries,
- public leaderboard snapshots,
- detailed completed analytics that pass privacy filters.

Website cannot write:

- fight creation,
- leader acceptance,
- live event telemetry,
- member identity claims,
- winner overrides.

Admin/moderation writes, if ever needed, should use a separate admin-only path with Azure auth/GitHub environment style controls, not the public website.

## RuneLite plugin tabs

Keep the same side-panel width as proven previous plugins. Use vertical views/tabs/selector, not wider horizontal layouts.

Suggested views:

1. **Board** — browse availability and confirmed fights.
2. **My Clan** — clan install count, member readiness, current fights.
3. **Leader** — create availability, review applications, accept/counter/reject.
4. **Live** — current fight overview metrics.
5. **Results** — latest completed fight summaries.
6. **Settings** — sync/privacy/refresh controls.

Leader-only views should show the no-access message for normal members.

## Data privacy rules

Public before fight:

- clan names,
- rough time window,
- size target,
- rules summary,
- availability/application status.

Private before/during fight:

- exact world,
- exact hotspot/location,
- rally notes,
- fallback worlds,
- leader notes,
- live player positions.

Public after fight:

- sanitized completed analytics,
- winner/confidence,
- aggregated fight metrics,
- player names only if product policy allows; default should aggregate by clan/member role until consent policy is finalized.
