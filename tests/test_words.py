"""Word count, manuscript compile, and explicit snapshots.

Real embedded Postgres. No mocks.
"""

from test_invariants import add_block, add_document, add_section, init_work, run

from littera.cli.words import count_words, visible_text


def test_visible_text_strips_mention_markup():
    raw = "Hello {@Ada|entity:aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa} Lovelace"
    assert visible_text(raw) == "Hello Ada Lovelace"
    assert count_words(raw) == 3


def test_visible_text_strips_markdown_lightly():
    raw = "A **bold** and [linked](https://example.com) word"
    assert count_words(raw) == 5


def test_wc_and_status_agree(tmp_path):
    with init_work(tmp_path) as workdir:
        add_document(workdir, "Ch1")
        add_section(workdir, "Scene")
        add_block(workdir, "One two three four")

        wc = run("littera wc", cwd=workdir)
        assert wc.returncode == 0, wc.stderr
        assert "4 words" in wc.stdout
        assert "work" in wc.stdout

        status = run("littera status", cwd=workdir)
        assert status.returncode == 0, status.stderr
        assert "Words:" in status.stdout
        assert "4" in status.stdout


def test_wc_document_and_section_scope(tmp_path):
    with init_work(tmp_path) as workdir:
        add_document(workdir, "Ch1")
        add_section(workdir, "A")
        add_block(workdir, "alpha beta")
        run("littera doc add 'Ch2'", cwd=workdir)
        run("littera section add 2 'B'", cwd=workdir)
        run("littera block add 2 'gamma delta epsilon'", cwd=workdir)

        work = run("littera wc", cwd=workdir)
        assert work.returncode == 0, work.stderr
        assert "5 words" in work.stdout

        doc1 = run("littera wc --document 1", cwd=workdir)
        assert doc1.returncode == 0, doc1.stderr
        assert "2 words" in doc1.stdout
        assert "Ch1" in doc1.stdout

        sec2 = run("littera wc --section 2", cwd=workdir)
        assert sec2.returncode == 0, sec2.stderr
        assert "3 words" in sec2.stdout


def test_wc_counts_mention_label_only(tmp_path):
    mention = "{@Ada|entity:aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa}"
    with init_work(tmp_path) as workdir:
        add_document(workdir)
        add_section(workdir)
        add_block(workdir, f"Hello {mention} here")

        res = run("littera wc", cwd=workdir)
        assert res.returncode == 0, res.stderr
        assert "3 words" in res.stdout


def test_export_markdown_default_is_labeled_dump(tmp_path):
    with init_work(tmp_path) as workdir:
        add_document(workdir, "Chapter One")
        add_section(workdir, "Opening")
        add_block(workdir, "Once upon a time")

        res = run("littera export markdown", cwd=workdir)
        assert res.returncode == 0, res.stderr
        assert "## Document: Chapter One" in res.stdout
        assert "[en] Once upon a time" in res.stdout


def test_export_markdown_compile_is_chapter_joined(tmp_path):
    mention = "{@Ada|entity:aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa}"
    with init_work(tmp_path) as workdir:
        add_document(workdir, "Chapter One")
        add_section(workdir, "Opening")
        add_block(workdir, "Once " + mention + " wrote")

        dest = tmp_path / "manuscript.md"
        res = run(f"littera export markdown --compile -o {dest}", cwd=workdir)
        assert res.returncode == 0, res.stderr
        text = dest.read_text(encoding="utf-8")
        assert "## Document:" not in text
        assert "[en]" not in text
        assert "## Chapter One" in text
        assert "### Opening" in text
        assert "Once Ada wrote" in text
        assert mention not in text


def test_snapshot_writes_json_under_littera(tmp_path):
    with init_work(tmp_path) as workdir:
        add_document(workdir, "Snap")
        add_section(workdir)
        add_block(workdir, "Keep this")

        res = run("littera snapshot --name draft", cwd=workdir)
        assert res.returncode == 0, res.stderr
        assert "Snapshot written" in res.stdout

        snap_dir = workdir / ".littera" / "snapshots"
        files = list(snap_dir.glob("*-draft.json"))
        assert len(files) == 1
        data = files[0].read_text(encoding="utf-8")
        assert "littera_version" in data
        assert "Keep this" in data
        assert "Snap" in data
