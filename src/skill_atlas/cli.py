"""Command-line entry point for skill-atlas."""
from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable

from . import __version__
from .dedupe import dedupe
from .discovery import find_skill_files
from .models import Skill
from .output import (
    Painter, error, render_header, render_list, render_owner_header, render_owner_summary, render_skills,
    render_summary, use_color, warn,
)
from .parser import SkillParseError, parse_skill
from .repo import EmptyRepoError, RepoError, clone, github_owner_url, list_owner_repos, normalize_repo_url
from .store import Store, default_db_path


def scan_repo(
    url: str, ref: str | None = None, warn: Callable[[str], None] = warn,
) -> tuple[str, str, list[Skill]]:
    repo = normalize_repo_url(url)
    skills: list[Skill] = []
    with clone(repo, ref) as (root, commit):
        found = find_skill_files(root)
        for path in found.symlinks:
            warn(f"skipping {path.relative_to(root).as_posix()}: symlink")
        for path in found.files:
            rel = path.relative_to(root).as_posix()
            try:
                name, description, content = parse_skill(path)
            except (SkillParseError, OSError) as e:
                warn(f"skipping {rel}: {e}")
                continue
            skills.append(Skill(repo, name, description, commit, rel, content=content))
        skills = dedupe(skills, read=lambda rel: (root / rel).read_bytes(), warn=warn)
    return repo, commit, skills


def print_json(skills: list[Skill]) -> None:
    json.dump([s.to_dict() for s in skills], sys.stdout, indent=2, ensure_ascii=False)
    print()


def print_scan(repo: str, commit: str, skills: list[Skill], paint: Painter) -> None:
    print(render_header(repo, commit, paint))
    print()
    if skills:
        print(render_skills(skills, paint))
        print()
    print(render_summary(len(skills), paint))


def cmd_scan(args: argparse.Namespace) -> int:
    if owner := github_owner_url(args.repo):
        return scan_owner(owner, args)
    try:
        repo, commit, skills = scan_repo(args.repo, args.ref)
    except RepoError as e:
        error(str(e))
        return 1
    if not args.no_store:
        with Store(args.db) as store:
            store.replace_repo(repo, skills, commit)
    if args.json:
        print_json(skills)
        return 0
    print_scan(repo, commit, skills, Painter(use_color(args.color, sys.stdout)))
    return 0


def _scan_collecting(repo: str) -> tuple[str, str | None, list[Skill], list[str], str | None]:
    """``scan_repo()`` for one repository of an organization: warnings and the error are returned, not printed.

    An empty repository is a warning, not an error: it is skipped (``commit`` is None, no error).
    """
    warnings: list[str] = []
    try:
        _, commit, skills = scan_repo(repo, warn=warnings.append)
    except EmptyRepoError as e:
        return repo, None, [], [*warnings, f"skipping: {e}"], None
    except RepoError as e:
        return repo, None, [], warnings, str(e)
    return repo, commit, skills, warnings, None


def scan_owner(owner: str, args: argparse.Namespace) -> int:
    """``scan`` for an organization or user URL: scan every repository (see spec/cli.md)."""
    if args.ref:
        error("--ref can't be used with an organization URL")
        return 2
    try:
        repos, forks = list_owner_repos(owner, include_forks=args.include_forks)
    except RepoError as e:
        error(str(e))
        return 1
    paint = Painter(use_color(args.color, sys.stdout))
    if not args.json:
        print(render_owner_header(owner, len(repos), forks, paint), flush=True)
    found: list[Skill] = []
    with_skills = failed = 0
    store = None if args.no_store else Store(args.db)
    try:
        with ThreadPoolExecutor(max_workers=args.jobs) as pool:
            # map() yields in submission order, so output is in name order whatever finishes first;
            # if the loop is interrupted (Ctrl-C), map() cancels the repositories still queued
            for repo, commit, skills, warnings, err in pool.map(_scan_collecting, repos):
                for msg in warnings:
                    warn(f"{repo}: {msg}")
                if err is not None:
                    error(f"{repo}: {err}")
                    failed += 1
                    continue
                if commit is None:  # empty repository
                    continue
                if store:
                    store.replace_repo(repo, skills, commit)
                if not skills:
                    continue
                with_skills += 1
                found += skills
                if not args.json:
                    print()
                    print_scan(repo, commit, skills, paint)
                    sys.stdout.flush()
    finally:
        if store:
            store.close()
    if args.json:
        print_json(found)
    else:
        print()
        print(render_owner_summary(len(found), with_skills, len(repos), failed, paint))
    return 1 if failed else 0


def cmd_list(args: argparse.Namespace) -> int:
    repo = normalize_repo_url(args.repo) if args.repo else None
    with Store(args.db) as store:
        skills = store.list(repo)
    if args.json:
        print_json(skills)
    else:
        print(render_list(skills, Painter(use_color(args.color, sys.stdout))))
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    from .web import make_server

    server = make_server(
        args.host, args.port, args.db, store=not args.no_store, allow_local=args.allow_local,
    )
    host, port = server.server_address[:2]
    print(f"skill-atlas web UI on http://{host}:{port}/", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


def _positive_int(value: str) -> int:
    n = int(value)
    if n < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return n


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="skill-atlas", description=__doc__)
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true", help="output JSON")
    common.add_argument(
        "--color", choices=("auto", "always", "never"), default="auto",
        help="colorize output (default: auto — only on a terminal, disabled by NO_COLOR)",
    )
    common.add_argument(
        "--db", type=Path, default=None,
        help="SQLite database path (default: $SKILL_ATLAS_DB or ~/.skill-atlas/atlas.db)",
    )

    scan = sub.add_parser("scan", parents=[common], help="list and store skills of a repository")
    scan.add_argument(
        "repo",
        help="repository URL, e.g. https://github.com/owner/name, or an organization/user URL "
        "(https://github.com/owner) to scan all its repositories",
    )
    scan.add_argument("--ref", help="branch or tag to scan (default: repository default branch)")
    scan.add_argument("--no-store", action="store_true", help="do not write results to the database")
    scan.add_argument(
        "--include-forks", action="store_true", help="organization URL: also scan the owner's forks",
    )
    scan.add_argument(
        "--jobs", type=_positive_int, default=4, metavar="N",
        help="organization URL: clone up to N repositories at once (default: 4)",
    )
    scan.set_defaults(func=cmd_scan)

    ls = sub.add_parser("list", parents=[common], help="list skills stored in the database")
    ls.add_argument("--repo", help="only show skills of this repository")
    ls.set_defaults(func=cmd_list)

    serve = sub.add_parser("serve", help="run the web UI (see spec/web.md)")
    serve.add_argument("--host", default="127.0.0.1", help="address to bind (default: 127.0.0.1)")
    serve.add_argument("--port", type=int, default=8000, help="port to bind (default: 8000)")
    serve.add_argument(
        "--db", type=Path, default=None,
        help="SQLite database path (default: $SKILL_ATLAS_DB or ~/.skill-atlas/atlas.db)",
    )
    serve.add_argument("--no-store", action="store_true", help="do not write results to the database")
    serve.add_argument(
        "--allow-local", action="store_true",
        help="also accept non-https:// repository URLs such as file:// (unsafe on a shared host)",
    )
    serve.set_defaults(func=cmd_serve)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.db is None:
        args.db = default_db_path()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
