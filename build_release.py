"""Build the self-contained plugin archive without caches or installation data."""
import argparse
import ast
import hashlib
import io
import json
import zipfile
from pathlib import Path

def _uses_host_core_logger(tree, relative):
    if relative not in {"life/core/narrative.py", "life/core/narrative_io.py"}:
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("logging"):
            return False
        if isinstance(node, ast.Import):
            if any(n.name.startswith("logging") and (n.name != "logging" or n.asname) for n in node.names):
                return False
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "logging":
            if node.attr not in {"getLogger", "INFO", "DEBUG"}:
                return False
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name) and node.func.value.id == "logging":
                if node.func.attr != "getLogger" or len(node.args) != 1 or node.keywords:
                    return False
                if not isinstance(node.args[0], ast.Constant) or node.args[0].value != "astrbot.plugin.astrbot_plugin_dynamics_world":
                    return False
            if node.func.attr in {"addHandler", "removeHandler", "setLevel"}:
                return False
    return True


def build(root,output):
    root=Path(root).resolve();output=Path(output).resolve();buffer=io.BytesIO();files=[]
    excluded={'.git','__pycache__','.pytest_cache','node_modules','tests','data','dist','release','.venv'}
    with zipfile.ZipFile(buffer,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for path in sorted(root.rglob('*')):
            rel=path.relative_to(root)
            if not path.is_file() or path.resolve()==output or any(p in excluded for p in rel.parts):continue
            if path.name in {'nul','cmd_config.json','worldbook_store.json','.env','requirements-dev.txt'} or path.suffix in {'.sqlite3','.db','.pyc','.zip'} or path.name.endswith('_config.json'):continue
            if rel.parts[:4]==('vendor','azgaar','images','textures'):continue
            if path.suffix=='.py':
                tree = ast.parse(path.read_text('utf-8-sig'))
                core_logger = _uses_host_core_logger(tree, rel.as_posix())
                for node in ast.walk(tree):
                    names=([n.name for n in node.names] if isinstance(node,ast.Import)
                           else [node.module or ''] if isinstance(node,ast.ImportFrom) else [])
                    if any(name=='logging' or name.startswith('logging.') for name in names) and not core_logger:
                        raise ValueError(f'{rel}:{node.lineno}: runtime must use astrbot.api.logger')
            archive.write(path,rel.as_posix());files.append(rel.as_posix())
    data=buffer.getvalue()
    if len(data)>16_000_000:raise ValueError('Release archive exceeds the 16 MB market limit')
    output.parent.mkdir(parents=True,exist_ok=True);output.write_bytes(data)
    return {'bytes':len(data),'MiB':round(len(data)/1048576,2),'sha256':hashlib.sha256(data).hexdigest(),'files':len(files),'output':str(output)}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('output',type=Path);args=parser.parse_args()
    print(json.dumps(build(Path(__file__).parent,args.output),indent=2))
