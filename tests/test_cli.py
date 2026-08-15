"""Tests for linkblog_commons.cli: CLI output and exit-code behavior.

Two-tier pattern (mirrors feed-commons/tests/test_cli.py):

- In-process tests call main() directly in this same process and capture
  stdout via capsys. These are cheap and exercise the real parse -> render/
  feed -> JSON-envelope pipeline.
- Subprocess tests spawn a genuinely separate `python -m linkblog_commons`
  process to prove the __main__.py wiring, stdin handling, and process-level
  exit codes all work outside of pytest's own process. They resolve the
  interpreter via sys.executable rather than a __file__-relative venv path —
  sys.executable is guaranteed to be whatever interpreter is actually
  running this test process, which stays correct even when the test file
  runs from a sandboxed/copied location (e.g. mutation-testing tools that
  copy the source tree elsewhere before running pytest against it).
"""

from __future__ import annotations

import io
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from linkblog_commons import hugo_render
from linkblog_commons.cli import main
from linkblog_commons.record import LinkPost

REPO_ROOT = Path(__file__).resolve().parent.parent
VENV_PYTHON = sys.executable


# --- In-process: render ------------------------------------------------------


def test_main_render_prints_ok_envelope_and_returns_zero(tmp_path, capsys):
    exit_code = main(
        [
            "render",
            "--url",
            "http://x.com",
            "--published",
            "2026-08-15T10:00:00+00:00",
            "--output-dir",
            str(tmp_path),
        ]
    )

    assert exit_code == 0

    envelope = json.loads(capsys.readouterr().out.strip())
    assert envelope["schema_version"] == 1
    assert envelope["status"] == "ok"
    assert envelope["error"] is None
    assert isinstance(envelope["result"], dict)
    assert "path" in envelope["result"]
    assert "filename" in envelope["result"]
    assert Path(envelope["result"]["path"]).exists()


def test_main_render_passes_comment_and_tags_through_to_output(tmp_path, capsys):
    exit_code = main(
        [
            "render",
            "--url",
            "http://x.com",
            "--published",
            "2026-08-15T10:00:00+00:00",
            "--comment",
            "hello from the CLI",
            "--tag",
            "a",
            "--tag",
            "b",
            "--output-dir",
            str(tmp_path),
        ]
    )

    assert exit_code == 0
    envelope = json.loads(capsys.readouterr().out.strip())
    written = Path(envelope["result"]["path"]).read_text(encoding="utf-8")
    assert "hello from the CLI" in written
    assert '"a"' in written
    assert '"b"' in written


def test_main_render_missing_required_arg_exits_two(tmp_path, capsys):
    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "render",
                "--published",
                "2026-08-15T10:00:00+00:00",
                "--output-dir",
                str(tmp_path),
            ]
        )
    assert exc_info.value.code == 2


def test_main_render_omitted_comment_defaults_to_empty_body(tmp_path, capsys):
    exit_code = main(
        [
            "render",
            "--url",
            "http://x.com",
            "--published",
            "2026-08-15T10:00:00+00:00",
            "--output-dir",
            str(tmp_path),
        ]
    )

    assert exit_code == 0
    envelope = json.loads(capsys.readouterr().out.strip())
    written = Path(envelope["result"]["path"]).read_text(encoding="utf-8")
    assert written.endswith("---\n")


def test_main_no_subcommand_exits_two():
    with pytest.raises(SystemExit) as exc_info:
        main([])
    assert exc_info.value.code == 2


RENDER_ARGS = [
    "--url",
    "http://x.com",
    "--published",
    "2026-08-15T10:00:00+00:00",
    "--output-dir",
    ".",
]


@pytest.mark.parametrize("dropped_flag", ["--url", "--published", "--output-dir"])
def test_main_render_missing_any_required_arg_exits_two(dropped_flag):
    args = list(RENDER_ARGS)
    idx = args.index(dropped_flag)
    del args[idx : idx + 2]

    with pytest.raises(SystemExit) as exc_info:
        main(["render", *args])
    assert exc_info.value.code == 2


FEED_ARGS = [
    "--input",
    "some_input.json",
    "--output",
    "some_output.xml",
    "--title",
    "Test",
    "--link",
    "http://example.com",
]


@pytest.mark.parametrize(
    "dropped_flag", ["--input", "--output", "--title", "--link"]
)
def test_main_feed_missing_any_required_arg_exits_two(dropped_flag):
    args = list(FEED_ARGS)
    idx = args.index(dropped_flag)
    del args[idx : idx + 2]

    with pytest.raises(SystemExit) as exc_info:
        main(["feed", *args])
    assert exc_info.value.code == 2


# --- In-process: feed --------------------------------------------------------


def test_main_feed_prints_ok_envelope_and_returns_zero(tmp_path, capsys):
    input_path = tmp_path / "records.json"
    input_path.write_text(
        json.dumps(
            [
                {
                    "url": "http://x.com",
                    "published": "2026-08-15T10:00:00+00:00",
                    "comment": "hello",
                    "tags": ["a", "b"],
                }
            ]
        ),
        encoding="utf-8",
    )
    output_path = tmp_path / "feed.xml"

    exit_code = main(
        [
            "feed",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
            "--title",
            "Test",
            "--link",
            "http://example.com",
        ]
    )

    assert exit_code == 0

    envelope = json.loads(capsys.readouterr().out.strip())
    assert envelope["schema_version"] == 1
    assert envelope["status"] == "ok"
    assert envelope["error"] is None
    assert isinstance(envelope["result"], dict)
    assert "path" in envelope["result"]
    assert envelope["result"]["path"] == str(output_path)
    assert envelope["result"]["entry_count"] == 1
    assert output_path.exists()


def test_main_feed_with_id_flag_sets_feed_id(tmp_path, capsys):
    input_path = tmp_path / "records.json"
    input_path.write_text(
        json.dumps(
            [{"url": "http://x.com", "published": "2026-08-15T10:00:00+00:00"}]
        ),
        encoding="utf-8",
    )
    output_path = tmp_path / "feed.xml"

    exit_code = main(
        [
            "feed",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
            "--title",
            "Test",
            "--link",
            "http://example.com",
            "--id",
            "urn:custom-feed-id",
        ]
    )

    assert exit_code == 0
    capsys.readouterr()
    tree = ET.parse(output_path)
    id_el = tree.getroot().find("{http://www.w3.org/2005/Atom}id")
    assert id_el is not None
    assert id_el.text == "urn:custom-feed-id"


def test_main_feed_stdin_input_in_process(tmp_path, capsys, monkeypatch):
    records = json.dumps(
        [{"url": "http://x.com", "published": "2026-08-15T10:00:00+00:00"}]
    )
    monkeypatch.setattr(sys, "stdin", io.StringIO(records))
    output_path = tmp_path / "feed.xml"

    exit_code = main(
        [
            "feed",
            "--input",
            "-",
            "--output",
            str(output_path),
            "--title",
            "Test",
            "--link",
            "http://example.com",
        ]
    )

    assert exit_code == 0
    envelope = json.loads(capsys.readouterr().out.strip())
    assert envelope["status"] == "ok"
    assert envelope["result"]["entry_count"] == 1
    assert output_path.exists()


def test_main_feed_invalid_json_input_maps_to_invalid_json_error(tmp_path, capsys):
    input_path = tmp_path / "bad.json"
    input_path.write_text("not valid json {{{", encoding="utf-8")
    output_path = tmp_path / "feed.xml"

    exit_code = main(
        [
            "feed",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
            "--title",
            "Test",
            "--link",
            "http://example.com",
        ]
    )

    assert exit_code == 1
    envelope = json.loads(capsys.readouterr().out.strip())
    assert envelope["status"] == "fail"
    assert envelope["error"]["code"] == "invalid_json"


def test_main_feed_non_list_json_input_maps_to_invalid_json_error(tmp_path, capsys):
    input_path = tmp_path / "not_a_list.json"
    input_path.write_text(json.dumps({"url": "http://x.com"}), encoding="utf-8")
    output_path = tmp_path / "feed.xml"

    exit_code = main(
        [
            "feed",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
            "--title",
            "Test",
            "--link",
            "http://example.com",
        ]
    )

    assert exit_code == 1
    envelope = json.loads(capsys.readouterr().out.strip())
    assert envelope["status"] == "fail"
    assert envelope["error"]["code"] == "invalid_json"


# --- In-process: failure path -------------------------------------------------


def test_main_render_empty_url_prints_fail_envelope_and_returns_one(tmp_path, capsys):
    exit_code = main(
        [
            "render",
            "--url",
            "",
            "--published",
            "2026-08-15T10:00:00+00:00",
            "--output-dir",
            str(tmp_path),
        ]
    )

    assert exit_code == 1

    envelope = json.loads(capsys.readouterr().out.strip())
    assert envelope["schema_version"] == 1
    assert envelope["status"] == "fail"
    assert envelope["result"] is None
    assert envelope["error"]["code"] == "missing_fields"
    assert envelope["error"]["fields"] == ["url"]


def test_main_unanticipated_exception_maps_to_internal_error(tmp_path, capsys, monkeypatch):
    def _boom(record, output_dir):
        raise RuntimeError("something no LinkBlogError branch expects")

    monkeypatch.setattr("linkblog_commons.cli.hugo_render", _boom)

    exit_code = main(
        [
            "render",
            "--url",
            "http://x.com",
            "--published",
            "2026-08-15T10:00:00+00:00",
            "--output-dir",
            str(tmp_path),
        ]
    )

    assert exit_code == 1
    envelope = json.loads(capsys.readouterr().out.strip())
    assert envelope == {
        "schema_version": 1,
        "status": "fail",
        "result": None,
        "error": {"code": "internal_error", "fields": []},
    }


# --- Subprocess: stdin feed ---------------------------------------------------


def test_subprocess_feed_reads_from_stdin(tmp_path):
    output_path = tmp_path / "feed2.xml"
    records = json.dumps(
        [
            {
                "url": "http://x.com",
                "published": "2026-08-15T10:00:00+00:00",
                "comment": "hi",
                "tags": [],
            }
        ]
    )

    result = subprocess.run(
        [
            str(VENV_PYTHON),
            "-m",
            "linkblog_commons",
            "feed",
            "--input",
            "-",
            "--output",
            str(output_path),
            "--title",
            "T",
            "--link",
            "http://x.com",
        ],
        input=records,
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        check=False,
    )

    assert result.returncode == 0, result.stderr

    envelope = json.loads(result.stdout.strip())
    assert envelope["schema_version"] == 1
    assert envelope["status"] == "ok"
    assert output_path.exists()


# --- Subprocess parity: byte-for-byte identical rendered file ----------------


def test_render_output_byte_for_byte_identical_in_process_vs_subprocess(tmp_path):
    url = "http://x.com"
    published = "2026-08-15T10:00:00+00:00"
    comment = "hello world"

    direct_dir = tmp_path / "direct"
    direct_dir.mkdir()
    subprocess_dir = tmp_path / "subprocess"
    subprocess_dir.mkdir()

    record = LinkPost(url=url, published=published, comment=comment, tags=("a", "b"))
    direct_path = hugo_render(record, direct_dir)

    result = subprocess.run(
        [
            str(VENV_PYTHON),
            "-m",
            "linkblog_commons",
            "render",
            "--url",
            url,
            "--published",
            published,
            "--comment",
            comment,
            "--tag",
            "a",
            "--tag",
            "b",
            "--output-dir",
            str(subprocess_dir),
        ],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        check=False,
    )

    assert result.returncode == 0, result.stderr
    envelope = json.loads(result.stdout.strip())
    assert envelope["status"] == "ok"
    subprocess_path = Path(envelope["result"]["path"])

    assert direct_path.read_bytes() == subprocess_path.read_bytes()


# --- Subprocess: --help -------------------------------------------------------


def test_subprocess_help_exits_zero_and_prints_usage():
    result = subprocess.run(
        [str(VENV_PYTHON), "-m", "linkblog_commons", "--help"],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        check=False,
    )

    assert result.returncode == 0
    assert "usage" in result.stdout.lower()
    assert "Traceback" not in result.stdout
    assert "Traceback" not in result.stderr
