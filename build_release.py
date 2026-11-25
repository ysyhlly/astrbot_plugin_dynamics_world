"""Build the self-contained plugin archive without caches or installation data."""

import argparse
import ast
import hashlib
import io
import json
import subprocess
import zipfile
from pathlib import Path


def release_metadata(root):
    """Identify clean checkouts and preserve the commit recorded by git archive."""
    raw = (root / "metadata.yaml").read_bytes()
    marker = b"$Format:%H$"
    if marker not in raw or not (root / ".git").exists():
        return raw
    try:
        if subprocess.check_output(
            ["git", "-C", str(root), "status", "--porcelain"], stderr=subprocess.DEVNULL, timeout=5
        ).strip():
            return raw
        revision = subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "--verify", "HEAD"], stderr=subprocess.DEVNULL, timeout=5
        ).strip()
    except (OSError, subprocess.SubprocessError):
        return raw
    if len(revision) not in (40, 64) or any(c not in b"0123456789abcdef" for c in revision):
        return raw
    return raw.replace(marker, revision)


_DEFAULT_PLUGIN_DIR_NAME = "astrbot_plugin_dynamics_world"

_AZGAAR_EXCLUDED_PREFIXES = (
    "icons-charges-",
    "icons-goods-",
    "view-3d-renderer",
    "view-3d-",
    "Dropbox-sdk",
    "notes-editor",
    "assistant-",
    "Assistant-",
    "Knowledge Base",
    "jszip",
    "battle-screen",
    "Battle-Simulator",
    "ui-tour",
)

_AZGAAR_EXCLUDED_IMAGES = {
    "waves.png",
    "preview.png",
    "tour-button-icon.png",
    "kiwiroo.png",
    "Discord.png",
    "Reddit.png",
    "Pinterest.png",
    "Twitter.png",
    "Facebook.png",
}


def _archive_root_name(root: Path) -> str:
    """Resolve the single top-level plugin folder name for installable archives."""
    meta = root / "metadata.yaml"
    if meta.is_file():
        for raw_line in meta.read_text("utf-8", errors="ignore").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("name:"):
                name = line.split(":", 1)[1].strip().strip("\"'")
                if name and "/" not in name and "\\" not in name and name not in {".", ".."}:
                    return name
                break
    return root.name or _DEFAULT_PLUGIN_DIR_NAME


def _is_excluded_azgaar_asset(rel: Path) -> bool:
    """Exclude interactive-only Azgaar assets unused by headless map_renderer.py."""
    if rel.parts[:2] != ("vendor", "azgaar"):
        return False
    if rel.parts[:4] in {
        ("vendor", "azgaar", "images", "textures"),
        ("vendor", "azgaar", "images", "icons"),
        ("vendor", "azgaar", "images", "style-presets"),
    }:
        return True
    if rel.parts[:3] in {
        ("vendor", "azgaar", "styles"),
        ("vendor", "azgaar", "heightmaps"),
    }:
        return True
    if (
        len(rel.parts) == 4
        and rel.parts[:3] == ("vendor", "azgaar", "images")
        and rel.parts[3] in _AZGAAR_EXCLUDED_IMAGES
    ):
        return True
    if len(rel.parts) == 3:
        name = rel.parts[2]
        if name in {"dropbox.html", "sw.js"} or any(
            name.startswith(prefix) for prefix in _AZGAAR_EXCLUDED_PREFIXES
        ):
            return True
    return False


def build(root, output):
    root = Path(root).resolve()
    output = Path(output).resolve()
    top_level_dir = _archive_root_name(root)
    buffer = io.BytesIO()
    files = []
    excluded = {
        ".git",
        ".github",
        "__pycache__",
        ".pytest_cache",
        ".ruff_cache",
        ".mypy_cache",
        "node_modules",
        "tests",
        "data",
        "dist",
        "release",
        ".venv",
        "src",
    }
    excluded_files = {
        "nul",
        "cmd_config.json",
        "worldbook_store.json",
        ".env",
        ".gitignore",
        ".gitattributes",
        "requirements-dev.txt",
        "build_release.py",
        "package.json",
        "package-lock.json",
    }
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(root.rglob("*")):
            rel = path.relative_to(root)
            if (
                not path.is_file()
                or path.resolve() == output
                or any(p in excluded for p in rel.parts)
            ):
                continue
            if (
                path.name in excluded_files
                or path.suffix in {".sqlite3", ".db", ".pyc", ".zip", ".bak"}
                or path.name.endswith("_config.json")
            ):
                continue
            if _is_excluded_azgaar_asset(rel):
                continue
            if path.suffix == ".py":
                tree = ast.parse(path.read_text("utf-8-sig"))
                for node in ast.walk(tree):
                    names = (
                        [n.name for n in node.names]
                        if isinstance(node, ast.Import)
                        else [node.module or ""]
                        if isinstance(node, ast.ImportFrom)
                        else []
                    )
                    if any(name == "logging" or name.startswith("logging.") for name in names):
                        raise ValueError(
                            f"{rel}:{node.lineno}: runtime must use astrbot.api.logger"
                        )
            arcname = f"{top_level_dir}/{rel.as_posix()}"
            info = zipfile.ZipInfo(arcname, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, release_metadata(root) if rel.as_posix() == "metadata.yaml" else path.read_bytes())
            files.append(arcname)
    data = buffer.getvalue()
    if len(data) > 16_000_000:
        raise ValueError("Release archive exceeds the 16 MB market limit")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(data)
    return {
        "bytes": len(data),
        "MiB": round(len(data) / 1048576, 2),
        "sha256": hashlib.sha256(data).hexdigest(),
        "files": len(files),
        "top_level_dir": top_level_dir,
        "output": str(output),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    print(json.dumps(build(Path(__file__).parent, args.output), indent=2))
