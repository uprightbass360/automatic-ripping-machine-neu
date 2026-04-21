# Claude Code Project Instructions

## Superpowers Docs Location

Plans, specs, and research for this project live in a **separate private repo**, not in this repo. This keeps AI-collaboration artifacts out of the project history and syncs them across machines.

Expected location: `../ai/<project-subdir>/docs/superpowers/`
  - arm-neu        -> ../ai/arm-neu/docs/superpowers/
  - arm-ui         -> ../ai/arm-ui/docs/superpowers/
  - arm-transcoder -> ../ai/arm-transcoder/docs/superpowers/

When the brainstorming, writing-plans, or executing-plans skills reference `docs/superpowers/specs/...` or `docs/superpowers/plans/...`, resolve those paths against the sibling `ai/` repo above, not this repo.

If the sibling `ai/` directory does not exist, ask the user before creating specs/plans anywhere else. Other developers using this fork should maintain their own equivalent sibling repo.

## Git Commits
- Never include `Co-Authored-By` lines in commit messages
- Do not sign commits with Claude's name or email
