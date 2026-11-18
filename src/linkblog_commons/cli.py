import argparse
import json
import sys
from typing import Any

from linkblog_commons.errors import LinkBlogError
from linkblog_commons.feed import generate_feed
from linkblog_commons.record import LinkPost
from linkblog_commons.render import hugo_render


def _build_render_parser(
    subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]",
) -> argparse.ArgumentParser:
    p = subparsers.add_parser("render", help="render a single link post to a Hugo content file")
    p.add_argument("--url", required=True)
    p.add_argument("--published", required=True)
    p.add_argument("--comment", default="")
    p.add_argument("--tag", action="append", default=None)
    p.add_argument("--output-dir", required=True)
    return p


def _build_feed_parser(
    subparsers: "argparse._SubParsersAction[argparse.ArgumentParser]",
) -> argparse.ArgumentParser:
    p = subparsers.add_parser("feed", help="generate an Atom feed from a JSON array of link posts")
    p.add_argument("--input", required=True, help="path to a JSON array file, or - to read stdin")
    p.add_argument("--output", required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--link", required=True)
    p.add_argument("--id", default=None)
    return p


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="linkblog_commons")
    subparsers = parser.add_subparsers(dest="command", required=True)
    _build_render_parser(subparsers)
    _build_feed_parser(subparsers)
    return parser


def _run_render(args: argparse.Namespace) -> dict[str, Any]:
    record = LinkPost(
        url=args.url,
        published=args.published,
        comment=args.comment or "",
        tags=tuple(args.tag or ()),
    )
    path = hugo_render(record, args.output_dir)
    return {"path": str(path), "filename": path.name}


def _run_feed(args: argparse.Namespace) -> dict[str, Any]:
    if args.input == "-":
        raw = sys.stdin.read()
    else:
        with open(args.input, encoding="utf-8") as f:
            raw = f.read()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LinkBlogError("invalid_json") from exc

    if not isinstance(data, list):
        raise LinkBlogError("invalid_json")

    records = [LinkPost.from_dict(item) for item in data]

    path = generate_feed(
        records,
        args.output,
        feed_title=args.title,
        feed_link=args.link,
        feed_id=args.id,
    )
    return {"path": str(path), "entry_count": len(records)}


def _envelope(status: str, result: dict[str, Any] | None, error: dict[str, Any] | None) -> str:
    return json.dumps(
        {
            "schema_version": 1,
            "status": status,
            "result": result,
            "error": error,
        }
    )


def _dispatch(args: argparse.Namespace) -> dict[str, Any]:
    if args.command == "render":
        return _run_render(args)
    if args.command == "feed":
        return _run_feed(args)
    raise LinkBlogError("internal_error")


def _emit(line: str) -> None:
    sys.stdout.write(line + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        result = _dispatch(args)
        _emit(_envelope("ok", result, None))
        return 0
    except LinkBlogError as e:
        _emit(_envelope("fail", None, {"code": e.code, "fields": list(e.fields)}))
        return 1
    except Exception:  # noqa: BLE001 -- a shell caller must never see a raw traceback on stdout
        _emit(_envelope("fail", None, {"code": "internal_error", "fields": []}))
        return 1
