#!/usr/bin/env python3
# agent-entry-check v3
"""agent_entry_check.py: the rot guards for a repo's agent entry files.

Checks `AGENTS.md`, `CLAUDE.md`, and any `--extra` instruction file against the
rules in `endaoment-fabric/standards/agent-instructions.md`: the entry size
bound, the `CLAUDE.md` import, the Shared rules block, dead paths, and toolbox
skill and rule names. Toolbox names are checked against a committed snapshot of
the toolbox catalog, because CI can read neither the toolbox repo nor `gh`.

Each Endaoment repo that uses this script carries an identical copy, marked by
the `# agent-entry-check v3` line above. Change every copy together, and bump the
marker when the behaviour changes, so `grep -r "agent-entry-check v"` finds a
copy that fell behind. Python 3.9+, standard library only.

What counts as a path or a skill:

- A relative Markdown link outside inline code counts, resolved from the
  naming file's folder, as GitHub resolves it. A backticked token counts only
  when it has a slash, no placeholder or glob characters, does not start with
  `/`, `./` or `../`, and its first segment exists at the repo root; it may
  resolve from the naming file's folder or the repo root.
- A skill is a backticked `/name` on a line that mentions skills, a
  "`name` toolbox skill", or an `endaoment-toolbox/catalog/skills/<name>/` path,
  so routes such as `/v1` are not skills. A skill name also passes when git
  tracks the repo's own `SKILL.md` for it (an ignored toolbox install does not
  count), when it is a harness command such as `/loop`, or when it is a
  placeholder such as `/skill-name`.
- Toolbox docs paths (`endaoment-toolbox/catalog/docs/...`) are not checked,
  because the snapshot format lists only skills and rules.

Run from the repo root:

    python3 path/to/agent_entry_check.py [--extra FILE ...] [--snapshot PATH]
    python3 path/to/agent_entry_check.py refresh [--clone PATH] [--ref SHA] [--snapshot PATH]

The check exits 1 with one line per violation. Outside CI (env `CI` unset or
empty) it also reads the live catalog and warns when the snapshot has drifted,
but never fails on drift. `refresh` rewrites the snapshot from GitHub when `gh`
is signed in, else from the `endaoment-toolbox` clone next to this repo's main
clone, or from `--clone PATH`. The snapshot defaults to
`toolbox-catalog.snapshot.json` beside this script.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from typing import Callable

TOOLBOX_REPO = "endaoment/endaoment-toolbox"
SNAPSHOT_NAME = "toolbox-catalog.snapshot.json"
SNAPSHOT_LISTS = ("skills", "rules", "alwaysOnRules")
AGENTS_FILE = "AGENTS.md"
CLAUDE_FILE = "CLAUDE.md"
CLAUDE_IMPORT_LINE = "@AGENTS.md"
# Codex stops reading project docs at 32 KiB combined; 20 KiB leaves room for a nested AGENTS.md.
ENTRY_MAX_BYTES = 20 * 1024

FRONTMATTER_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---", re.S)
ALWAYS_APPLY_RE = re.compile(r"^alwaysApply:\s*(?:true|True|TRUE)\s*(?:#.*)?$", re.M)

# A fence opens with three or more backticks or tildes; a backtick opener's info string has no backtick.
FENCE_OPEN_RE = re.compile(r"^([ \t]*)(`{3,}(?=[^`\n]*$)|~{3,})")
# A fence closes on the same character, at least as long, indented at most 3 spaces past the opener.
FENCE_CLOSE_RE = re.compile(r"^([ \t]*)(`{3,}|~{3,})[ \t]*$")
# An unclosed comment hides everything after it, so it runs to the end of the text.
HTML_COMMENT_RE = re.compile(r"<!--.*?(?:-->|\Z)", re.S)
LIST_ITEM_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s")
HEADING_RE = re.compile(r"^(#{1,6})[ \t]+(.*)$", re.M)
SHARED_RULES_TITLE_RE = re.compile(r"shared rules\b", re.I)
SHARED_RULE_PATH_RE = re.compile(r"endaoment-toolbox/catalog/rules/([a-z0-9-]+)/index\.md")
TOOLBOX_RULE_NAME_RE = re.compile(r"endaoment-toolbox/catalog/rules/([a-z0-9-]+)")

BACKTICK_TOKEN_RE = re.compile(r"`([^`\s]+)`")
CODE_SPAN_RE = re.compile(r"`[^`\n]*`")
# A link target up to its anchor or title.
LINK_TARGET_RE = re.compile(r"\]\(([^)#\s]+)")
URL_SCHEME_RE = re.compile(r"^[a-z]+:", re.I)
# A token with any of these is a placeholder, a glob, a command, or a package, not a path.
NON_PATH_CHARS_RE = re.compile(r"[<>*{}$:@]")
SKILL_LINE_RE = re.compile(r"skill", re.I)
BACKTICKED_SKILL_RE = re.compile(r"`/([a-z][a-z0-9-]*)`")
NAMED_SKILL_RE = re.compile(r"`([a-z][a-z0-9-]*)` toolbox skill")
CATALOG_SKILL_PATH_RE = re.compile(r"endaoment-toolbox/catalog/skills/([a-z0-9-]+)/")
# Where a repo keeps its own skills, each as <folder>/<name>/SKILL.md.
REPO_SKILL_FOLDERS = ("skills", ".cursor/skills", ".claude/skills", ".agents/skills")
# Commands a harness provides itself, so they are never toolbox skills. Each is
# listed in at least one of: code.claude.com/docs/en/commands (`/code-review`,
# `/loop` and `/simplify` are bundled skills there, and `/review` an alias),
# cursor.com/docs/cli/reference/slash-commands, and the Codex CLI slash commands.
HARNESS_COMMANDS = frozenset(
    {
        "agents", "clear", "code-review", "compact", "config", "context", "goal", "help", "hooks", "init",
        "loop", "mcp", "memory", "model", "permissions", "plan", "resume", "review", "security-review",
        "simplify", "skills", "status",
    }
)
# A name made only of these words, such as `skill-name` or `your-skill`, is a placeholder.
PLACEHOLDER_WORDS = frozenset({"skill", "name", "your", "my"})
GLOB_CHARS = frozenset("*?[")


class SourceError(Exception):
    """A catalog source could not be read. The message says why."""


# --- reading ---------------------------------------------------------------


def first_line(text: str | None) -> str:
    return (text or "").strip().split("\n")[0]


def git(cwd: str, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout


def read_text(root: str, rel: str) -> tuple[str | None, str | None]:
    """The file's text, or None and the violation that stopped the read."""
    try:
        with open(os.path.join(root, rel), encoding="utf-8") as handle:
            return handle.read(), None
    except FileNotFoundError:
        return None, f"{rel}: does not exist"
    except UnicodeDecodeError as error:
        return None, f"{rel}: is not UTF-8 text ({error.reason} at byte {error.start})"


def strip_fences(text: str) -> str:
    """The text without fenced code blocks; an unclosed fence runs to the end."""
    kept = []
    opener = None  # the open fence's indent and marker
    for line in text.splitlines(keepends=True):
        if opener:
            close = FENCE_CLOSE_RE.match(line.rstrip("\r\n"))
            indent, marker = opener
            if (
                close
                and close.group(2)[0] == marker[0]
                and len(close.group(2)) >= len(marker)
                and len(close.group(1)) <= len(indent) + 3
            ):
                opener = None
        else:
            fence = FENCE_OPEN_RE.match(line.rstrip("\r\n"))
            if fence:
                opener = (fence.group(1), fence.group(2))
            else:
                kept.append(line)
    return "".join(kept)


# --- entry checks ------------------------------------------------------------


def entry_file_violations(root: str, texts: dict) -> list[str]:
    """AGENTS.md is within the size bound, and CLAUDE.md imports it on line one."""
    violations = []
    if AGENTS_FILE in texts:
        size = os.path.getsize(os.path.join(root, AGENTS_FILE))
        if size > ENTRY_MAX_BYTES:
            violations.append(f"{AGENTS_FILE}: {size} bytes, over the {ENTRY_MAX_BYTES}-byte bound")
    if CLAUDE_FILE in texts:
        lines = texts[CLAUDE_FILE].splitlines()
        first = lines[0] if lines else ""
        if first != CLAUDE_IMPORT_LINE:
            violations.append(f"{CLAUDE_FILE}: first line must be `{CLAUDE_IMPORT_LINE}`, found {first!r}")
    return violations


def shared_rules_section(text: str) -> str | None:
    """The text under the Shared rules heading, up to the next heading at its level or above."""
    headings = list(HEADING_RE.finditer(text))
    for index, heading in enumerate(headings):
        if not SHARED_RULES_TITLE_RE.match(heading.group(2)):
            continue
        level = len(heading.group(1))
        end = next(
            (later.start() for later in headings[index + 1 :] if len(later.group(1)) <= level),
            len(text),
        )
        return text[heading.end() : end]
    return None


def shared_rules_violations(agents: str, always_on: list[str]) -> list[str]:
    """The Shared rules list items name exactly the snapshot's always-on rules."""
    # Comments and fenced examples are not the block, so neither can satisfy it.
    section = shared_rules_section(strip_fences(HTML_COMMENT_RE.sub("", agents)))
    if section is None:
        return [f"{AGENTS_FILE}: no `Shared rules` heading listing the always-on toolbox rules"]
    listed = {
        name
        for line in section.splitlines()
        if LIST_ITEM_RE.match(line)
        for name in SHARED_RULE_PATH_RE.findall(line)
    }
    expected = set(always_on)
    return [
        f"{AGENTS_FILE}: Shared rules is missing always-on rule `{name}`"
        for name in sorted(expected - listed)
    ] + [
        f"{AGENTS_FILE}: Shared rules lists `{name}`, which is not an always-on rule in the snapshot"
        for name in sorted(listed - expected)
    ]


def path_tokens(root: str, text: str) -> tuple[list[str], list[str]]:
    """The repo paths a file names: relative link targets, and backticked tokens that look like repo paths.

    The first-segment test skips per-project conventions such as
    `tests/test-context.ts`, code such as `try/finally`, branch patterns such as
    `rc/vX.Y.Z`, and other repos' paths such as `endaoment-fabric/...`.
    """
    links = [
        target
        for target in LINK_TARGET_RE.findall(CODE_SPAN_RE.sub("", text))
        if not URL_SCHEME_RE.match(target) and not target.startswith("/")
    ]
    backticked = [
        token
        for token in BACKTICK_TOKEN_RE.findall(text)
        if "/" in token
        and not token.startswith(("/", "./", "../"))
        and not NON_PATH_CHARS_RE.search(token)
        and os.path.exists(os.path.join(root, token.split("/")[0]))
    ]
    return list(dict.fromkeys(links)), list(dict.fromkeys(backticked))


def cited_skills(text: str) -> list[str]:
    """Toolbox skills a file names: a backticked `/name` on a line about skills, a
    "`name` toolbox skill", or a catalog skill path."""
    on_skill_lines = [
        name for line in text.splitlines() if SKILL_LINE_RE.search(line) for name in BACKTICKED_SKILL_RE.findall(line)
    ]
    return on_skill_lines + NAMED_SKILL_RE.findall(text) + CATALOG_SKILL_PATH_RE.findall(text)


def candidate_paths(root: str, rel: str, token: str, from_root: bool) -> list[str]:
    """Where a path a file names can live: beside the file, and from the repo root when from_root.

    A trailing slash stays, so a file cannot stand in for a folder and git can
    match a folder-only ignore pattern such as `dist/`.
    """
    slash = "/" if token.endswith("/") else ""
    bases = (os.path.dirname(rel), "") if from_root else (os.path.dirname(rel),)
    return [os.path.normpath(os.path.join(root, base, token)) + slash for base in bases]


def repo_skills(root: str) -> set[str]:
    """The skills this repo keeps itself: each <folder>/<name>/SKILL.md that git tracks.

    A toolbox install in the same folder is git-ignored, and a clean checkout in
    CI lacks it, so it must not pass here either. Outside a git clone, every
    SKILL.md on disk counts.
    """
    pattern = re.compile(
        r"^(?:%s)/([^/]+)/SKILL\.md$" % "|".join(re.escape(folder) for folder in REPO_SKILL_FOLDERS)
    )
    try:
        files = git(root, "ls-files", "-z", "--", *REPO_SKILL_FOLDERS).split("\0")
    except (OSError, subprocess.CalledProcessError):
        files = [
            f"{folder}/{name}/SKILL.md"
            for folder in REPO_SKILL_FOLDERS
            if os.path.isdir(os.path.join(root, folder))
            for name in os.listdir(os.path.join(root, folder))
            if os.path.isfile(os.path.join(root, folder, name, "SKILL.md"))
        ]
    return {match.group(1) for match in map(pattern.match, files) if match}


def is_known_skill(name: str, snapshot: dict, own_skills: set[str]) -> bool:
    """Whether a cited skill exists: in the toolbox snapshot, in this repo, or as a harness command.

    A placeholder name passes too, because it names no skill at all.
    """
    return (
        name in snapshot["skills"]
        or name in HARNESS_COMMANDS
        or set(name.split("-")) <= PLACEHOLDER_WORDS
        or name in own_skills
    )


def named_item_violations(
    root: str, rel: str, text: str, snapshot: dict, own_skills: set[str]
) -> tuple[list[str], list[tuple[str, str, list[str]]]]:
    """Unknown toolbox names in a file, and the paths it names that do not exist.

    The missing paths come back as (file, token, candidates) so one git call can
    excuse the ones git ignores as generated output.
    """
    violations = []
    missing = []
    links, backticked = path_tokens(root, text)
    # GitHub resolves a link from the file's folder; a backticked path may also mean the repo root.
    named = [(token, False) for token in links] + [(token, True) for token in backticked if token not in links]
    for token, from_root in named:
        candidates = candidate_paths(root, rel, token, from_root)
        if not any(os.path.exists(path) for path in candidates):
            missing.append((rel, token, candidates))
    for name in cited_skills(text):
        if not is_known_skill(name, snapshot, own_skills):
            violations.append(f"{rel}: skill `{name}` is not in the toolbox snapshot or this repo's skill folders")
    for name in TOOLBOX_RULE_NAME_RE.findall(text):
        if name not in snapshot["rules"]:
            violations.append(f"{rel}: toolbox rule `{name}` is not in the snapshot")
    return violations, missing


def ignore_excuses(pattern: str, path: str) -> bool:
    """Whether an ignore pattern that matched a missing path marks it as generated, not dead.

    A literal pattern (no glob, no `!`) names output a fresh clone may lack. So
    does `X/*` for the folder `X/` itself, the usual way to ignore generated rule
    copies. Any other glob, such as `*.md`, would excuse a typo.
    """
    if pattern.startswith("!"):
        return False
    if not GLOB_CHARS & set(pattern):
        return True
    folder = pattern[:-1]  # `X/` for `X/*`, so only the folder path itself ends with it
    return pattern.endswith("/*") and not GLOB_CHARS & set(folder) and path.endswith(folder.lstrip("/"))


def generated_paths(root: str, paths: list[str]) -> set[str]:
    """The repo-relative paths git ignores through a pattern that `ignore_excuses` accepts."""
    if not paths:
        return set()
    result = subprocess.run(
        ["git", "check-ignore", "--no-index", "--verbose", "-z", "--stdin"],
        cwd=root,
        input="\0".join(paths) + "\0",
        capture_output=True,
        text=True,
    )
    if result.returncode > 1:  # 1 means it ignores none of them
        sys.exit(f"git check-ignore failed: {result.stderr.strip()}")
    fields = result.stdout.split("\0")
    # -z -v prints source, line number, pattern, and path for each match.
    return {path for pattern, path in zip(fields[2::4], fields[3::4]) if ignore_excuses(pattern, path)}


def dead_path_violations(root: str, missing: list[tuple[str, str, list[str]]]) -> list[str]:
    def repo_relative(path: str) -> str | None:
        """The path from the repo root, or None outside the repo, where git cannot check it."""
        rel = os.path.relpath(path, root) + ("/" if path.endswith("/") else "")
        return None if rel.startswith("../") or rel == ".." else rel

    inside = {rel for _, _, candidates in missing for rel in map(repo_relative, candidates) if rel}
    ignored = generated_paths(root, sorted(inside))
    return [
        f"{rel}: `{token}` does not exist"
        for rel, token, candidates in missing
        if not any(repo_relative(path) in ignored for path in candidates)
    ]


def check_violations(root: str, snapshot: dict, files: list[str]) -> list[str]:
    """Every violation in the entry files and the extra instruction files, in order."""
    violations = []
    texts = {}
    for rel in files:
        text, problem = read_text(root, rel)
        if problem:
            violations.append(problem)
        else:
            texts[rel] = text
    violations += entry_file_violations(root, texts)
    if AGENTS_FILE in texts:
        violations += shared_rules_violations(texts[AGENTS_FILE], snapshot["alwaysOnRules"])
    missing = []
    own_skills = repo_skills(root)
    for rel, text in texts.items():
        found, missing_here = named_item_violations(root, rel, text, snapshot, own_skills)
        violations += found
        missing += missing_here
    violations += dead_path_violations(root, missing)
    return list(dict.fromkeys(violations))


# --- the toolbox catalog -----------------------------------------------------


def is_always_on(index_text: str) -> bool:
    frontmatter = FRONTMATTER_RE.match(index_text)
    return bool(frontmatter and ALWAYS_APPLY_RE.search(frontmatter.group(1)))


def to_catalog(ref: str, skills: list[str], rule_indexes: dict) -> dict:
    """A snapshot from the skill folder names and each rule folder's index.md text."""
    return {
        "source": TOOLBOX_REPO,
        "ref": ref,
        "skills": sorted(skills),
        "rules": sorted(rule_indexes),
        "alwaysOnRules": sorted(name for name, text in rule_indexes.items() if is_always_on(text)),
    }


def format_snapshot(catalog: dict) -> str:
    return json.dumps(catalog, indent=2) + "\n"


CATALOG_QUERY = """query($owner: String!, $name: String!, $commit: String!, $skills: String!, $rules: String!) {
  repository(owner: $owner, name: $name) {
    commit: object(expression: $commit) { oid }
    skills: object(expression: $skills) { ... on Tree { entries { name type } } }
    rules: object(expression: $rules) {
      ... on Tree { entries { name type object { ... on Tree { entries { name object { ... on Blob { text } } } } } } }
    }
  }
}"""


def run_gh(args: list[str], timeout: int) -> str:
    try:
        return subprocess.run(
            ["gh", *args], check=True, capture_output=True, text=True, timeout=timeout
        ).stdout
    except FileNotFoundError:
        raise SourceError("gh is not installed") from None
    except subprocess.TimeoutExpired:
        raise SourceError(f"gh {args[0]} timed out after {timeout}s") from None
    except subprocess.CalledProcessError as error:
        reason = first_line(error.stderr) or f"exit {error.returncode}"
        raise SourceError(f"gh {' '.join(args[:2])} failed: {reason}") from None


def github_catalog(ref: str) -> tuple[dict, str]:
    """The catalog on GitHub at ref (HEAD is the default branch), and where it came from."""
    run_gh(["auth", "status"], timeout=10)
    owner, name = TOOLBOX_REPO.split("/")
    response = run_gh(
        [
            "api", "graphql",
            "-f", f"query={CATALOG_QUERY}",
            "-f", f"owner={owner}",
            "-f", f"name={name}",
            "-f", f"commit={ref}",
            "-f", f"skills={ref}:catalog/skills",
            "-f", f"rules={ref}:catalog/rules",
        ],
        timeout=30,
    )
    try:
        repository = (json.loads(response).get("data") or {}).get("repository") or {}
    except json.JSONDecodeError:
        raise SourceError("gh api graphql returned a response that is not JSON") from None
    commit = repository.get("commit") or {}
    skills = (repository.get("skills") or {}).get("entries")
    rules = (repository.get("rules") or {}).get("entries")
    if not commit.get("oid"):
        raise SourceError(f"GitHub has no commit {ref} in {TOOLBOX_REPO}")
    if skills is None or rules is None:
        raise SourceError(f"GitHub has no catalog/skills and catalog/rules folders at {ref}")

    def index_text(rule: dict) -> str:
        files = (rule.get("object") or {}).get("entries") or []
        return next(((f.get("object") or {}).get("text") or "" for f in files if f["name"] == "index.md"), "")

    catalog = to_catalog(
        commit["oid"],
        [entry["name"] for entry in skills if entry["type"] == "tree"],
        {rule["name"]: index_text(rule) for rule in rules if rule["type"] == "tree"},
    )
    return catalog, f"github.com/{TOOLBOX_REPO}"


def clone_catalog(clone: str, ref: str) -> tuple[dict, str]:
    """The catalog at a commit of a toolbox clone, read from git so local edits do not leak in."""
    if not os.path.isdir(clone):
        raise SourceError(f"there is no toolbox clone at {clone}")
    try:
        sha = git(clone, "rev-parse", "--verify", f"{ref}^{{commit}}").strip()
    except subprocess.CalledProcessError as error:
        raise SourceError(f"could not read {ref} in {clone}: {first_line(error.stderr)}") from None
    try:
        skills = git(clone, "ls-tree", "-d", "--name-only", f"{sha}:catalog/skills").split()
        rules = git(clone, "ls-tree", "-d", "--name-only", f"{sha}:catalog/rules").split()
        rule_files = set(git(clone, "ls-tree", "-r", "--name-only", f"{sha}:catalog/rules").split())
    except subprocess.CalledProcessError:
        raise SourceError(f"{clone} has no catalog/skills and catalog/rules folders at {sha}") from None
    rule_indexes = {
        rule: git(clone, "cat-file", "blob", f"{sha}:catalog/rules/{rule}/index.md")
        if f"{rule}/index.md" in rule_files
        else ""
        for rule in rules
    }
    return to_catalog(sha, skills, rule_indexes), clone


def sibling_toolbox(root: str) -> str:
    """The endaoment-toolbox clone next to this repo's main clone, which a worktree finds too."""
    try:
        common_dir = git(root, "rev-parse", "--git-common-dir").strip()
    except subprocess.CalledProcessError:
        raise SourceError(f"{root} is not a git clone, so it has no sibling toolbox clone") from None
    main_clone = os.path.dirname(os.path.abspath(os.path.join(root, common_dir)))
    return os.path.join(os.path.dirname(main_clone), "endaoment-toolbox")


def live_catalog(readers: list[Callable[[], tuple[dict, str]]]) -> tuple[dict, str]:
    """The first source that reads. When none does, the error names every reason."""
    reasons = []
    for reader in readers:
        try:
            return reader()
        except SourceError as error:
            reasons.append(str(error))
    raise SourceError("; ".join(reasons))


def default_readers(root: str, ref: str) -> list[Callable[[], tuple[dict, str]]]:
    # GitHub first: a sibling clone can sit on an old commit or another branch.
    return [lambda: github_catalog(ref), lambda: clone_catalog(sibling_toolbox(root), ref)]


def catalog_drift(snapshot: dict, live: dict) -> list[str]:
    """How the live catalog's names differ from the snapshot's, one entry per list that changed."""
    drift = []
    for key in SNAPSHOT_LISTS:
        added = sorted(set(live[key]) - set(snapshot[key]))
        removed = sorted(set(snapshot[key]) - set(live[key]))
        if added:
            drift.append(f"{key} added: {', '.join(added)}")
        if removed:
            drift.append(f"{key} removed: {', '.join(removed)}")
    return drift


# --- commands ----------------------------------------------------------------


def load_snapshot(path: str) -> dict:
    """The snapshot, or exit with why it cannot be used."""
    try:
        with open(path, encoding="utf-8") as handle:
            snapshot = json.load(handle)
    except FileNotFoundError:
        sys.exit(f"{path}: does not exist. Run `refresh` to write it.")
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        sys.exit(f"{path}: is not a JSON toolbox snapshot ({error})")
    lacking = [key for key in ("ref", *SNAPSHOT_LISTS) if key not in snapshot]
    if lacking:
        sys.exit(f"{path}: is not a toolbox snapshot; it has no {', '.join(lacking)}")
    return snapshot


def run_check(root: str, snapshot_path: str, extras: list[str]) -> int:
    snapshot = load_snapshot(snapshot_path)
    files = list(dict.fromkeys([AGENTS_FILE, CLAUDE_FILE, *map(os.path.normpath, extras)]))
    violations = check_violations(root, snapshot, files)
    for violation in violations:
        print(violation, file=sys.stderr)

    live_note = ""
    if not os.environ.get("CI"):
        refresh = f"Run `python3 {os.path.relpath(__file__)} refresh` and commit the snapshot."
        try:
            live, source = live_catalog(default_readers(root, "HEAD"))
        except SourceError as error:
            print(f"warning: did not compare the snapshot with the live catalog: {error}", file=sys.stderr)
        else:
            drift = catalog_drift(snapshot, live)
            if drift:
                print(
                    f"warning: the live catalog at {source} ({live['ref'][:12]}) differs from the "
                    f"snapshot: {'; '.join(drift)}. {refresh}",
                    file=sys.stderr,
                )
            else:
                live_note = f" The snapshot matches {source} at {live['ref'][:12]}."

    if violations:
        return 1
    print(
        f"Agent entry files pass ({', '.join(files)}) against the committed toolbox snapshot "
        f"at {snapshot['ref']}.{live_note}"
    )
    return 0


def run_refresh(root: str, snapshot_path: str, clone: str | None, ref: str) -> int:
    readers = [lambda: clone_catalog(os.path.abspath(clone), ref)] if clone else default_readers(root, ref)
    try:
        catalog, source = live_catalog(readers)
    except SourceError as error:
        print(f"Could not read the toolbox catalog: {error}", file=sys.stderr)
        return 1
    with open(snapshot_path, "w", encoding="utf-8") as handle:
        handle.write(format_snapshot(catalog))
    print(
        f"Wrote {snapshot_path} from {source} at {catalog['ref']}: {len(catalog['skills'])} skills, "
        f"{len(catalog['rules'])} rules, {len(catalog['alwaysOnRules'])} always on."
    )
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Check the agent entry files, or refresh the toolbox snapshot.")
    parser.add_argument("command", nargs="?", choices=("check", "refresh"), default="check")
    parser.add_argument(
        "--snapshot",
        default=os.path.join(os.path.dirname(os.path.abspath(__file__)), SNAPSHOT_NAME),
        help=f"snapshot file (default: {SNAPSHOT_NAME} beside this script)",
    )
    parser.add_argument(
        "--extra",
        nargs="+",
        action="extend",
        default=[],
        metavar="FILE",
        help="check: more instruction files whose paths and names to check",
    )
    parser.add_argument("--clone", metavar="PATH", help="refresh: read this toolbox clone instead")
    parser.add_argument("--ref", default="HEAD", help="refresh: the toolbox commit to read (default: HEAD)")
    args = parser.parse_args(argv)
    root = os.getcwd()
    if args.command == "refresh":
        if args.extra:
            parser.error("--extra applies to check, not refresh")
        return run_refresh(root, args.snapshot, args.clone, args.ref)
    if args.clone or args.ref != "HEAD":
        parser.error("--clone and --ref apply to refresh, not check")
    return run_check(root, args.snapshot, args.extra)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
