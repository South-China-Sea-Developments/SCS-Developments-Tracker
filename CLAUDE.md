# Working on the SCS Developments Tracker

Read by every Claude session in this repository. The maintainer is Angelo M. (GitHub `Angelo-M-SCS`).

## Tasks run to the end, whether or not the maintainer is watching

The maintainer may shut his laptop at any point in a task. The session runs in the cloud and keeps going;
what stops work is the end of a reply (background processes are stopped a few minutes later) and steps
that wait for an approval nobody is there to give. So:

- Keep every wait inside the turn: CI checks, merges, the publish run, clearing Airtable rows. Poll in the
  foreground in chunks of up to ten minutes until the task is done; do not end the reply with a helper
  script still running in the background.
- If a task cannot finish within the turn, set up a scheduled check-in in this session (send_later) that
  resumes it, rather than letting it stall.
- Get any step that needs the maintainer's approval (changing a scheduled task, for instance) done while he
  is present, or take a route that needs none. If neither is possible, finish everything else, and say
  exactly what is waiting and why.
- When the maintainer is away, do not ask questions: take the most reasonable reading, say which in the
  report, and carry on. A decision that cannot be undone and could reasonably go either way is the
  exception: prepare it, set it out, and stop there.
- End with a report sent with SendUserMessage, so it reaches him wherever he reads next.

## Standing rules

- Never commit to `main`: always a branch and a pull request, created with `gh api` (the `gh pr`
  subcommands do not work through the proxy).
- Never `git add -A`; add named paths only.
- `data/raw/` is never edited.
- Airtable only through the Airtable connector; there is no token, and none is to be asked for or pasted.
- The maintainer's decisions recorded in Airtable are his review (decision 07); a sitting is applied and
  merged once the pipeline and CI accept it. A merge or duplicate whose lead was rejected is rejected with
  it (#133).
- The de-escalation tracker is a separate project, done by the maintainer outside the ASPI framework:
  never merge it into this one.
- Write in English.
