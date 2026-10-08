# Contributing

## Workflow (simple Git for the team)

1. `git pull` to get the latest `main`.
2. Create a branch for your task: `git checkout -b stage-2-tokens`.
3. Make small changes, run `pytest`, commit often with clear messages:
   `git commit -m "Add token check endpoint"`.
4. Push your branch and open a pull request. Someone else reads it before it is merged.
5. Never commit directly to `main` and never force-push.

## Before you open a pull request

- [ ] `pytest` passes
- [ ] The server still starts
- [ ] No secrets or election data in the commit (`git status` shows nothing from `data/`)
- [ ] No CDN links or internet access added
- [ ] Comments explain *why*, not just *what*, so the next person can follow

## Anonymity checklist (review these for every change)

- [ ] Nothing added to `votes` besides `id` and `candidate_id`
- [ ] No timestamps, IPs, or device info stored next to votes or tokens
- [ ] Vote endpoint is not logged with IP or time
- [ ] Tokens are stored only as hashes
- [ ] Exports never join tokens with votes

## Code style

Keep it short and readable. Observers have to trust this code, so
a plain 10-line function beats a clever 3-line one.
