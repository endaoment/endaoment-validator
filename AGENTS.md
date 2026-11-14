# Endaoment Validator Agent Guide

This file is the entry point for every coding agent in `endaoment-validator`, whatever the harness (Claude Code, Cursor, Codex, and others) and however it runs (terminal, IDE, desktop, cloud, or headless in CI). Read this file before you change anything. [`CLAUDE.md`](./CLAUDE.md) imports this file and holds only Claude Code specifics.

## Overview

`endaoment-validator` is Endaoment's public Ethereum validator build guide. Endaoment runs its own validators on a Reth (execution client) and Prysm (consensus client) node, and the guide is the standard operating procedure (SOP) a human operator follows to build, update, monitor, and recover that node. The repo holds MDX pages, a Mintlify site config, and monitoring config templates. The repo holds no application code, no Terraform, no deploy scripts, and no keys.

Mintlify publishes the guide to [validators.endaoment.org](https://validators.endaoment.org) from `main`, and the Mintlify GitHub app builds a preview site for every pull request (the `Mintlify Deployment` check). The GitHub repo is public, so everything committed here is public too.

| Path                                            | What it holds                                                                                            |
| ----------------------------------------------- | -------------------------------------------------------------------------------------------------------- |
| `validators/introduction.mdx`                   | The guide's readme: table of contents, overall flow, and disclaimers                                     |
| `validators/validator-open-source-publish.mdx`  | The post announcing the open-source guide                                                                |
| `validators/validator-sop-part1-setup.mdx`      | Part 1: hardware, Ubuntu server, Reth, Prysm, key import, and the deposit                                |
| `validators/validator-sop-part2-upkeep.mdx`     | Part 2: package updates, Reth and Prysm updates, exits, sync committees, MEV-Boost, and Reth resets      |
| `validators/validator-sop-part3-emergency.mdx`  | Part 3: emergency action plans for a dead node or a missing operator                                     |
| `validators/validator-sop-part4-monitoring.mdx` | Part 4: Prometheus, exporters, and the Grafana dashboard                                                 |
| `.imgs/`                                        | Prometheus, exporter, StakeLocal, and Grafana config files that Part 4 tells the operator to copy        |
| `images/`, `logo/`                              | Site images, plus `images/variables.xlsx`, the blank template for the operator's paper record of secrets |
| `mint.json`                                     | Mintlify site config, including the `navigation` list of published pages                                 |
| `cspell.json`                                   | The spellcheck word list                                                                                 |

## Commands

```bash
npm ci                      # install; also runs `husky install` for the pre-commit hook
npm run dev                 # local Mintlify preview
npx mintlify broken-links   # the pre-commit hook runs this
npm run spellcheck:sop      # cspell over the four SOP parts
npm run check               # both checks above
toolbox agent-check         # the agent entry check
```

Install with `npm ci`. The repo commits `package-lock.json` and no `yarn.lock`, even though `package.json` names Yarn in `packageManager`.

`npm run check` and `toolbox agent-check` prove a change is done. `npm run check` runs `mintlify broken-links` and `npm run spellcheck:sop`, and fails if either fails. For a change to rendered content, also open the page in `npm run dev` or in the pull request's Mintlify preview.

## Agent entry check

The agent entry check lives in `endaoment-toolbox`. It checks `AGENTS.md` and `CLAUDE.md` against the rot guards in `endaoment-fabric/standards/agent-instructions.md`, and it reads toolbox skill and rule names from the toolbox catalog, so this repo keeps no copy of the check and no catalog snapshot. The workflow `.github/workflows/agent-entry-check.yml` runs it on every pull request through the `endaoment/endaoment-toolbox/tools/agent-entry-check` action, but only while GitHub Actions is turned on for this repo, so run `toolbox agent-check` from the repo root yourself before you open a pull request.

## What an agent must never do

The guide describes a machine that holds Endaoment's staked ETH. A wrong command on that machine, or a leaked key, can get the validators slashed or lose the stake, and a pull request review never sees either. An agent in this repo edits documentation only:

1. Never connect to the validator node or any machine near the validator node, and never run the SOP's operator commands (`systemctl`, `ufw`, `reth`, `prysm`, `deposit`, and the rest) anywhere. The SOP's commands are for a human operator at the node.
2. Never create, ask for, read, store, or repeat key material: a mnemonic, a validator keystore, a keystore or wallet password, the client auth JWT secret, an SSH key, or a filled-in copy of the variables document. The SOP keeps these on paper and offline USB drives on purpose. If you find something in the repo or a pull request that looks like key material, do not quote the value. Stop and report the file and line to a human.
3. Never prepare, sign, or send an on-chain action: a deposit, a voluntary exit, a withdrawal address change, or any Launchpad action. A deposit or an exit cannot be undone.
4. Never add operational details that are not already public: the node's location, IP addresses, SSH ports, hardware serials, or operator contact details. Examples use the placeholder style the SOP already uses, such as `{YourWithdrawalAddress}` and `{yourusername}`.

Two shared rules sit next to these limits:

1. `terraform-owned-infra` makes Terraform the only write path for infrastructure Terraform owns. The validator node and its monitoring stack are a physical machine that no Terraform module declares, so `terraform-owned-infra` gives an agent no write path to the node either. If a task ever reaches Endaoment cloud infrastructure, `terraform-owned-infra` applies in full.
2. `endaoment-fabric/standards/agent-credentials.md` governs the credentials an agent itself uses, which live in GCP Secret Manager. Validator key material is not an agent credential and has no agent path at all.

## Editing the guide

- Most changes bump the Reth or Prysm version. Each version appears in both Part 1 and Part 2: in a "current as of" sentence and in every download URL and file name. Change every occurrence in both files, take the version from the client's official GitHub releases page, and do not guess a version.
- A table of contents at the top of each SOP part links to heading anchors, and Part 3 sets its anchors with `<a id>` tags. When you rename a heading, update every link to the heading's anchor.
- A new page needs an entry in `mint.json` `navigation` and in the table of contents in `validators/introduction.mdx`.
- When cspell flags a correct technical word, add the word to `cspell.json` `words`.
- Keep the disclaimers in `validators/introduction.mdx`, and keep the tone of the pages around your change.
- `.mintignore` keeps this file, `CLAUDE.md`, and `tools/` off the published site. Add any new file that is not a guide page to `.mintignore`.

## Shared rules

These toolbox rules apply in every Endaoment repo. Read each one that is not already in your context, from the `endaoment-toolbox` clone next to this repo's main clone (from a worktree, that is next to the folder `git rev-parse --git-common-dir` points into), or with `gh api repos/endaoment/endaoment-toolbox/contents/catalog/rules/<name>/index.md -H "Accept: application/vnd.github.raw"`. If a rule cannot be read either way, keep working, with two limits: make no infrastructure change without `terraform-owned-infra`, and no Notion write without `issue-status-honesty`. Name every rule you could not read at the top of your final report and PR body.

- `endaoment-toolbox/catalog/rules/good-code/index.md`: what good code looks like, by topic
- `endaoment-toolbox/catalog/rules/hyperlinking/index.md`: accurate deep links in agent messages
- `endaoment-toolbox/catalog/rules/issue-status-honesty/index.md`: set the Issue to In progress before work starts
- `endaoment-toolbox/catalog/rules/markdown-style/index.md`: markdown formatting conventions
- `endaoment-toolbox/catalog/rules/systematic-debugging/index.md`: find the root cause before any fix
- `endaoment-toolbox/catalog/rules/tdd-bug-fixes/index.md`: failing test first, then the fix
- `endaoment-toolbox/catalog/rules/terraform-owned-infra/index.md`: Terraform is the only write path for infrastructure it owns
- `endaoment-toolbox/catalog/rules/thin-deliverables/index.md`: lead with the answer, link the paper trail
- `endaoment-toolbox/catalog/rules/verify-before-done/index.md`: fresh evidence before claiming something works
- `endaoment-toolbox/catalog/rules/voice/index.md`: writing published under a person's name
- `endaoment-toolbox/catalog/rules/write-for-humans/index.md`: plain prose a reader understands on the first read

## Shared workflows, policy, and memory

- This repo has no toolbox install of its own, so toolbox skills reach it from the parent Endaoment folder's install, and where none exists, read `endaoment-toolbox/catalog/skills/<name>/SKILL.md` and follow it (for example `/open-pr` for a pull request).
- Fabric documents shared policy, not runnable procedures. Start with `endaoment-fabric/standards/fabric-toolbox-boundaries.md`. Name branches and pull requests per `endaoment-fabric/standards/git-branch-and-pr-naming.md`.
- An `endaoment-fabric/<path>` or `endaoment-toolbox/<path>` citation resolves from that repo's clone next to this repo's main clone (from a worktree, next to the folder `git rev-parse --git-common-dir` points into), from `fabric <path>` where the Fabric CLI is installed, or from GitHub: `gh api repos/endaoment/<repo>/contents/<path> -H "Accept: application/vnd.github.raw"`.
- The MDX pages under `validators/` are this repo's only docs. This repo keeps no agent memory file, and this repo has no rule files beyond this one. A lesson worth keeping becomes an edit to this file or to the guide.
- When a step needs a human decision and nobody can answer, as in a headless or CI run, stop and report the decision needed. Do not guess.
