# Contributing

## Which folder?

- `offline/` is the real election. Most work happens here.
- `online/` is an experimental demo (fake data only). Work there only if the team has agreed.
- **One folder per pull request.** If both need the same change, make two pull requests.

## Workflow (simple Git for the team)

1. `git pull` to get the latest `main`.
2. Create a branch for your task: `git checkout -b stage-2-tokens`.
3. Make small changes, run `pytest`, commit often with clear messages:
   `git commit -m "Add token check endpoint"`.
4. Push your branch and open a pull request. Someone else reads it before it is merged.
5. Never commit directly to `main` and never force-push.

## Before you open a pull request

- [ ] `pytest` passes (run it from the `offline/` folder)
- [ ] The server still starts (also from `offline/`)
- [ ] No secrets or election data in the commit (`git status` shows nothing from `offline/data/`)
- [ ] No `.env` files or Supabase keys
- [ ] No CDN links or internet access added
- [ ] Comments explain *why*, not just *what*, so the next person can follow

## Anonymity checklist (review these for every change)

- [ ] Nothing added to `votes` besides `id` and `candidate_id`
- [ ] No timestamps, IPs, or device info stored next to votes or tokens
- [ ] Vote endpoint is not logged with IP or time
- [ ] Tokens are stored only as hashes
- [ ] Exports never join tokens with votes

## Election day

Tag the exact commit that was tested and will be run: `git tag election-v1` then
`git push origin election-v1`. Run the server from that tag, so observers can check
that the code was not changed after the dry run.

## Code style

Keep it short and readable. Observers have to trust this code, so
a plain 10-line function beats a clever 3-line one.
