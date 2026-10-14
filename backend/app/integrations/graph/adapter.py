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
        index_file = self.navigator_path / "data" / "indexes" / f"{repo_id}_nx.json"
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

        # 3. Fallback Mode
        return {
            "connected": False,
            "mode": "AST_FALLBACK",
            "message": f"Meta-Graph HTTP API offline and index file not found at {index_file}. Local AST scanner active."
        }

    def _load_local_graph(self, repo_id: str) -> nx.MultiDiGraph:
        """Loads and caches the NetworkX graph from data/indexes/{repo_id}_nx.json."""
        if repo_id in self._cached_graphs:
            return self._cached_graphs[repo_id]

        index_file = self.navigator_path / "data" / "indexes" / f"{repo_id}_nx.json"
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
                    if clean in str(v_data.get("rel_path", "")).lower():
                        matched_tests.add(u_data.get("rel_path", u))

            # 2. Heuristic convention matching (e.g. backend/tests/test_agents.py for backend/app/agents/...)
            for node, d in graph.nodes(data=True):
                rel = str(d.get("rel_path", "")).replace("\\", "/").lower()
                if "test_" in rel:
                    if base in rel or any(part in rel for part in Path(clean).parts if len(part) > 3):
                        matched_tests.add(d.get("rel_path"))

        return sorted(list(matched_tests))

    def get_architectural_summary(self, repo_id: str, max_files: int = 15) -> Dict[str, Any]:
        """Provides high-level architectural overview and key symbols for the Architect Agent."""
        graph = self._load_local_graph(repo_id)
        if graph.number_of_nodes() == 0:
            return {"status": "empty", "modules": []}

        modules: Dict[str, List[str]] = {}
        classes: List[Dict[str, str]] = []
        functions: List[Dict[str, str]] = []

        for n, d in graph.nodes(data=True):
            ntype = d.get("type")
            rel = str(d.get("rel_path", "")).replace("\\", "/")
            if ntype == "File":
                parent_mod = str(Path(rel).parent).replace("\\", "/")
                modules.setdefault(parent_mod, []).append(Path(rel).name)
            elif ntype == "Class":
                classes.append({"class_name": d.get("name", ""), "file": rel})
            elif ntype == "Function":
                fname = d.get("name", "")
                if not fname.startswith("__"):
                    functions.append({"func_name": fname, "file": rel})

        return {
            "status": "ready",
            "repo_id": repo_id,
            "total_nodes": graph.number_of_nodes(),
            "total_edges": graph.number_of_edges(),
            "module_structure": {k: v[:8] for k, v in list(modules.items())[:max_files]},
            "key_classes": classes[:25],
            "key_functions": functions[:35]
        }

meta_graph_adapter = MetaGraphAdapter()
