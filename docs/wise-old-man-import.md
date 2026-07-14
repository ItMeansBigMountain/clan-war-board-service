# Wise Old Man Clan/Group Import Plan

Wise Old Man has group/clan functionality and public API documentation. We can use it as an optional enrichment source when a clan already maintains a WOM group.

## Goals

- Help clans avoid re-entering member lists.
- Link Clan War Board clan pages to existing WOM groups when available.
- Import public group/member metadata only after clan opt-in.
- Never use WOM import to expose upcoming war world/location/time.

## Candidate data to import

Allowed:

```text
WOM group ID
WOM group name
public member list
public player names
public WOM ranks/scores/metrics
```

Not allowed:

```text
upcoming war world
upcoming hotspot
leader notes
rally/fallback locations
private Discord info
```

## Integration approach

V1:

- Add optional `womGroupId` on clan records.
- Display a WOM link on public clan pages.
- Do not auto-sync unless a leader opts in.

V2:

- Scheduled import of public WOM group members.
- Use imported members to help match clan membership, with clear "WOM-sourced" labels.
- Add stale-data timestamp.

## Security and abuse notes

- Treat WOM data as public enrichment, not authority for leader permissions.
- Do not let arbitrary users overwrite a clan's WOM group ID after verification.
- Cache WOM reads to avoid hammering WOM's API.
- Add User-Agent identifying Clan War Board service.
