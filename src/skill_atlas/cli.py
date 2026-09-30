"""Command-line entry point for skill-atlas."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Callable

from . import __version__
from .dedupe import dedupe
from .discovery import find_skill_files
from .models import Skill
from .output import Painter, error, render_header, render_list, render_skills, render_summary, use_color, warn
from .parser import SkillParseError, parse_skill
from .repo import RepoError, clone, normalize_repo_url
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
                name, description = parse_skill(path)
            except (SkillParseError, OSError) as e:
                warn(f"skipping {rel}: {e}")
                continue
            skills.append(Skill(repo, name, description, commit, rel))
        skills = dedupe(skills, read=lambda rel: (root / rel).read_bytes(), warn=warn)
    return repo, commit, skills


def print_json(skills: list[Skill]) -> None:
    json.dump([s.to_dict() for s in skills], sys.stdout, indent=2, ensure_ascii=False)
    print()


def cmd_scan(args: argparse.Namespace) -> int:
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
    paint = Painter(use_color(args.color, sys.stdout))
    print(render_header(repo, commit, paint))
    print()
    if skills:
        print(render_skills(skills, paint))
        print()
    print(render_summary(len(skills), paint))
    return 0


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
    scan.add_argument("repo", help="repository URL, e.g. https://github.com/owner/name")
    scan.add_argument("--ref", help="branch or tag to scan (default: repository default branch)")
    scan.add_argument("--no-store", action="store_true", help="do not write results to the database")
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
