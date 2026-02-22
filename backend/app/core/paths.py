import os


def get_repo_root() -> str:
    # backend/app/core/paths.py -> repo root is three levels up from this file.
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.realpath(os.path.join(here, "..", "..", ".."))


def get_workspace_dir() -> str:
    raw = str(os.getenv("CLINIMETRIA_WORKSPACE_DIR", "workspace") or "").strip() or "workspace"
    if os.path.isabs(raw):
        return os.path.realpath(raw)
    return os.path.realpath(os.path.join(get_repo_root(), raw))


def get_datasets_dir() -> str:
    return os.path.join(get_workspace_dir(), "datasets")


def get_knowledge_dir() -> str:
    return os.path.join(get_workspace_dir(), "knowledge")

