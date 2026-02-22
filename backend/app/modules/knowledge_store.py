import json
import os
import re
import tempfile
import uuid
from datetime import datetime
from io import StringIO
from typing import Any, Dict, List, Optional, Tuple

from app.core.logging import logger
from app.core.paths import get_workspace_dir, get_knowledge_dir


WORKSPACE_DIR = get_workspace_dir()
KNOWLEDGE_DIR = get_knowledge_dir()
UPLOADS_DIR = os.path.join(KNOWLEDGE_DIR, "uploads")
DOCS_DIR = os.path.join(KNOWLEDGE_DIR, "docs")
INDEX_PATH = os.path.join(KNOWLEDGE_DIR, "index.json")


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return int(default)
    try:
        return int(str(raw).strip())
    except Exception:
        return int(default)


MAX_PDF_PAGES = _env_int("CLINIMETRIA_KB_PDF_MAX_PAGES", 0)
MAX_PDF_CHARS_PER_FILE = _env_int("CLINIMETRIA_KB_PDF_MAX_CHARS_PER_FILE", 2_000_000)
MAX_PDF_BYTES_PER_FILE = _env_int("CLINIMETRIA_KB_PDF_MAX_BYTES_PER_FILE", 30_000_000)
PDF_HARD_CHAR_CAP = _env_int("CLINIMETRIA_KB_PDF_HARD_MAX_CHARS_PER_FILE", 5_000_000)

_STOPWORDS_EN = {
    "the", "and", "or", "of", "for", "to", "in", "on", "with", "without", "by", "from",
    "a", "an", "is", "are", "was", "were", "be", "been", "this", "that", "these", "those",
    "as", "at", "it", "its", "if", "then", "than", "into", "about", "between", "within",
    "using", "used", "use", "can", "may", "might", "should", "could", "will", "would",
}

_STOPWORDS_RU = {
    "и", "или", "но", "а", "на", "в", "во", "к", "ко", "из", "по", "для", "при", "без",
    "что", "это", "эти", "этом", "этот", "эта", "этих", "как", "так", "также", "есть",
    "бы", "же", "ли", "не", "да", "нет", "или", "то", "мы", "вы", "они", "он", "она",
    "оно", "их", "его", "ее", "у", "от", "до", "над", "под", "между", "если", "тогда",
}


def _utc_iso() -> str:
    return datetime.utcnow().isoformat()


def _ensure_dirs() -> None:
    os.makedirs(UPLOADS_DIR, exist_ok=True)
    os.makedirs(DOCS_DIR, exist_ok=True)


def _atomic_write_bytes(path: str, data: bytes) -> None:
    parent = os.path.dirname(path)
    os.makedirs(parent, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix=".tmp_", dir=parent)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    finally:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass


def _atomic_write_json(path: str, payload: Dict[str, Any]) -> None:
    data = json.dumps(payload, ensure_ascii=False, indent=2, default=str).encode("utf-8")
    _atomic_write_bytes(path, data)


def _load_index() -> Dict[str, Any]:
    _ensure_dirs()
    if not os.path.exists(INDEX_PATH):
        return {"version": 1, "updated_at": _utc_iso(), "docs": []}
    try:
        with open(INDEX_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and isinstance(data.get("docs"), list):
            return data
    except Exception:
        pass
    return {"version": 1, "updated_at": _utc_iso(), "docs": []}


def _save_index(index: Dict[str, Any]) -> None:
    index = index if isinstance(index, dict) else {}
    index["version"] = index.get("version") or 1
    index["updated_at"] = _utc_iso()
    index.setdefault("docs", [])
    _atomic_write_json(INDEX_PATH, index)


def _clean_text(text: str, max_chars: int = 2_000_000) -> str:
    if not text:
        return ""
    cleaned = text.replace("\r\n", "\n").replace("\r", "\n")
    if len(cleaned) > max_chars:
        cleaned = cleaned[:max_chars]
    return cleaned


def _extract_keywords(text: str, top_k: int = 20) -> List[str]:
    if not text:
        return []
    text = text.lower()
    text = re.sub(r"[^0-9a-zа-яё]+", " ", text, flags=re.IGNORECASE)
    tokens = [t for t in text.split() if len(t) >= 3]
    if not tokens:
        return []
    freq: Dict[str, int] = {}
    for tok in tokens:
        if tok in _STOPWORDS_EN or tok in _STOPWORDS_RU:
            continue
        freq[tok] = freq.get(tok, 0) + 1
    if not freq:
        return []
    sorted_tokens = sorted(freq.items(), key=lambda x: (-x[1], x[0]))
    return [t for t, _ in sorted_tokens[:max(5, int(top_k))]]


def _tokenize(text: str) -> List[str]:
    if not text:
        return []
    text = text.lower()
    text = re.sub(r"[^0-9a-zа-яё]+", " ", text, flags=re.IGNORECASE)
    toks = [t for t in text.split() if len(t) >= 3]
    return [t for t in toks if t not in _STOPWORDS_EN and t not in _STOPWORDS_RU]


def route_documents(query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    q = str(query or "").strip()
    if not q:
        return []
    tokens = set(_tokenize(q))
    if not tokens:
        return []

    results: List[Tuple[float, Dict[str, Any]]] = []
    for doc in list_documents():
        title = str(doc.get("title") or doc.get("filename") or "")
        tags = doc.get("tags") if isinstance(doc.get("tags"), list) else []
        keywords = doc.get("keywords") if isinstance(doc.get("keywords"), list) else []
        preview = doc.get("preview")
        title_l = title.lower()
        score = 0.0
        for tok in tokens:
            if tok in title_l:
                score += 3.0
            if any(tok in str(t).lower() for t in tags):
                score += 2.0
            if any(tok in str(k).lower() for k in keywords):
                score += 1.0
        if score > 0:
            results.append(
                (
                    score,
                    {
                        "doc_id": doc.get("id"),
                        "title": title,
                        "tags": tags,
                        "keywords": keywords[:20],
                        "preview": preview,
                        "score": score,
                    },
                )
            )

    results.sort(key=lambda x: x[0], reverse=True)
    return [r[1] for r in results[:max(1, int(top_k))]]


def _chunk_text(text: str, chunk_size: int = 1200, overlap: int = 150) -> List[str]:
    if not text:
        return []
    text = text.strip()
    if not text:
        return []

    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: List[str] = []
    buff: List[str] = []
    total = 0

    def flush():
        nonlocal buff, total
        if buff:
            chunk = "\n\n".join(buff).strip()
            if chunk:
                chunks.append(chunk)
        buff = []
        total = 0

    for para in paragraphs:
        if total + len(para) + 2 > chunk_size and buff:
            flush()
        buff.append(para)
        total += len(para) + 2

    flush()

    if overlap > 0 and len(chunks) > 1:
        overlapped = []
        for i, chunk in enumerate(chunks):
            if i == 0:
                overlapped.append(chunk)
                continue
            prev = chunks[i - 1]
            prefix = prev[-overlap:] if len(prev) > overlap else prev
            overlapped.append((prefix + "\n\n" + chunk).strip())
        chunks = overlapped

    return chunks


def _extract_text(file_path: str) -> Tuple[str, List[str]]:
    warnings: List[str] = []
    ext = os.path.splitext(file_path)[-1].lower()
    text = ""

    if ext in {".txt", ".md", ".csv", ".tsv"}:
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()
        except Exception as e:
            warnings.append(f"read_failed:{e}")

    elif ext == ".docx":
        try:
            import docx
            doc = docx.Document(file_path)
            parts = [p.text for p in doc.paragraphs if p.text]
            text = "\n".join(parts)
        except Exception as e:
            warnings.append(f"docx_failed:{e}")

    elif ext == ".pdf":
        file_size = None
        try:
            file_size = int(os.path.getsize(file_path))
        except Exception:
            file_size = None

        def _extract_from_pages(pages_obj: Any, total_pages: int) -> str:
            buffer = StringIO()
            chars_total = 0
            pages_read = 0
            page_limit = int(total_pages)
            truncated_reasons: List[str] = []
            char_limit = int(MAX_PDF_CHARS_PER_FILE)
            if char_limit <= 0:
                # Safety guard: never allow unbounded extraction even if env disables soft limits.
                char_limit = int(PDF_HARD_CHAR_CAP) if PDF_HARD_CHAR_CAP > 0 else 5_000_000
                warnings.append("pdf_chars_limit_fallback")
            if MAX_PDF_PAGES > 0:
                page_limit = min(page_limit, int(MAX_PDF_PAGES))
            if (
                MAX_PDF_BYTES_PER_FILE > 0
                and isinstance(file_size, int)
                and file_size > MAX_PDF_BYTES_PER_FILE
            ):
                warnings.append("pdf_truncated_bytes")
                truncated_reasons.append("bytes")
                if MAX_PDF_PAGES <= 0 and total_pages > 0:
                    ratio = float(MAX_PDF_BYTES_PER_FILE) / float(max(1, file_size))
                    dynamic_limit = max(1, int(total_pages * ratio))
                    page_limit = min(page_limit, dynamic_limit)

            for idx, page in enumerate(pages_obj):
                if idx >= page_limit:
                    break
                pages_read += 1
                try:
                    page_text = page.extract_text() or ""
                except Exception:
                    continue
                if not page_text:
                    continue

                remaining = char_limit - chars_total
                if remaining <= 0:
                    warnings.append("pdf_truncated_chars")
                    truncated_reasons.append("chars")
                    break
                if len(page_text) > remaining:
                    buffer.write(page_text[:remaining])
                    chars_total += remaining
                    warnings.append("pdf_truncated_chars")
                    truncated_reasons.append("chars")
                    break

                buffer.write(page_text)
                buffer.write("\n")
                chars_total += len(page_text)

            if MAX_PDF_PAGES > 0 and total_pages > MAX_PDF_PAGES:
                warnings.append("pdf_truncated_pages")
                truncated_reasons.append("pages")
            if pages_read < total_pages and MAX_PDF_PAGES <= 0 and page_limit < total_pages:
                warnings.append("pdf_truncated_pages_dynamic")
                truncated_reasons.append("pages_dynamic")
            warnings.append(f"pdf_pages_read:{pages_read}")
            warnings.append(f"pdf_chars_extracted:{chars_total}")
            if truncated_reasons:
                uniq_reasons = ",".join(dict.fromkeys(truncated_reasons))
                warnings.append(f"pdf_truncated_reason:{uniq_reasons}")
            return buffer.getvalue()

        try:
            import pdfplumber  # type: ignore
            with pdfplumber.open(file_path) as pdf:
                text = _extract_from_pages(pdf.pages, len(pdf.pages))
        except Exception:
            try:
                from PyPDF2 import PdfReader  # type: ignore
                reader = PdfReader(file_path)
                text = _extract_from_pages(reader.pages, len(reader.pages))
            except Exception as e:
                warnings.append(f"pdf_failed:{e}")

    else:
        warnings.append("unsupported_type")

    return _clean_text(text), warnings


def list_documents() -> List[Dict[str, Any]]:
    index = _load_index()
    docs = index.get("docs")
    return docs if isinstance(docs, list) else []


def get_document(doc_id: str) -> Optional[Dict[str, Any]]:
    _ensure_dirs()
    path = os.path.join(DOCS_DIR, f"{doc_id}.json")
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def add_document(
    *,
    file_bytes: bytes,
    filename: str,
    title: Optional[str] = None,
    tags: Optional[List[str]] = None,
) -> Dict[str, Any]:
    _ensure_dirs()
    doc_id = str(uuid.uuid4())
    safe_name = os.path.basename(filename or "document")
    ext = os.path.splitext(safe_name)[-1].lower()
    upload_path = os.path.join(UPLOADS_DIR, f"{doc_id}{ext}")
    _atomic_write_bytes(upload_path, file_bytes)

    text, warnings = _extract_text(upload_path)
    chunks = _chunk_text(text)

    preview = ""
    if chunks:
        preview = chunks[0][:400]
    elif text:
        preview = text[:400]

    keywords = _extract_keywords(text)
    doc_payload = {
        "id": doc_id,
        "filename": safe_name,
        "title": title or safe_name,
        "tags": tags or [],
        "created_at": _utc_iso(),
        "source_path": upload_path,
        "source_type": ext.lstrip("."),
        "text": text,
        "chunks": chunks,
        "keywords": keywords,
        "warnings": warnings,
    }

    _atomic_write_json(os.path.join(DOCS_DIR, f"{doc_id}.json"), doc_payload)

    index = _load_index()
    docs = index.get("docs")
    if not isinstance(docs, list):
        docs = []

    docs.append(
        {
            "id": doc_id,
            "filename": safe_name,
            "title": title or safe_name,
            "tags": tags or [],
            "created_at": doc_payload["created_at"],
            "source_type": ext.lstrip("."),
            "size_bytes": len(file_bytes),
            "text_chars": len(text),
            "num_chunks": len(chunks),
            "preview": preview,
            "warnings": warnings,
            "keywords": keywords,
        }
    )
    index["docs"] = docs
    _save_index(index)

    return {"id": doc_id, "warnings": warnings, "preview": preview, "text_chars": len(text), "num_chunks": len(chunks)}


def search_documents(query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    q = str(query or "").strip().lower()
    if not q:
        return []
    tokens = [t for t in q.replace(",", " ").split() if t]
    if not tokens:
        return []

    results: List[Tuple[float, Dict[str, Any]]] = []
    for doc in list_documents():
        doc_id = doc.get("id")
        if not doc_id:
            continue
        payload = get_document(str(doc_id))
        if not isinstance(payload, dict):
            continue
        chunks = payload.get("chunks") if isinstance(payload.get("chunks"), list) else []
        best_score = 0.0
        best_chunk = None
        for chunk in chunks[:200]:
            text = str(chunk or "").lower()
            if not text:
                continue
            score = 0.0
            for tok in tokens:
                if tok in text:
                    score += text.count(tok)
            if score > best_score:
                best_score = score
                best_chunk = chunk
        if best_score > 0:
            keywords = payload.get("keywords") if isinstance(payload.get("keywords"), list) else []
            results.append(
                (
                    best_score,
                    {
                        "doc_id": doc_id,
                        "title": doc.get("title") or doc.get("filename"),
                        "score": best_score,
                        "snippet": (best_chunk or "")[:400],
                        "tags": doc.get("tags") or [],
                        "keywords": keywords[:20],
                    },
                )
            )

    results.sort(key=lambda x: x[0], reverse=True)
    return [r[1] for r in results[:max(1, int(top_k))]]


def delete_document(doc_id: str) -> bool:
    if not doc_id:
        return False
    _ensure_dirs()
    removed = False
    try:
        doc_path = os.path.join(DOCS_DIR, f"{doc_id}.json")
        if os.path.exists(doc_path):
            with open(doc_path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            try:
                src = payload.get("source_path")
                if src and os.path.exists(src):
                    os.remove(src)
            except Exception:
                pass
            os.remove(doc_path)
            removed = True
    except Exception as e:
        logger.error(f"Failed to delete knowledge doc {doc_id}: {e}", exc_info=True)
        return False

    index = _load_index()
    docs = index.get("docs") if isinstance(index.get("docs"), list) else []
    docs = [d for d in docs if str(d.get("id")) != str(doc_id)]
    index["docs"] = docs
    _save_index(index)
    return removed
