import os
import sys
import tempfile
import importlib
import types

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_knowledge_store_add_and_search(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        monkeypatch.setenv("CLINIMETRIA_WORKSPACE_DIR", tmpdir)
        import app.modules.knowledge_store as ks
        importlib.reload(ks)

        payload = ks.add_document(
            file_bytes=b"Clinical statistics guide. t-test and ANOVA usage.",
            filename="guide.txt",
            title="Stats Guide",
            tags=["stat"],
        )
        doc_id = payload.get("id")
        assert doc_id

        results = ks.search_documents("t-test", top_k=3)
        assert results
        assert results[0].get("doc_id") == doc_id

        doc = ks.get_document(doc_id)
        assert doc
        assert doc.get("title") == "Stats Guide"
        library = ks.list_documents()
        assert library and library[0].get("source_type") == "txt"


def test_knowledge_store_pdf_limits_chars_and_bytes(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        monkeypatch.setenv("CLINIMETRIA_WORKSPACE_DIR", tmpdir)
        monkeypatch.setenv("CLINIMETRIA_KB_PDF_MAX_PAGES", "0")
        monkeypatch.setenv("CLINIMETRIA_KB_PDF_MAX_CHARS_PER_FILE", "60")
        monkeypatch.setenv("CLINIMETRIA_KB_PDF_MAX_BYTES_PER_FILE", "100")

        import app.modules.knowledge_store as ks
        importlib.reload(ks)

        class _Page:
            def __init__(self, text):
                self._text = text

            def extract_text(self):
                return self._text

        class _PdfCtx:
            def __init__(self, pages):
                self.pages = pages

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        fake_pdf = types.SimpleNamespace(
            open=lambda _path: _PdfCtx([_Page("A" * 80), _Page("B" * 80), _Page("C" * 80)])
        )
        monkeypatch.setitem(sys.modules, "pdfplumber", fake_pdf)

        pdf_path = os.path.join(tmpdir, "big.pdf")
        with open(pdf_path, "wb") as f:
            f.write(b"x" * 512)

        text, warnings = ks._extract_text(pdf_path)
        assert len(text) <= 60
        assert "pdf_truncated_chars" in warnings
        assert "pdf_truncated_bytes" in warnings
        assert any(str(w).startswith("pdf_pages_read:") for w in warnings)
        assert any(str(w).startswith("pdf_chars_extracted:") for w in warnings)
        assert any(str(w).startswith("pdf_truncated_reason:") for w in warnings)


def test_knowledge_store_pdf_page_limit_applies(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        monkeypatch.setenv("CLINIMETRIA_WORKSPACE_DIR", tmpdir)
        monkeypatch.setenv("CLINIMETRIA_KB_PDF_MAX_PAGES", "1")
        monkeypatch.setenv("CLINIMETRIA_KB_PDF_MAX_CHARS_PER_FILE", "10000")
        monkeypatch.setenv("CLINIMETRIA_KB_PDF_MAX_BYTES_PER_FILE", "0")

        import app.modules.knowledge_store as ks
        importlib.reload(ks)

        class _Page:
            def __init__(self, text):
                self._text = text

            def extract_text(self):
                return self._text

        class _PdfCtx:
            def __init__(self, pages):
                self.pages = pages

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        fake_pdf = types.SimpleNamespace(
            open=lambda _path: _PdfCtx([_Page("P1"), _Page("P2"), _Page("P3")])
        )
        monkeypatch.setitem(sys.modules, "pdfplumber", fake_pdf)

        pdf_path = os.path.join(tmpdir, "sample.pdf")
        with open(pdf_path, "wb") as f:
            f.write(b"pdf")

        text, warnings = ks._extract_text(pdf_path)
        assert "P1" in text
        assert "P2" not in text
        assert "pdf_truncated_pages" in warnings


def test_knowledge_store_pdf_hard_char_cap_when_soft_limits_disabled(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        monkeypatch.setenv("CLINIMETRIA_WORKSPACE_DIR", tmpdir)
        monkeypatch.setenv("CLINIMETRIA_KB_PDF_MAX_PAGES", "0")
        monkeypatch.setenv("CLINIMETRIA_KB_PDF_MAX_CHARS_PER_FILE", "0")
        monkeypatch.setenv("CLINIMETRIA_KB_PDF_MAX_BYTES_PER_FILE", "0")
        monkeypatch.setenv("CLINIMETRIA_KB_PDF_HARD_MAX_CHARS_PER_FILE", "50")

        import app.modules.knowledge_store as ks
        importlib.reload(ks)

        class _Page:
            def __init__(self, text):
                self._text = text

            def extract_text(self):
                return self._text

        class _PdfCtx:
            def __init__(self, pages):
                self.pages = pages

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        fake_pdf = types.SimpleNamespace(
            open=lambda _path: _PdfCtx([_Page("A" * 80), _Page("B" * 80), _Page("C" * 80)])
        )
        monkeypatch.setitem(sys.modules, "pdfplumber", fake_pdf)

        pdf_path = os.path.join(tmpdir, "unbounded.pdf")
        with open(pdf_path, "wb") as f:
            f.write(b"x")

        text, warnings = ks._extract_text(pdf_path)
        assert len(text) <= 50
        assert "pdf_chars_limit_fallback" in warnings
        assert "pdf_truncated_chars" in warnings
