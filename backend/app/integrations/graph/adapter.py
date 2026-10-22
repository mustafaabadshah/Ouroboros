import os
import json
import ast
from pathlib import Path
from typing import Dict, List, Any, Optional
import httpx
import networkx as nx

from app.core.config import settings
from app.core.logging import logger

class MetaGraphAdapter:
    """
    Decoupled adapter for querying Meta-Graph Codebase Navigator.
    Supports 3-tier resilient architecture:
    1. Remote HTTP API probe
    2. Direct file ingestion of data/indexes/{repo_id}_nx.json into NetworkX
    3. Standalone Python AST static scanner fallback
    """

    def __init__(self, navigator_path: Optional[str] = None, api_url: Optional[str] = None):
        self.navigator_path = Path(navigator_path or settings.NAVIGATOR_PATH)
        self.api_url = (api_url or settings.NAVIGATOR_API_URL).rstrip("/")
        self._cached_graphs: Dict[str, nx.MultiDiGraph] = {}
        self._repo_metadata: Dict[str, Dict[str, Any]] = {}
        self._cached_summaries: Dict[str, Dict[str, Any]] = {}

    def clear_cache(self, repo_id: Optional[str] = None) -> None:
        """Clears in-memory graph and architectural summary caches."""
        if repo_id:
            self._cached_graphs.pop(repo_id, None)
            self._repo_metadata.pop(repo_id, None)
            self._cached_summaries.pop(repo_id, None)
        else:
            self._cached_graphs.clear()
            self._repo_metadata.clear()
            self._cached_summaries.clear()

    async def check_connection(self, repo_id: str = "agent_chess") -> Dict[str, Any]:
        """Probes HTTP API and local index files to determine graph availability."""
        # 1. Try HTTP API
        try:
            async with httpx.AsyncClient(timeout=1.5) as client:
                res = await client.get(f"{self.api_url}/api/health")
                if res.status_code == 200:
                    data = res.json()
                    return {
                        "connected": True,
                        "mode": "HTTP_API",
                        "api_url": self.api_url,
                        "details": data
                    }
        except Exception:
            pass

        # 2. Try Local File Index
        index_file = self._find_index_file(repo_id)
        if index_file.exists():
            graph = self._load_local_graph(repo_id)
            return {
                "connected": True,
                "mode": "DIRECT_FILE_INDEX",
                "index_path": str(index_file),
                "node_count": graph.number_of_nodes(),
                "edge_count": graph.number_of_edges(),
                "details": f"Direct NetworkX graph loaded with {graph.number_of_nodes()} nodes and {graph.number_of_edges()} edges."
            }

        # 3. Dynamic AST Indexing if repo registered in DB with valid directory
        try:
            from app.database.session import SessionLocal
            from app.database.models import RepositoryModel
            with SessionLocal() as db:
                r = db.query(RepositoryModel).filter(RepositoryModel.id == repo_id).first()
                if r and r.path and Path(r.path).exists():
                    graph = self.index_directory(repo_id, r.path)
                    return {
                        "connected": True,
                        "mode": "DYNAMIC_AST_INDEX",
                        "index_path": str(self._find_index_file(repo_id)),
                        "node_count": graph.number_of_nodes(),
                        "edge_count": graph.number_of_edges(),
                        "details": f"Dynamic AST graph parsed with {graph.number_of_nodes()} nodes and {graph.number_of_edges()} edges from {r.path}."
                    }
        except Exception as e:
            logger.debug(f"DB fallback for AST index check notice: {e}")

        # 4. Fallback Mode
        return {
            "connected": False,
            "mode": "AST_FALLBACK",
            "message": f"Meta-Graph HTTP API offline and index file not found at {index_file}. Local AST scanner active."
        }

    def _find_index_file(self, repo_id: str) -> Path:
        primary = self.navigator_path / "data" / "indexes" / f"{repo_id}_nx.json"
        if primary.exists():
            return primary
        # Check backend fixture indexes
        backend_dir = Path(__file__).resolve().parent.parent.parent.parent
        candidates = [
            backend_dir / "tests" / "fixtures" / "indexes" / f"{repo_id}_nx.json",
            Path.cwd() / "backend" / "tests" / "fixtures" / "indexes" / f"{repo_id}_nx.json",
        ]
        for c in candidates:
            if c.exists():
                return c
        return primary

    def index_directory(self, repo_id: str, repo_path: Any) -> nx.MultiDiGraph:
        """
        Parses all source and configuration files in repo_path:
        - Python (.py) via AST parsing (classes, functions, imports, calls, test links)
        - TypeScript/JavaScript (.ts, .tsx, .js, .jsx) via symbol and import parsing
        - Documentation and configs (.md, .json, .yaml, .yml, .toml)
        Builds a comprehensive NetworkX MultiDiGraph across all codebase subsystems.
        """
        repo_dir = Path(repo_path)
        if not repo_dir.exists() or not repo_dir.is_dir():
            logger.warning(f"Directory {repo_path} does not exist for AST indexing.")
            return nx.MultiDiGraph()

        graph = nx.MultiDiGraph()
        nodes_data = []
        edges_data = []

        ignore_dirs = {
            ".git", ".venv", "venv", "__pycache__", "node_modules", "dist", "build",
            ".pytest_cache", ".eggs", ".idea", ".vscode", "worktrees", ".next", ".nuxt"
        }
        supported_exts = {
            ".py", ".ts", ".tsx", ".js", ".jsx", ".json", ".md", ".yml", ".yaml", ".toml", ".html", ".css", ".sql"
        }

        project_files = []
        for root, dirs, files in os.walk(repo_dir):
            dirs[:] = [d for d in dirs if d not in ignore_dirs and not d.startswith(".")]
            for f in files:
                ext = Path(f).suffix.lower()
                if ext in supported_exts or f.lower() in ("dockerfile", "makefile"):
                    full_p = Path(root) / f
                    project_files.append(full_p)

        file_nodes = {}
        defined_symbols = {}

        for p in project_files:
            try:
                rel = str(p.relative_to(repo_dir)).replace("\\", "/")
            except ValueError:
                rel = p.name

            ext = p.suffix.lower()
            f_node_id = f"{repo_id}:file:{rel}"
            file_node_dict = {
                "id": f_node_id,
                "type": "File",
                "name": p.name,
                "rel_path": rel,
                "extension": ext,
                "repo_id": repo_id
            }
            graph.add_node(f_node_id, **file_node_dict)
            nodes_data.append(file_node_dict)
            file_nodes[rel] = f_node_id

            # 1. Python AST parsing
            if ext == ".py":
                try:
                    content = p.read_text(encoding="utf-8", errors="replace")
                    tree = ast.parse(content, filename=str(p))
                except Exception as e:
                    logger.debug(f"AST parse error in {rel}: {e}")
                    continue

                for node in ast.iter_child_nodes(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        sym_id = f"{repo_id}:function:{rel}:{node.name}"
                        sym_data = {
                            "id": sym_id,
                            "type": "Function",
                            "name": node.name,
                            "rel_path": rel,
                            "start_line": getattr(node, "lineno", None),
                            "end_line": getattr(node, "end_lineno", None),
                        }
                        graph.add_node(sym_id, **sym_data)
                        nodes_data.append(sym_data)
                        graph.add_edge(f_node_id, sym_id, key=f"DEFINES:{node.lineno}", type="DEFINES", line=node.lineno)
                        edges_data.append({"source_id": f_node_id, "target_id": sym_id, "type": "DEFINES", "properties": {"line": node.lineno}})
                        defined_symbols.setdefault(node.name, []).append((sym_id, rel))

                        for subnode in ast.walk(node):
                            if isinstance(subnode, ast.Call):
                                call_name = None
                                if isinstance(subnode.func, ast.Name):
                                    call_name = subnode.func.id
                                elif isinstance(subnode.func, ast.Attribute):
                                    call_name = subnode.func.attr
                                if call_name:
                                    graph.add_edge(sym_id, call_name, key=f"CALLS:{getattr(subnode, 'lineno', 0)}", type="CALLS", line=getattr(subnode, "lineno", 0))

                    elif isinstance(node, ast.ClassDef):
                        cls_id = f"{repo_id}:class:{rel}:{node.name}"
                        cls_data = {
                            "id": cls_id,
                            "type": "Class",
                            "name": node.name,
                            "rel_path": rel,
                            "start_line": getattr(node, "lineno", None),
                            "end_line": getattr(node, "end_lineno", None),
                        }
                        graph.add_node(cls_id, **cls_data)
                        nodes_data.append(cls_data)
                        graph.add_edge(f_node_id, cls_id, key=f"DEFINES:{node.lineno}", type="DEFINES", line=node.lineno)
                        edges_data.append({"source_id": f_node_id, "target_id": cls_id, "type": "DEFINES", "properties": {"line": node.lineno}})
                        defined_symbols.setdefault(node.name, []).append((cls_id, rel))

                        for item in node.body:
                            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                                m_id = f"{repo_id}:function:{rel}:{node.name}.{item.name}"
                                m_data = {
                                    "id": m_id,
                                    "type": "Function",
                                    "name": f"{node.name}.{item.name}",
                                    "rel_path": rel,
                                    "start_line": getattr(item, "lineno", None),
                                    "end_line": getattr(item, "end_lineno", None),
                                }
                                graph.add_node(m_id, **m_data)
                                nodes_data.append(m_data)
                                graph.add_edge(cls_id, m_id, key=f"DEFINES:{item.lineno}", type="DEFINES", line=item.lineno)
                                edges_data.append({"source_id": cls_id, "target_id": m_id, "type": "DEFINES", "properties": {"line": item.lineno}})
                                defined_symbols.setdefault(item.name, []).append((m_id, rel))

                    elif isinstance(node, (ast.Import, ast.ImportFrom)):
                        imported_module = getattr(node, "module", "") or ""
                        line_no = getattr(node, "lineno", 1)
                        graph.add_edge(f_node_id, imported_module, key=f"IMPORTS:{line_no}", type="IMPORTS", line=line_no)
                        edges_data.append({"source_id": f_node_id, "target_id": imported_module, "type": "IMPORTS", "properties": {"line": line_no}})

            # 2. TypeScript / JavaScript Parsing
            elif ext in (".ts", ".tsx", ".js", ".jsx"):
                try:
                    import re
                    content = p.read_text(encoding="utf-8", errors="replace")
                    lines = content.splitlines()

                    for line_idx, line in enumerate(lines, 1):
                        # Component / Function export
                        match_fn = re.search(r'(?:export\s+(?:default\s+)?(?:async\s+)?function\s+([A-Za-z0-9_]+)|export\s+const\s+([A-Za-z0-9_]+)\s*[:=])', line)
                        if match_fn:
                            fn_name = match_fn.group(1) or match_fn.group(2)
                            if fn_name and not fn_name.startswith("_") and fn_name not in ("default", "const"):
                                is_comp = fn_name[0].isupper() and ext in (".tsx", ".jsx")
                                sym_id = f"{repo_id}:component:{rel}:{fn_name}" if is_comp else f"{repo_id}:function:{rel}:{fn_name}"
                                sym_data = {
                                    "id": sym_id,
                                    "type": "Component" if is_comp else "Function",
                                    "name": fn_name,
                                    "rel_path": rel,
                                    "start_line": line_idx,
                                    "end_line": line_idx + 10
                                }
                                graph.add_node(sym_id, **sym_data)
                                nodes_data.append(sym_data)
                                graph.add_edge(f_node_id, sym_id, key=f"DEFINES:{line_idx}", type="DEFINES", line=line_idx)
                                edges_data.append({"source_id": f_node_id, "target_id": sym_id, "type": "DEFINES", "properties": {"line": line_idx}})
                                defined_symbols.setdefault(fn_name, []).append((sym_id, rel))

                        # Class export
                        match_cls = re.search(r'export\s+(?:default\s+)?class\s+([A-Za-z0-9_]+)', line)
                        if match_cls:
                            cls_name = match_cls.group(1)
                            sym_id = f"{repo_id}:class:{rel}:{cls_name}"
                            sym_data = {
                                "id": sym_id,
                                "type": "Class",
                                "name": cls_name,
                                "rel_path": rel,
                                "start_line": line_idx,
                                "end_line": line_idx + 20
                            }
                            graph.add_node(sym_id, **sym_data)
                            nodes_data.append(sym_data)
                            graph.add_edge(f_node_id, sym_id, key=f"DEFINES:{line_idx}", type="DEFINES", line=line_idx)
                            edges_data.append({"source_id": f_node_id, "target_id": sym_id, "type": "DEFINES", "properties": {"line": line_idx}})
                            defined_symbols.setdefault(cls_name, []).append((sym_id, rel))

                        # Import statement
                        match_imp = re.search(r'import\s+.*?from\s+[\'"](.*?)[\'"]', line)
                        if match_imp:
                            imp_mod = match_imp.group(1)
                            graph.add_edge(f_node_id, imp_mod, key=f"IMPORTS:{line_idx}", type="IMPORTS", line=line_idx)
                            edges_data.append({"source_id": f_node_id, "target_id": imp_mod, "type": "IMPORTS", "properties": {"line": line_idx}})
                except Exception as e:
                    logger.debug(f"TS parse error in {rel}: {e}")

        # Resolve unresolved CALLS edges
        for u, v, data in list(graph.edges(data=True)):
            if data.get("type") == "CALLS" and isinstance(v, str) and not v.startswith(f"{repo_id}:"):
                if v in defined_symbols:
                    target_id, target_file = defined_symbols[v][0]
                    graph.remove_edge(u, v)
                    graph.add_edge(u, target_id, key=f"CALLS:{data.get('line', 0)}", type="CALLS", line=data.get("line", 0))
                    edges_data.append({"source_id": u, "target_id": target_id, "type": "CALLS", "properties": {"line": data.get("line", 0)}})

        # Detect test relationships across python & typescript tests
        for rel, f_node_id in file_nodes.items():
            rel_lower = rel.lower()
            if any(k in rel_lower for k in ("test_", "_test", ".test.", ".spec.", "/tests/")):
                stem = Path(rel).stem.replace("test_", "").replace("_test", "").replace(".test", "").replace(".spec", "")
                for other_rel, other_node_id in file_nodes.items():
                    if other_rel != rel and stem and (stem in other_rel.lower()):
                        graph.add_edge(f_node_id, other_node_id, key="TESTS:0", type="TESTS")
                        edges_data.append({"source_id": f_node_id, "target_id": other_node_id, "type": "TESTS", "properties": {}})

        # Save to data/indexes/{repo_id}_nx.json
        index_dir = self.navigator_path / "data" / "indexes"
        index_dir.mkdir(parents=True, exist_ok=True)
        index_file = index_dir / f"{repo_id}_nx.json"

        meta = {
            "id": repo_id,
            "name": repo_dir.name,
            "root_path": str(repo_dir),
            "total_files": len(project_files)
        }
        self._repo_metadata[repo_id] = meta

        try:
            with open(index_file, "w", encoding="utf-8") as f:
                json.dump({
                    "repository": meta,
                    "nodes": nodes_data,
                    "edges": edges_data
                }, f, indent=2)
            logger.info(f"Generated comprehensive AST index for {repo_id}: {graph.number_of_nodes()} nodes, {graph.number_of_edges()} edges saved to {index_file}")
        except Exception as e:
            logger.warning(f"Could not persist AST index to {index_file}: {e}")

        self._cached_graphs[repo_id] = graph
        self._cached_summaries.pop(repo_id, None)
        return graph

    def _load_local_graph(self, repo_id: str) -> nx.MultiDiGraph:
        """Loads and caches the NetworkX graph from data/indexes/{repo_id}_nx.json."""
        if repo_id in self._cached_graphs:
            return self._cached_graphs[repo_id]

        index_file = self._find_index_file(repo_id)
        graph = nx.MultiDiGraph()

        if index_file.exists():
            try:
                with open(index_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                self._repo_metadata[repo_id] = data.get("repository", {})
                for node in data.get("nodes", []):
                    nid = node["id"]
                    graph.add_node(nid, **node)

                for edge in data.get("edges", []):
                    graph.add_edge(
                        edge["source_id"],
                        edge["target_id"],
                        key=f"{edge['type']}:{edge.get('properties', {}).get('line', 0)}",
                        type=edge["type"],
                        **edge.get("properties", {})
                    )
                logger.info(f"Loaded {graph.number_of_nodes()} nodes and {graph.number_of_edges()} edges for {repo_id}")
            except Exception as e:
                logger.error(f"Failed to parse NetworkX index {index_file}: {e}")
        else:
            # Fallback to auto-indexing if known repository in DB
            try:
                from app.database.session import SessionLocal
                from app.database.models import RepositoryModel
                with SessionLocal() as db:
                    r = db.query(RepositoryModel).filter(RepositoryModel.id == repo_id).first()
                    if r and r.path and Path(r.path).exists():
                        return self.index_directory(repo_id, r.path)
            except Exception as e:
                logger.debug(f"Auto-index fallback notice: {e}")

        self._cached_graphs[repo_id] = graph
        return graph

    def get_file_dependencies(self, repo_id: str, rel_path: str) -> Dict[str, Any]:
        """Returns callers, imports, and declared symbols for a specific file."""
        graph = self._load_local_graph(repo_id)
        clean_path = rel_path.replace("\\", "/")
        file_node_id = f"{repo_id}:file:{clean_path}"

        if not graph.has_node(file_node_id):
            # Try fuzzy match on rel_path attribute
            matches = [n for n, d in graph.nodes(data=True) if d.get("rel_path") == clean_path]
            if matches:
                file_node_id = matches[0]
            else:
                return {"file": clean_path, "found": False, "symbols": [], "dependencies": []}

        symbols = []
        imports = []
        callers = []

        # Find nodes contained in this file
        for _, target, data in graph.out_edges(file_node_id, data=True):
            edge_type = data.get("type")
            if edge_type in ("CONTAINS", "DEFINES"):
                node_data = graph.nodes.get(target, {})
                symbols.append({
                    "id": target,
                    "name": node_data.get("name"),
                    "type": node_data.get("type", "Symbol"),
                    "start_line": node_data.get("start_line"),
                    "end_line": node_data.get("end_line")
                })
            elif edge_type == "IMPORTS":
                imports.append(target)

        # Find callers into symbols of this file
        for sym in symbols:
            sid = sym["id"]
            for caller, _, data in graph.in_edges(sid, data=True):
                if data.get("type") == "CALLS":
                    c_data = graph.nodes.get(caller, {})
                    callers.append({
                        "caller_name": c_data.get("name", caller),
                        "caller_file": c_data.get("rel_path"),
                        "called_symbol": sym["name"]
                    })

        return {
            "file": clean_path,
            "found": True,
            "symbols": symbols,
            "imports": imports,
            "callers": callers[:20]  # bounded context
        }

    @staticmethod
    def _is_runnable_test_file(path_str: Optional[str]) -> bool:
        """Determines if a path represents an executable test file (e.g. test_*.py or *_test.py), ignoring fixtures/conftest."""
        if not path_str:
            return False
        clean = str(path_str).replace("\\", "/").lower()
        if not clean.endswith(".py"):
            return False
        filename = Path(clean).name
        # Disallow non-test files: conftest, __init__, fixtures, setup
        if (
            filename.startswith("conftest") or
            filename.startswith("__") or
            "fixture" in filename or
            filename == "setup.py"
        ):
            return False
        # Require standard pytest naming conventions
        return filename.startswith("test_") or filename.endswith("_test.py")

    def get_associated_tests(self, repo_id: str, candidate_files: List[str]) -> List[str]:
        """Identifies test files and test functions related to the candidate files."""
        graph = self._load_local_graph(repo_id)
        matched_tests = set()

        for f in candidate_files:
            clean = f.replace("\\", "/").lower()
            base = Path(clean).stem

            # 1. Search graph for TESTS relationships
            for u, v, data in graph.edges(data=True):
                if data.get("type") == "TESTS":
                    u_data = graph.nodes.get(u, {})
                    v_data = graph.nodes.get(v, {})
                    target_rel = str(v_data.get("rel_path", "")).lower()
                    test_candidate = u_data.get("rel_path", u)
                    if clean in target_rel and self._is_runnable_test_file(test_candidate):
                        matched_tests.add(test_candidate)

            # 2. Heuristic convention matching (e.g. backend/tests/test_agents.py for backend/app/agents/...)
            for node, d in graph.nodes(data=True):
                rel = str(d.get("rel_path", "")).replace("\\", "/").lower()
                if self._is_runnable_test_file(rel):
                    if base in rel or any(part in rel for part in Path(clean).parts if len(part) > 3):
                        matched_tests.add(d.get("rel_path"))

        return sorted([t for t in matched_tests if self._is_runnable_test_file(t)])

    def get_impacted_tests_from_callgraph(
        self,
        repo_id: str,
        candidate_files: List[str],
        target_symbols: Optional[List[str]] = None
    ) -> List[str]:
        """
        AST-Directed Test Impact Ordering (Fail-Fast):
        Traverses AST dependency and call graphs to identify test files that directly
        import the modified module or directly call the target symbols.
        Orders them by impact depth (direct symbol callers first, direct module importers second)
        so the Judge can execute targeted fail-fast tests within 2-3s before running the full suite.
        Excludes fixtures, conftest.py, and non-test modules.
        """
        graph = self._load_local_graph(repo_id)
        if graph.number_of_nodes() == 0:
            return [t for t in self.get_associated_tests(repo_id, candidate_files) if self._is_runnable_test_file(t)]

        direct_symbol_test_files = set()
        direct_import_test_files = set()
        heuristic_test_files = set()

        norm_symbols = set()
        if target_symbols:
            for s in target_symbols:
                clean_s = str(s).strip().lower()
                norm_symbols.add(clean_s)
                if "." in clean_s:
                    norm_symbols.add(clean_s.split(".")[-1])

        candidate_rel_paths = set()
        candidate_modules = set()
        for f in candidate_files:
            clean_f = f.replace("\\", "/").lower()
            candidate_rel_paths.add(clean_f)
            stem = Path(clean_f).stem
            candidate_modules.add(stem)
            parts = clean_f.replace(".py", "").split("/")
            if "app" in parts:
                app_idx = parts.index("app")
                candidate_modules.add(".".join(parts[app_idx:]))

        for node, data in graph.nodes(data=True):
            rel = str(data.get("rel_path", "")).replace("\\", "/").lower()
            # Only consider runnable test files (excludes conftest.py, fixtures, etc.)
            if not self._is_runnable_test_file(rel):
                continue

            test_path_val = data.get("rel_path")

            # Check if this test node calls target symbols
            if norm_symbols:
                for _, target, edge_data in graph.out_edges(node, data=True):
                    if edge_data.get("type") == "CALLS":
                        target_name = str(target).lower()
                        if target_name in norm_symbols or any(sym in target_name for sym in norm_symbols):
                            direct_symbol_test_files.add(test_path_val)

            # Check outbound IMPORTS edges from test file
            for _, target_mod, edge_data in graph.out_edges(node, data=True):
                if edge_data.get("type") == "IMPORTS":
                    target_mod_str = str(target_mod).lower()
                    if any(c_mod in target_mod_str for c_mod in candidate_modules):
                        direct_import_test_files.add(test_path_val)

            # Check explicit TESTS edges
            for _, target_file, edge_data in graph.out_edges(node, data=True):
                if edge_data.get("type") == "TESTS":
                    tf_str = str(target_file).lower()
                    if any(c_rel in tf_str for c_rel in candidate_rel_paths):
                        direct_symbol_test_files.add(test_path_val)

            # Heuristic naming fallback
            for c_f in candidate_files:
                base = Path(c_f).stem.lower()
                if base in rel:
                    heuristic_test_files.add(test_path_val)

        ordered_tests = []
        for t in list(direct_symbol_test_files):
            if t and self._is_runnable_test_file(t) and t not in ordered_tests:
                ordered_tests.append(t)
        for t in list(direct_import_test_files):
            if t and self._is_runnable_test_file(t) and t not in ordered_tests:
                ordered_tests.append(t)
        for t in list(heuristic_test_files):
            if t and self._is_runnable_test_file(t) and t not in ordered_tests:
                ordered_tests.append(t)

        if ordered_tests:
            return ordered_tests
        return [t for t in self.get_associated_tests(repo_id, candidate_files) if self._is_runnable_test_file(t)]

    def get_architectural_summary(self, repo_id: str, max_files: int = 100) -> Dict[str, Any]:
        """Provides comprehensive architectural overview across all subsystems and key symbols for the Architect Agent."""
        if repo_id in self._cached_summaries:
            return dict(self._cached_summaries[repo_id])

        graph = self._load_local_graph(repo_id)
        if graph.number_of_nodes() == 0:
            return {"status": "empty", "modules": []}

        modules: Dict[str, List[str]] = {}
        subsystem_categories: Dict[str, str] = {}
        category_counts: Dict[str, int] = {"BACKEND": 0, "FRONTEND": 0, "DOCS": 0, "CONFIG": 0}
        classes: List[Dict[str, str]] = []
        functions: List[Dict[str, str]] = []

        for n, d in graph.nodes(data=True):
            ntype = d.get("type")
            rel = str(d.get("rel_path", "")).replace("\\", "/")
            if ntype == "File":
                parent_mod = str(Path(rel).parent).replace("\\", "/")
                if parent_mod == ".":
                    parent_mod = "root"
                modules.setdefault(parent_mod, []).append(Path(rel).name)
            elif ntype in ("Class",):
                classes.append({"class_name": d.get("name", ""), "file": rel})
            elif ntype in ("Function", "Component"):
                fname = d.get("name", "")
                if not fname.startswith("__"):
                    functions.append({"func_name": fname, "file": rel, "type": ntype})

        # Categorize subsystems
        for mod in modules.keys():
            mod_lower = mod.lower()
            if mod_lower.startswith("frontend") or "src/" in mod_lower or "components" in mod_lower:
                cat = "FRONTEND"
            elif mod_lower.startswith("backend") or "app/" in mod_lower or "server" in mod_lower:
                cat = "BACKEND"
            elif mod_lower.startswith("docs") or "doc" in mod_lower:
                cat = "DOCS"
            else:
                cat = "CONFIG"
            subsystem_categories[mod] = cat
            category_counts[cat] = category_counts.get(cat, 0) + 1

        # Priority sort: BACKEND first, then FRONTEND, then DOCS, then CONFIG
        def sort_key(item):
            mod_name, _ = item
            cat = subsystem_categories.get(mod_name, "CONFIG")
            order = {"BACKEND": 0, "FRONTEND": 1, "DOCS": 2, "CONFIG": 3}
            return (order.get(cat, 99), mod_name)

        sorted_modules = dict(sorted(modules.items(), key=sort_key))

        summary = {
            "status": "ready",
            "repo_id": repo_id,
            "total_nodes": graph.number_of_nodes(),
            "total_edges": graph.number_of_edges(),
            "module_structure": {k: v[:50] for k, v in list(sorted_modules.items())[:max_files]},
            "subsystem_categories": subsystem_categories,
            "category_counts": category_counts,
            "key_classes": classes[:40],
            "key_functions": functions[:60]
        }
        self._cached_summaries[repo_id] = summary
        return summary

meta_graph_adapter = MetaGraphAdapter()
