# RuneLite Plugin UX Plan

## Width constraint

Clan War Board must preserve the narrow RuneLite side-panel width used by the user's proven plugins. Do not add wide horizontal tab bars or buttons that force resizing.

Use a vertical view selector or compact dropdown at the top. Every view stacks content vertically.

## Top-level views

Suggested view selector values:

```text
Board
My Clan
Leader
Live
Results
Settings
```

## Board view

Purpose: browse fight availability and accepted/confirmed fights.

Member/leader content:

```text
Open fights
- Clan name
- rough time
- target size
- war type
- verification badge
- [Interested] only if leader eligible
```

Non-leader clicking Interested:

```text
Leader access required
Your current clan rank does not allow fight management.
Ask an Administrator, Deputy Owner, or Owner to manage Clan War Board fights.
```

## My Clan view

Purpose: show plugin network/readiness.

```text
Clan: TRAPISTAN
Plugin members seen: 58
Recently active: 42
Leader eligible seen: 4
Upcoming confirmed fights: 1
Live fights: 0
```

This view helps leaders understand that the plugin knows the clan because members installed it and are heartbeating.

## Leader view

Only for eligible leaders. Members see the leader-access-required card.

Leader can:

```text
Post availability
View applications
Accept/counter/reject
Confirm/cancel fight
```

Form should be narrow:

```text
Ready time
Duration
Target size
War type
Rules summary
Private terms section
[Post availability]
```

Private terms should be visually marked:

```text
Private: exact world/location/rally notes are not public before confirmation.
```

## Live view

Purpose: crucial overview metrics during a fight.

```text
TRAPISTAN vs Rival Clan
Time left: 42m
Confidence: Medium

Active members
TRAPISTAN: 48
Rival: 45
Third-party: 7

Observed events
Kills: 22 / 19
Returns: 55 / 44
Damage: 8.2k / 7.9k

Signal
TRAPISTAN slightly ahead
Heavy third-party interference
```

The panel should not try to show the full analytics table. It should show compact overview only and link/direct to the website for details.

## Results view

Purpose: recent completed fights.

```text
Latest result
TRAPISTAN defeated Rival Clan
Confidence: Medium
Kills: 34 / 27
Returns: 79 / 63
Third-party interactions: 27
[Open full analytics]
```

## Settings view

```text
Online Sync: enabled/disabled
Refresh interval
Telemetry disclosure
Service URL
Privacy summary
```

## Leader access message

Use this exact style/message target:

```text
Leader access required
Your current clan rank does not allow fight management.
Ask an Administrator, Deputy Owner, or Owner to manage Clan War Board fights.
```

If the configured minimum is stricter, substitute the configured minimum.

## Tracking disclosure

The plugin should clearly state before enabling online sync:

```text
Online Sync sends your player name, clan name, observed clan rank, plugin version, fight actions, and fight event observations to the Clan War Board service. This powers clan fight scheduling, live fight metrics, and completed fight analytics. Upcoming exact world/location/rally notes are private by default and are not shown on the public website.
```

## Event collection UX

During a confirmed fight, show tracking state:

```text
Tracking this fight
Submitting batched observations every few seconds.
No live player locations are published publicly.
```

If outside fight window:

```text
Fight tracking starts at the agreed time.
```

If not in participating clan but nearby/damaged/damaging:

```text
Third-party interaction observed
Your events may be counted as outside interference in the public summary.
```

## Website handoff

The plugin shows summary metrics only. Full analytics are website-first:

```text
Open full analytics
```

Opening URL should go to a public completed-fight page, not an upcoming private-intel page.
