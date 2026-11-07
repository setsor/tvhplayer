# Recording identity and duplicate prevention (TVHplayer)

Status: proposed for review, 2026-11-07. Client-side behaviour; no server changes.

## Rules

- Only **one Quick Record per channel** should be started from the player,
  channel context menu, or shortcuts. Stop from the player targets one Quick
  only; existing concurrent Quick jobs remain selectable in Tasks.
- Do not create Quick and Scheduled DVR entries for the **same EPG event on
  the same channel**. Use the server's broadcast/event ID when available.
- A manual-duration Quick has no broadcast ID; associate it with the
  programme during which it began (allow DVR pre-roll tolerance).
- Different EPG programmes on the same channel may be scheduled separately,
  even if padded recording intervals overlap. The same programme on a
  different channel remains independent.
- Never infer programme identity from the channel name alone.
- When a user attempts to schedule a programme already being captured by
  Quick Record, offer to extend the existing recording to the programme end
  (without shortening it) when necessary. Otherwise explain the existing
  recording and offer Tasks.
- Each creation path checks the server's **current DVR list** just before
  sending a create RPC. A stale UI display cannot authorize a duplicate.
- With no EPG, the player fails safely if another recording is already active
  on that channel; unrelated upcoming programmes remain schedulable.
- Tasks continues to stop or cancel by the individual DVR entry identifier.
- Server-side duplicate handling and unrelated clients are unchanged.

## Verification

Pure tests cover broadcast ID matching, same channel/different programme,
different channels, manual Quick association, old scheduled metadata, and
completed recordings. UI tests cover player, channel EPG, TV Guide and Tasks
regressions.

## Separate TVHeadend finding

A Synology DSM/Linux DVR profile using "Don't keep" repeatedly invoked
POSIX_FADV_DONTNEED in its pass-muxer write path. During historical 50s API
stalls the DVR thread appeared in writeback/cache waits. Switching that
profile to "System" correlated with substantially faster Stop Recording and
stable short API probes. This is an operational observation, not proof of a
specific lock dependency, and is unrelated to the client duplicate guard.
