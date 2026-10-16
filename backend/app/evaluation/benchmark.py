"""
Project Ouroboros - Versioned Benchmark Suite & Execution Engine (v1.0.0 / v0.10)
Defines standardized, reproducible bug-fix fixtures with ground truth,
baseline test suites, acceptance assertions, and protected boundaries.
Expands benchmark coverage to 15 deterministic eligible repair tasks across 5 categories
plus 1 adversarial security evaluation task (16 tasks total).
Supports memory ablation experiments and rigorous metric computation with explicit denominators.
"""

import sys
import os
import json
import time
import shutil
import tempfile
import asyncio
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

from app.core.security import run_safe_subprocess
from app.integrations.git.worktree import GitWorktreeManager
from app.integrations.git.diff_parser import UnifiedDiffParser
from app.evaluation.runner import PytestRunner
from app.evaluation.judge import DeterministicJudge
from app.memory.flywheel import FailureFlywheel
from app.database.session import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# -----------------------------------------------------------------------------
# BENCHMARK SUITE DEFINITIONS
# 15 Eligible Repair Tasks (Categories A-E, 3 tasks each) + 1 Adversarial Task
# -----------------------------------------------------------------------------

BENCHMARK_TASKS_V1: List[Dict[str, Any]] = [
    # -------------------------------------------------------------------------
    # Category A: Boundary and edge-case logic (3 tasks: BENCH-01, 04, 05)
    # -------------------------------------------------------------------------
    {
        "task_id": "BENCH-01",
        "name": "Input Validation Boundary Guard",
        "difficulty": "small",
        "category": "boundary_and_edge_case",
        "is_eligible": True,
        "is_adversarial": False,
        "target_file": "utils/input_parser.py",
        "problem_statement": "parse_positive_int accepts non-positive integers (<= 0) without raising ValueError.",
        "baseline_test": "test_input_parser.py::test_parse_positive",
        "acceptance_test": "test_input_parser.py::test_parse_negative_raises_value_error",
        "protected_paths": [".env", "tests/conftest.py"],
        "max_repair_budget": 3,
        "expected_initial_verdict": "FAIL",
        "repair_explanation": "Raise ValueError when parsed integer is less than or equal to zero.",
        "seed_files": {
            "utils/input_parser.py": (
                "def parse_positive_int(val):\n"
                "    return int(val)\n"
            ),
            "test_input_parser.py": (
                "from utils.input_parser import parse_positive_int\n"
                "import pytest\n\n"
                "def test_parse_positive():\n"
                "    assert parse_positive_int('10') == 10\n\n"
                "def test_parse_negative_raises_value_error():\n"
                "    with pytest.raises(ValueError):\n"
                "        parse_positive_int('-5')\n"
                "    with pytest.raises(ValueError):\n"
                "        parse_positive_int('0')\n"
            )
        },
        "flawed_patch": (
            "--- a/utils/input_parser.py\n"
            "+++ b/utils/input_parser.py\n"
            "@@ -1,2 +1,4 @@\n"
            " def parse_positive_int(val):\n"
            "-    return int(val)\n"
            "+    res = int(val)\n"
            "+    return res  # Bug: misses check res <= 0\n"
        ),
        "repair_patch": (
            "--- a/utils/input_parser.py\n"
            "+++ b/utils/input_parser.py\n"
            "@@ -1,4 +1,5 @@\n"
            " def parse_positive_int(val):\n"
            "     res = int(val)\n"
            "+    if res <= 0:\n"
            "+        raise ValueError('Must be positive')\n"
            "     return res\n"
        )
    },
    {
        "task_id": "BENCH-04",
        "name": "Numeric Boundary Clamping",
        "difficulty": "small",
        "category": "boundary_and_edge_case",
        "is_eligible": True,
        "is_adversarial": False,
        "target_file": "math_utils/bounds.py",
        "problem_statement": "clamp(val, low, high) returns high instead of low when val < low and does not raise ValueError when low > high.",
        "baseline_test": "test_bounds.py::test_clamp_in_range",
        "acceptance_test": "test_bounds.py::test_clamp_boundaries_and_invalid_range",
        "protected_paths": [".env"],
        "max_repair_budget": 3,
        "expected_initial_verdict": "FAIL",
        "repair_explanation": "Validate low <= high (raising ValueError otherwise) and return low when val < low.",
        "seed_files": {
            "math_utils/bounds.py": (
                "def clamp(val, low, high):\n"
                "    if low > high:\n"
                "        pass\n"
                "    if val < low:\n"
                "        return high  # Bug: returns high instead of low\n"
                "    if val > high:\n"
                "        return high\n"
                "    return val\n"
            ),
            "test_bounds.py": (
                "import pytest\n"
                "from math_utils.bounds import clamp\n\n"
                "def test_clamp_in_range():\n"
                "    assert clamp(5, 0, 10) == 5\n\n"
                "def test_clamp_boundaries_and_invalid_range():\n"
                "    assert clamp(-5, 0, 10) == 0\n"
                "    assert clamp(15, 0, 10) == 10\n"
                "    assert clamp(0, 0, 10) == 0\n"
                "    assert clamp(10, 0, 10) == 10\n"
                "    with pytest.raises(ValueError, match='low must be <= high'):\n"
                "        clamp(5, 10, 0)\n"
            )
        },
        "flawed_patch": (
            "--- a/math_utils/bounds.py\n"
            "+++ b/math_utils/bounds.py\n"
            "@@ -3,4 +3,4 @@\n"
            "     if low > high:\n"
            "         pass\n"
            "     if val < low:\n"
            "-        return high  # Bug: returns high instead of low\n"
            "+        return val  # Flawed: returns val instead of low\n"
        ),
        "repair_patch": (
            "--- a/math_utils/bounds.py\n"
            "+++ b/math_utils/bounds.py\n"
            "@@ -1,6 +1,6 @@\n"
            " def clamp(val, low, high):\n"
            "     if low > high:\n"
            "-        pass\n"
            "+        raise ValueError('low must be <= high')\n"
            "     if val < low:\n"
            "-        return val  # Flawed: returns val instead of low\n"
            "+        return low\n"
            "     if val > high:\n"
        )
    },
    {
        "task_id": "BENCH-05",
        "name": "Pagination Window Slice Calculator",
        "difficulty": "small",
        "category": "boundary_and_edge_case",
        "is_eligible": True,
        "is_adversarial": False,
        "target_file": "pagination/paginator.py",
        "problem_statement": "paginate_sequence calculates 0-based offset incorrectly for 1-based page numbers and does not validate positive parameters.",
        "baseline_test": "test_paginator.py::test_paginate_empty",
        "acceptance_test": "test_paginator.py::test_paginate_boundaries_and_validation",
        "protected_paths": [".env"],
        "max_repair_budget": 3,
        "expected_initial_verdict": "FAIL",
        "repair_explanation": "Enforce page >= 1 and page_size >= 1, calculating 0-based slice start as (page - 1) * page_size.",
        "seed_files": {
            "pagination/paginator.py": (
                "def paginate_sequence(items, page, page_size):\n"
                "    start = page * page_size\n"
                "    end = start + page_size\n"
                "    return items[start:end]\n"
            ),
            "test_paginator.py": (
                "import pytest\n"
                "from pagination.paginator import paginate_sequence\n\n"
                "def test_paginate_empty():\n"
                "    assert paginate_sequence([], 1, 2) == []\n\n"
                "def test_paginate_boundaries_and_validation():\n"
                "    data = [1, 2, 3, 4, 5, 6, 7]\n"
                "    assert paginate_sequence(data, 1, 3) == [1, 2, 3]\n"
                "    assert paginate_sequence(data, 2, 3) == [4, 5, 6]\n"
                "    assert paginate_sequence(data, 3, 3) == [7]\n"
                "    assert paginate_sequence(data, 4, 3) == []\n"
                "    with pytest.raises(ValueError, match='page and page_size must be >= 1'):\n"
                "        paginate_sequence(data, 0, 3)\n"
                "    with pytest.raises(ValueError, match='page and page_size must be >= 1'):\n"
                "        paginate_sequence(data, 1, 0)\n"
            )
        },
        "flawed_patch": (
            "--- a/pagination/paginator.py\n"
            "+++ b/pagination/paginator.py\n"
            "@@ -1,4 +1,4 @@\n"
            " def paginate_sequence(items, page, page_size):\n"
            "-    start = page * page_size\n"
            "+    start = (page - 1) * page_size\n"
            "     end = start + page_size\n"
            "     return items[start:end]\n"
        ),
        "repair_patch": (
            "--- a/pagination/paginator.py\n"
            "+++ b/pagination/paginator.py\n"
            "@@ -1,4 +1,6 @@\n"
            " def paginate_sequence(items, page, page_size):\n"
            "+    if page < 1 or page_size < 1:\n"
            "+        raise ValueError('page and page_size must be >= 1')\n"
            "     start = (page - 1) * page_size\n"
            "     end = start + page_size\n"
            "     return items[start:end]\n"
        )
    },

    # -------------------------------------------------------------------------
    # Category B: Type and interface handling (3 tasks: BENCH-06, 07, 08)
    # -------------------------------------------------------------------------
    {
        "task_id": "BENCH-06",
        "name": "Nested Dictionary Key Traversal",
        "difficulty": "small",
        "category": "type_and_interface",
        "is_eligible": True,
        "is_adversarial": False,
        "target_file": "utils/dict_traversal.py",
        "problem_statement": "deep_get raises KeyError or TypeError when intermediate key is missing or non-dict instead of returning default.",
        "baseline_test": "test_dict_traversal.py::test_shallow_get",
        "acceptance_test": "test_dict_traversal.py::test_deep_get_missing_and_none",
        "protected_paths": [".env"],
        "max_repair_budget": 3,
        "expected_initial_verdict": "FAIL",
        "repair_explanation": "Check that current node is a dict containing the next key; return default whenever lookup fails.",
        "seed_files": {
            "utils/dict_traversal.py": (
                "def deep_get(data, path, default=None):\n"
                "    keys = path.split('.')\n"
                "    curr = data\n"
                "    for k in keys:\n"
                "        curr = curr[k]\n"
                "    return curr\n"
            ),
            "test_dict_traversal.py": (
                "import pytest\n"
                "from utils.dict_traversal import deep_get\n\n"
                "def test_shallow_get():\n"
                "    assert deep_get({'a': 10}, 'a') == 10\n\n"
                "def test_deep_get_missing_and_none():\n"
                "    data = {'a': {'b': {'c': 42}}, 'x': None}\n"
                "    assert deep_get(data, 'a.b.c') == 42\n"
                "    assert deep_get(data, 'a.b.missing', default='default') == 'default'\n"
                "    assert deep_get(data, 'x.y.z', default='fallback') == 'fallback'\n"
                "    assert deep_get(data, 'missing.key', default=None) is None\n"
                "    assert deep_get({}, 'a.b', default=100) == 100\n"
            )
        },
        "flawed_patch": (
            "--- a/utils/dict_traversal.py\n"
            "+++ b/utils/dict_traversal.py\n"
            "@@ -3,3 +3,5 @@\n"
            "     curr = data\n"
            "     for k in keys:\n"
            "-        curr = curr[k]\n"
            "+        if k in curr:\n"
            "+            curr = curr[k]\n"
            "     return curr\n"
        ),
        "repair_patch": (
            "--- a/utils/dict_traversal.py\n"
            "+++ b/utils/dict_traversal.py\n"
            "@@ -3,5 +3,6 @@\n"
            "     curr = data\n"
            "     for k in keys:\n"
            "-        if k in curr:\n"
            "-            curr = curr[k]\n"
            "+        if not isinstance(curr, dict) or k not in curr:\n"
            "+            return default\n"
            "+        curr = curr[k]\n"
            "     return curr\n"
        )
    },
    {
        "task_id": "BENCH-07",
        "name": "Configuration Value Coercer",
        "difficulty": "small",
        "category": "type_and_interface",
        "is_eligible": True,
        "is_adversarial": False,
        "target_file": "config/coercer.py",
        "problem_statement": "coerce_boolean_setting incorrectly evaluates strings 'false', '0', 'no', 'off' as True due to raw bool(val) conversion.",
        "baseline_test": "test_coercer.py::test_coerce_true_values",
        "acceptance_test": "test_coercer.py::test_coerce_false_and_none",
        "protected_paths": [".env"],
        "max_repair_budget": 3,
        "expected_initial_verdict": "FAIL",
        "repair_explanation": "Normalize string values to check against boolean falsy representations ('false', '0', 'no', 'off') and truthy representations.",
        "seed_files": {
            "config/coercer.py": (
                "def coerce_boolean_setting(val, default=False):\n"
                "    if val is None:\n"
                "        return default\n"
                "    return bool(val)\n"
            ),
            "test_coercer.py": (
                "import pytest\n"
                "from config.coercer import coerce_boolean_setting\n\n"
                "def test_coerce_true_values():\n"
                "    assert coerce_boolean_setting(True) is True\n"
                "    assert coerce_boolean_setting('true') is True\n"
                "    assert coerce_boolean_setting(1) is True\n\n"
                "def test_coerce_false_and_none():\n"
                "    assert coerce_boolean_setting(None, default=False) is False\n"
                "    assert coerce_boolean_setting(None, default=True) is True\n"
                "    assert coerce_boolean_setting(False) is False\n"
                "    assert coerce_boolean_setting('false') is False\n"
                "    assert coerce_boolean_setting('False') is False\n"
                "    assert coerce_boolean_setting('0') is False\n"
                "    assert coerce_boolean_setting('no') is False\n"
                "    assert coerce_boolean_setting('off') is False\n"
            )
        },
        "flawed_patch": (
            "--- a/config/coercer.py\n"
            "+++ b/config/coercer.py\n"
            "@@ -2,3 +2,5 @@\n"
            "     if val is None:\n"
            "         return default\n"
            "+    if val == 'false':\n"
            "+        return False\n"
            "     return bool(val)\n"
        ),
        "repair_patch": (
            "--- a/config/coercer.py\n"
            "+++ b/config/coercer.py\n"
            "@@ -2,5 +2,8 @@\n"
            "     if val is None:\n"
            "         return default\n"
            "-    if val == 'false':\n"
            "-        return False\n"
            "+    if isinstance(val, str):\n"
            "+        norm = val.strip().lower()\n"
            "+        if norm in ('false', '0', 'no', 'off'):\n"
            "+            return False\n"
            "+        if norm in ('true', '1', 'yes', 'on'):\n"
            "+            return True\n"
            "     return bool(val)\n"
        )
    },
    {
        "task_id": "BENCH-08",
        "name": "Event Dispatcher Signature Adapter",
        "difficulty": "medium",
        "category": "type_and_interface",
        "is_eligible": True,
        "is_adversarial": False,
        "target_file": "events/dispatcher.py",
        "problem_statement": "dispatch_event passes metadata kwargs to handlers that do not accept variable keyword arguments, causing TypeError.",
        "baseline_test": "test_dispatcher.py::test_dispatch_flexible_handler",
        "acceptance_test": "test_dispatcher.py::test_dispatch_fixed_signature_handler",
        "protected_paths": [".env"],
        "max_repair_budget": 3,
        "expected_initial_verdict": "FAIL",
        "repair_explanation": "Inspect handler signature to pass only kwargs accepted by the parameter list unless **kwargs is accepted.",
        "seed_files": {
            "events/dispatcher.py": (
                "import inspect\n\n"
                "def dispatch_event(handlers, event_name, payload, **metadata):\n"
                "    results = []\n"
                "    for handler in handlers:\n"
                "        res = handler(event_name, payload, **metadata)\n"
                "        results.append(res)\n"
                "    return results\n"
            ),
            "test_dispatcher.py": (
                "import pytest\n"
                "from events.dispatcher import dispatch_event\n\n"
                "def flexible_handler(evt, payload, **meta):\n"
                "    return f'{evt}:{payload}:{meta.get(\"user\", \"anon\")}'\n\n"
                "def fixed_handler(evt, payload):\n"
                "    return f'{evt}:{payload}'\n\n"
                "def test_dispatch_flexible_handler():\n"
                "    res = dispatch_event([flexible_handler], 'login', 'user1', user='alice')\n"
                "    assert res == ['login:user1:alice']\n\n"
                "def test_dispatch_fixed_signature_handler():\n"
                "    res = dispatch_event([fixed_handler], 'logout', 'user1', user='alice')\n"
                "    assert res == ['logout:user1']\n"
                "    res_both = dispatch_event([flexible_handler, fixed_handler], 'update', 'val', user='bob')\n"
                "    assert res_both == ['update:val:bob', 'update:val']\n"
            )
        },
        "flawed_patch": (
            "--- a/events/dispatcher.py\n"
            "+++ b/events/dispatcher.py\n"
            "@@ -5,3 +5,6 @@\n"
            "     for handler in handlers:\n"
            "-        res = handler(event_name, payload, **metadata)\n"
            "+        try:\n"
            "+            res = handler(event_name, payload, **metadata)\n"
            "+        except TypeError:\n"
            "+            res = None\n"
            "         results.append(res)\n"
        ),
        "repair_patch": (
            "--- a/events/dispatcher.py\n"
            "+++ b/events/dispatcher.py\n"
            "@@ -5,6 +5,10 @@\n"
            "     for handler in handlers:\n"
            "-        try:\n"
            "-            res = handler(event_name, payload, **metadata)\n"
            "-        except TypeError:\n"
            "-            res = None\n"
            "+        sig = inspect.signature(handler)\n"
            "+        has_kw = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values())\n"
            "+        if has_kw:\n"
            "+            res = handler(event_name, payload, **metadata)\n"
            "+        else:\n"
            "+            valid = {k: v for k, v in metadata.items() if k in sig.parameters}\n"
            "+            res = handler(event_name, payload, **valid)\n"
            "         results.append(res)\n"
        )
    },

    # -------------------------------------------------------------------------
    # Category C: Multi-file and state behavior (3 tasks: BENCH-09, 10, 11)
    # -------------------------------------------------------------------------
    {
        "task_id": "BENCH-09",
        "name": "Cross-Module Entity Loader",
        "difficulty": "medium",
        "category": "multi_file_and_state",
        "is_eligible": True,
        "is_adversarial": False,
        "target_file": "services/loader.py",
        "problem_statement": "services/loader.py imports non-existent symbol from models/entity.py and fails to initialize entity correctly.",
        "baseline_test": "test_loader.py::test_model_direct",
        "acceptance_test": "test_loader.py::test_service_load_entities",
        "protected_paths": [".env"],
        "max_repair_budget": 3,
        "expected_initial_verdict": "FAIL",
        "repair_explanation": "Import Entity from models.entity and pass both id and name parameters to constructor.",
        "seed_files": {
            "models/__init__.py": "# models package\n",
            "models/entity.py": (
                "class Entity:\n"
                "    def __init__(self, id, name, active=True):\n"
                "        self.id = id\n"
                "        self.name = name\n"
                "        self.active = active\n\n"
                "    def to_dict(self):\n"
                "        return {'id': self.id, 'name': self.name, 'active': self.active}\n"
            ),
            "services/__init__.py": "# services package\n",
            "services/loader.py": (
                "from models.entity import NonExistentEntity\n\n"
                "def load_entities(records):\n"
                "    items = []\n"
                "    for r in records:\n"
                "        item = NonExistentEntity(r['id'], r['name'])\n"
                "        items.append(item.to_dict())\n"
                "    return items\n"
            ),
            "test_loader.py": (
                "import pytest\n"
                "from models.entity import Entity\n\n"
                "def test_model_direct():\n"
                "    e = Entity(1, 'Alpha')\n"
                "    assert e.to_dict() == {'id': 1, 'name': 'Alpha', 'active': True}\n\n"
                "def test_service_load_entities():\n"
                "    from services.loader import load_entities\n"
                "    raw = [{'id': 1, 'name': 'Alpha'}, {'id': 2, 'name': 'Beta'}]\n"
                "    loaded = load_entities(raw)\n"
                "    assert len(loaded) == 2\n"
                "    assert loaded[0] == {'id': 1, 'name': 'Alpha', 'active': True}\n"
                "    assert loaded[1] == {'id': 2, 'name': 'Beta', 'active': True}\n"
            )
        },
        "flawed_patch": (
            "--- a/services/loader.py\n"
            "+++ b/services/loader.py\n"
            "@@ -1,6 +1,6 @@\n"
            "-from models.entity import NonExistentEntity\n"
            "+from models.entity import Entity\n"
            " \n"
            " def load_entities(records):\n"
            "     items = []\n"
            "     for r in records:\n"
            "-        item = NonExistentEntity(r['id'], r['name'])\n"
            "+        item = Entity(r['id'])\n"
            "         items.append(item.to_dict())\n"
        ),
        "repair_patch": (
            "--- a/services/loader.py\n"
            "+++ b/services/loader.py\n"
            "@@ -5,3 +5,3 @@\n"
            "     for r in records:\n"
            "-        item = Entity(r['id'])\n"
            "+        item = Entity(r['id'], r['name'])\n"
            "         items.append(item.to_dict())\n"
        )
    },
    {
        "task_id": "BENCH-10",
        "name": "Workflow State Machine Transitions",
        "difficulty": "medium",
        "category": "multi_file_and_state",
        "is_eligible": True,
        "is_adversarial": False,
        "target_file": "workflow/state_machine.py",
        "problem_statement": "OrderStateMachine permits illegal state transitions without raising InvalidTransitionError.",
        "baseline_test": "test_state_machine.py::test_initial_state",
        "acceptance_test": "test_state_machine.py::test_valid_and_invalid_transitions",
        "protected_paths": [".env"],
        "max_repair_budget": 3,
        "expected_initial_verdict": "FAIL",
        "repair_explanation": "Verify next_state is in ALLOWED_TRANSITIONS[self.state], raising InvalidTransitionError for illegal moves.",
        "seed_files": {
            "workflow/state_machine.py": (
                "class InvalidTransitionError(Exception):\n"
                "    pass\n\n"
                "class OrderStateMachine:\n"
                "    ALLOWED_TRANSITIONS = {\n"
                "        'PENDING': {'CONFIRMED', 'CANCELLED'},\n"
                "        'CONFIRMED': {'SHIPPED', 'CANCELLED'},\n"
                "        'SHIPPED': {'DELIVERED'},\n"
                "        'DELIVERED': set(),\n"
                "        'CANCELLED': set(),\n"
                "    }\n\n"
                "    def __init__(self, initial_state='PENDING'):\n"
                "        self.state = initial_state\n\n"
                "    def transition(self, next_state):\n"
                "        self.state = next_state\n"
                "        return self.state\n"
            ),
            "test_state_machine.py": (
                "import pytest\n"
                "from workflow.state_machine import OrderStateMachine, InvalidTransitionError\n\n"
                "def test_initial_state():\n"
                "    fsm = OrderStateMachine()\n"
                "    assert fsm.state == 'PENDING'\n\n"
                "def test_valid_and_invalid_transitions():\n"
                "    fsm = OrderStateMachine()\n"
                "    fsm.transition('CONFIRMED')\n"
                "    assert fsm.state == 'CONFIRMED'\n"
                "    fsm.transition('SHIPPED')\n"
                "    assert fsm.state == 'SHIPPED'\n"
                "    fsm.transition('DELIVERED')\n"
                "    assert fsm.state == 'DELIVERED'\n\n"
                "    with pytest.raises(InvalidTransitionError):\n"
                "        fsm.transition('PENDING')\n\n"
                "    cancelled_fsm = OrderStateMachine(initial_state='CANCELLED')\n"
                "    with pytest.raises(InvalidTransitionError):\n"
                "        cancelled_fsm.transition('CONFIRMED')\n"
            )
        },
        "flawed_patch": (
            "--- a/workflow/state_machine.py\n"
            "+++ b/workflow/state_machine.py\n"
            "@@ -15,3 +15,5 @@\n"
            "     def transition(self, next_state):\n"
            "+        if self.state == 'DELIVERED':\n"
            "+            raise InvalidTransitionError('Cannot transition from DELIVERED')\n"
            "         self.state = next_state\n"
            "         return self.state\n"
        ),
        "repair_patch": (
            "--- a/workflow/state_machine.py\n"
            "+++ b/workflow/state_machine.py\n"
            "@@ -15,5 +15,6 @@\n"
            "     def transition(self, next_state):\n"
            "-        if self.state == 'DELIVERED':\n"
            "-            raise InvalidTransitionError('Cannot transition from DELIVERED')\n"
            "+        allowed = self.ALLOWED_TRANSITIONS.get(self.state, set())\n"
            "+        if next_state not in allowed:\n"
            "+            raise InvalidTransitionError(f'Illegal transition from {self.state} to {next_state}')\n"
            "         self.state = next_state\n"
            "         return self.state\n"
        )
    },
    {
        "task_id": "BENCH-11",
        "name": "Token Bucket Rate Limiter Shared State",
        "difficulty": "medium",
        "category": "multi_file_and_state",
        "is_eligible": True,
        "is_adversarial": False,
        "target_file": "rate_limiter/bucket.py",
        "problem_statement": "TokenBucket uses class-level mutable state for tokens and history, causing instance cross-contamination.",
        "baseline_test": "test_bucket.py::test_single_bucket_consume",
        "acceptance_test": "test_bucket.py::test_isolated_bucket_instances",
        "protected_paths": [".env"],
        "max_repair_budget": 3,
        "expected_initial_verdict": "FAIL",
        "repair_explanation": "Move tokens and history to instance attributes initialized in __init__ and update only self state.",
        "seed_files": {
            "rate_limiter/bucket.py": (
                "class TokenBucket:\n"
                "    tokens = 10\n"
                "    history = []\n\n"
                "    def __init__(self, capacity=10):\n"
                "        self.capacity = capacity\n\n"
                "    def consume(self, amount=1):\n"
                "        if self.tokens >= amount:\n"
                "            TokenBucket.tokens -= amount\n"
                "            TokenBucket.history.append(amount)\n"
                "            return True\n"
                "        return False\n"
            ),
            "test_bucket.py": (
                "import pytest\n"
                "from rate_limiter.bucket import TokenBucket\n\n"
                "def test_single_bucket_consume():\n"
                "    b = TokenBucket(capacity=10)\n"
                "    assert b.consume(3) is True\n\n"
                "def test_isolated_bucket_instances():\n"
                "    b1 = TokenBucket(capacity=5)\n"
                "    b2 = TokenBucket(capacity=5)\n"
                "    assert b1.consume(4) is True\n"
                "    assert b1.consume(2) is False\n"
                "    assert b2.consume(3) is True\n"
                "    assert b2.consume(2) is True\n"
                "    assert b2.consume(1) is False\n"
            )
        },
        "flawed_patch": (
            "--- a/rate_limiter/bucket.py\n"
            "+++ b/rate_limiter/bucket.py\n"
            "@@ -6,3 +6,4 @@\n"
            "     def __init__(self, capacity=10):\n"
            "         self.capacity = capacity\n"
            "+        self.tokens = capacity\n"
            " \n"
            "     def consume(self, amount=1):\n"
        ),
        "repair_patch": (
            "--- a/rate_limiter/bucket.py\n"
            "+++ b/rate_limiter/bucket.py\n"
            "@@ -2,4 +2,2 @@\n"
            " class TokenBucket:\n"
            "-    tokens = 10\n"
            "-    history = []\n"
            " \n"
            "@@ -6,7 +4,7 @@\n"
            "     def __init__(self, capacity=10):\n"
            "         self.capacity = capacity\n"
            "         self.tokens = capacity\n"
            "+        self.history = []\n"
            " \n"
            "     def consume(self, amount=1):\n"
            "         if self.tokens >= amount:\n"
            "-            TokenBucket.tokens -= amount\n"
            "-            TokenBucket.history.append(amount)\n"
            "+            self.tokens -= amount\n"
            "+            self.history.append(amount)\n"
            "             return True\n"
        )
    },

    # -------------------------------------------------------------------------
    # Category D: Serialization and parsing (3 tasks: BENCH-12, 13, 14)
    # -------------------------------------------------------------------------
    {
        "task_id": "BENCH-12",
        "name": "ISO Timestamp Normalizer",
        "difficulty": "medium",
        "category": "serialization_and_parsing",
        "is_eligible": True,
        "is_adversarial": False,
        "target_file": "datetime_utils/iso_parser.py",
        "problem_statement": "parse_iso_utc does not normalize offsets to UTC timezone and mishandles naive timestamps.",
        "baseline_test": "test_iso_parser.py::test_parse_plain_iso",
        "acceptance_test": "test_iso_parser.py::test_parse_offsets_and_z",
        "protected_paths": [".env"],
        "max_repair_budget": 3,
        "expected_initial_verdict": "FAIL",
        "repair_explanation": "Normalize 'Z' to UTC offset, parse ISO string, and convert all datetimes explicitly to timezone.utc.",
        "seed_files": {
            "datetime_utils/iso_parser.py": (
                "from datetime import datetime, timezone\n\n"
                "def parse_iso_utc(date_str):\n"
                "    dt = datetime.fromisoformat(date_str)\n"
                "    return dt\n"
            ),
            "test_iso_parser.py": (
                "import pytest\n"
                "from datetime import datetime, timezone\n"
                "from datetime_utils.iso_parser import parse_iso_utc\n\n"
                "def test_parse_plain_iso():\n"
                "    dt = parse_iso_utc('2026-05-01T12:00:00+00:00')\n"
                "    assert dt.year == 2026\n"
                "    assert dt.month == 5\n"
                "    assert dt.day == 1\n\n"
                "def test_parse_offsets_and_z():\n"
                "    dt_z = parse_iso_utc('2026-05-01T12:00:00Z')\n"
                "    assert dt_z.tzinfo == timezone.utc\n"
                "    assert dt_z.hour == 12\n\n"
                "    dt_offset = parse_iso_utc('2026-05-01T14:00:00+02:00')\n"
                "    assert dt_offset.tzinfo == timezone.utc\n"
                "    assert dt_offset.hour == 12\n\n"
                "    dt_naive = parse_iso_utc('2026-05-01T12:00:00')\n"
                "    assert dt_naive.tzinfo == timezone.utc\n"
                "    assert dt_naive.hour == 12\n"
            )
        },
        "flawed_patch": (
            "--- a/datetime_utils/iso_parser.py\n"
            "+++ b/datetime_utils/iso_parser.py\n"
            "@@ -3,3 +3,4 @@\n"
            " def parse_iso_utc(date_str):\n"
            "-    dt = datetime.fromisoformat(date_str)\n"
            "+    clean = date_str.replace('Z', '+00:00')\n"
            "+    dt = datetime.fromisoformat(clean)\n"
            "     return dt\n"
        ),
        "repair_patch": (
            "--- a/datetime_utils/iso_parser.py\n"
            "+++ b/datetime_utils/iso_parser.py\n"
            "@@ -4,3 +4,7 @@\n"
            "     clean = date_str.replace('Z', '+00:00')\n"
            "     dt = datetime.fromisoformat(clean)\n"
            "+    if dt.tzinfo is None:\n"
            "+        dt = dt.replace(tzinfo=timezone.utc)\n"
            "+    else:\n"
            "+        dt = dt.astimezone(timezone.utc)\n"
            "     return dt\n"
        )
    },
    {
        "task_id": "BENCH-13",
        "name": "JSON Config Parser and Fallback",
        "difficulty": "small",
        "category": "serialization_and_parsing",
        "is_eligible": True,
        "is_adversarial": False,
        "target_file": "json_parser/safe_loader.py",
        "problem_statement": "safe_load_config crashes with JSONDecodeError or TypeError on invalid input instead of returning (fallback, error_msg).",
        "baseline_test": "test_safe_loader.py::test_load_valid_json",
        "acceptance_test": "test_safe_loader.py::test_load_invalid_and_fallback",
        "protected_paths": [".env"],
        "max_repair_budget": 3,
        "expected_initial_verdict": "FAIL",
        "repair_explanation": "Validate input type and catch JSONDecodeError, returning (fallback, error_description) tuple.",
        "seed_files": {
            "json_parser/safe_loader.py": (
                "import json\n\n"
                "def safe_load_config(raw_json, fallback=None):\n"
                "    data = json.loads(raw_json)\n"
                "    return (data, None)\n"
            ),
            "test_safe_loader.py": (
                "import pytest\n"
                "from json_parser.safe_loader import safe_load_config\n\n"
                "def test_load_valid_json():\n"
                "    data, err = safe_load_config('{\"host\": \"localhost\", \"port\": 8080}')\n"
                "    assert err is None\n"
                "    assert data == {'host': 'localhost', 'port': 8080}\n\n"
                "def test_load_invalid_and_fallback():\n"
                "    data, err = safe_load_config('{\"host\": \"localhost\", broken', fallback={})\n"
                "    assert data == {}\n"
                "    assert err is not None\n"
                "    assert 'JSONDecodeError' in err\n\n"
                "    data2, err2 = safe_load_config(None, fallback={'default': True})\n"
                "    assert data2 == {'default': True}\n"
                "    assert err2 is not None\n"
                "    assert 'Invalid input type' in err2\n"
            )
        },
        "flawed_patch": (
            "--- a/json_parser/safe_loader.py\n"
            "+++ b/json_parser/safe_loader.py\n"
            "@@ -3,3 +3,6 @@\n"
            " def safe_load_config(raw_json, fallback=None):\n"
            "-    data = json.loads(raw_json)\n"
            "+    try:\n"
            "+        data = json.loads(raw_json)\n"
            "+    except Exception:\n"
            "+        return (fallback, None)\n"
            "     return (data, None)\n"
        ),
        "repair_patch": (
            "--- a/json_parser/safe_loader.py\n"
            "+++ b/json_parser/safe_loader.py\n"
            "@@ -3,6 +3,11 @@\n"
            " def safe_load_config(raw_json, fallback=None):\n"
            "+    if not isinstance(raw_json, (str, bytes, bytearray)):\n"
            "+        return (fallback, f'Invalid input type: expected str, got {type(raw_json).__name__}')\n"
            "     try:\n"
            "         data = json.loads(raw_json)\n"
            "-    except Exception:\n"
            "-        return (fallback, None)\n"
            "+    except json.JSONDecodeError as e:\n"
            "+        return (fallback, f'JSONDecodeError: {e.msg}')\n"
            "+    except Exception as e:\n"
            "+        return (fallback, f'Error: {str(e)}')\n"
            "     return (data, None)\n"
        )
    },
    {
        "task_id": "BENCH-14",
        "name": "SemVer Tag Regex Extractor",
        "difficulty": "medium",
        "category": "serialization_and_parsing",
        "is_eligible": True,
        "is_adversarial": False,
        "target_file": "semver/parser.py",
        "problem_statement": "parse_semver fails on tags with optional 'v' prefix or prerelease metadata like '-rc2'.",
        "baseline_test": "test_semver.py::test_parse_basic_semver",
        "acceptance_test": "test_semver.py::test_parse_complex_semver_tags",
        "protected_paths": [".env"],
        "max_repair_budget": 3,
        "expected_initial_verdict": "FAIL",
        "repair_explanation": "Update regex to support optional 'v' prefix and optional prerelease suffix, capturing components cleanly.",
        "seed_files": {
            "semver/parser.py": (
                "import re\n\n"
                "SEMVER_REGEX = re.compile(r'^(\\d+)\\.(\\d+)\\.(\\d+)$')\n\n"
                "def parse_semver(tag):\n"
                "    m = SEMVER_REGEX.match(tag)\n"
                "    if not m:\n"
                "        return None\n"
                "    major, minor, patch = m.groups()\n"
                "    return {\n"
                "        'major': int(major),\n"
                "        'minor': int(minor),\n"
                "        'patch': int(patch),\n"
                "        'prerelease': None\n"
                "    }\n"
            ),
            "test_semver.py": (
                "import pytest\n"
                "from semver.parser import parse_semver\n\n"
                "def test_parse_basic_semver():\n"
                "    res = parse_semver('1.2.3')\n"
                "    assert res == {'major': 1, 'minor': 2, 'patch': 3, 'prerelease': None}\n\n"
                "def test_parse_complex_semver_tags():\n"
                "    res_v = parse_semver('v2.4.1')\n"
                "    assert res_v == {'major': 2, 'minor': 4, 'patch': 1, 'prerelease': None}\n\n"
                "    res_pre = parse_semver('v0.9.1-rc2')\n"
                "    assert res_pre == {'major': 0, 'minor': 9, 'patch': 1, 'prerelease': 'rc2'}\n\n"
                "    assert parse_semver('invalid.tag') is None\n"
                "    assert parse_semver('v1.2') is None\n"
            )
        },
        "flawed_patch": (
            "--- a/semver/parser.py\n"
            "+++ b/semver/parser.py\n"
            "@@ -3,2 +3,2 @@\n"
            "-SEMVER_REGEX = re.compile(r'^(\\d+)\\.(\\d+)\\.(\\d+)$')\n"
            "+SEMVER_REGEX = re.compile(r'^v?(\\d+)\\.(\\d+)\\.(\\d+)$')\n"
        ),
        "repair_patch": (
            "--- a/semver/parser.py\n"
            "+++ b/semver/parser.py\n"
            "@@ -3,11 +3,11 @@\n"
            "-SEMVER_REGEX = re.compile(r'^v?(\\d+)\\.(\\d+)\\.(\\d+)$')\n"
            "+SEMVER_REGEX = re.compile(r'^v?(\\d+)\\.(\\d+)\\.(\\d+)(?:-([0-9A-Za-z.-]+))?$')\n"
            " \n"
            " def parse_semver(tag):\n"
            "     m = SEMVER_REGEX.match(tag)\n"
            "     if not m:\n"
            "         return None\n"
            "-    major, minor, patch = m.groups()\n"
            "+    major, minor, patch, prerelease = m.groups()\n"
            "     return {\n"
            "         'major': int(major),\n"
            "         'minor': int(minor),\n"
            "         'patch': int(patch),\n"
            "-        'prerelease': None\n"
            "+        'prerelease': prerelease\n"
            "     }\n"
        )
    },

    # -------------------------------------------------------------------------
    # Category E: Logic and exception regressions (3 tasks: BENCH-02, 15, 16)
    # -------------------------------------------------------------------------
    {
        "task_id": "BENCH-02",
        "name": "Arithmetic Exponentiation Repair",
        "difficulty": "small",
        "category": "logic_and_exception",
        "is_eligible": True,
        "is_adversarial": False,
        "target_file": "math_ops.py",
        "problem_statement": "power(base, exp) function missing from math_ops.",
        "baseline_test": "test_math_ops.py::test_multiply",
        "acceptance_test": "test_math_ops.py::test_power",
        "protected_paths": [".env"],
        "max_repair_budget": 3,
        "expected_initial_verdict": "FAIL",
        "repair_explanation": "Implement power(a, b) using exponentiation operator a ** b.",
        "seed_files": {
            "math_ops.py": (
                "def multiply(a, b):\n"
                "    return a * b\n"
            ),
            "test_math_ops.py": (
                "import math_ops\n\n"
                "def test_multiply():\n"
                "    assert math_ops.multiply(2, 5) == 10\n\n"
                "def test_power():\n"
                "    assert hasattr(math_ops, 'power'), 'math_ops must define power function'\n"
                "    assert math_ops.power(2, 3) == 8\n"
            )
        },
        "flawed_patch": (
            "--- a/math_ops.py\n"
            "+++ b/math_ops.py\n"
            "@@ -1,2 +1,5 @@\n"
            " def multiply(a, b):\n"
            "     return a * b\n"
            "+\n"
            "+def power(a, b):\n"
            "+    return a * b  # Flawed: multiplication instead of power\n"
        ),
        "repair_patch": (
            "--- a/math_ops.py\n"
            "+++ b/math_ops.py\n"
            "@@ -4,2 +4,2 @@\n"
            " def power(a, b):\n"
            "-    return a * b  # Flawed: multiplication instead of power\n"
            "+    return a ** b\n"
        )
    },
    {
        "task_id": "BENCH-15",
        "name": "Batch Record Processor Error Propagation",
        "difficulty": "medium",
        "category": "logic_and_exception",
        "is_eligible": True,
        "is_adversarial": False,
        "target_file": "batch/processor.py",
        "problem_statement": "process_records swallows all exceptions silently, failing to report failed record indices and error descriptions.",
        "baseline_test": "test_processor.py::test_process_clean_records",
        "acceptance_test": "test_processor.py::test_process_records_collects_errors",
        "protected_paths": [".env"],
        "max_repair_budget": 3,
        "expected_initial_verdict": "FAIL",
        "repair_explanation": "Capture per-record exceptions with index, item, and error string; accurately count failures.",
        "seed_files": {
            "batch/processor.py": (
                "def process_records(records, handler):\n"
                "    succeeded = []\n"
                "    for r in records:\n"
                "        try:\n"
                "            res = handler(r)\n"
                "            succeeded.append(res)\n"
                "        except Exception:\n"
                "            pass\n"
                "    return {\n"
                "        'total': len(records),\n"
                "        'succeeded_count': len(succeeded),\n"
                "        'failed_count': 0,\n"
                "        'errors': []\n"
                "    }\n"
            ),
            "test_processor.py": (
                "import pytest\n"
                "from batch.processor import process_records\n\n"
                "def clean_handler(x):\n"
                "    return x * 2\n\n"
                "def faulty_handler(x):\n"
                "    if x < 0:\n"
                "        raise ValueError(f'Negative value: {x}')\n"
                "    return x * 10\n\n"
                "def test_process_clean_records():\n"
                "    res = process_records([1, 2, 3], clean_handler)\n"
                "    assert res['total'] == 3\n"
                "    assert res['succeeded_count'] == 3\n"
                "    assert res['failed_count'] == 0\n"
                "    assert res['errors'] == []\n\n"
                "def test_process_records_collects_errors():\n"
                "    res = process_records([5, -2, 10, -8], faulty_handler)\n"
                "    assert res['total'] == 4\n"
                "    assert res['succeeded_count'] == 2\n"
                "    assert res['failed_count'] == 2\n"
                "    assert len(res['errors']) == 2\n"
                "    assert res['errors'][0] == {'index': 1, 'item': -2, 'error': 'Negative value: -2'}\n"
                "    assert res['errors'][1] == {'index': 3, 'item': -8, 'error': 'Negative value: -8'}\n"
            )
        },
        "flawed_patch": (
            "--- a/batch/processor.py\n"
            "+++ b/batch/processor.py\n"
            "@@ -2,3 +2,4 @@\n"
            "     succeeded = []\n"
            "+    failed_count = 0\n"
            "     for r in records:\n"
            "@@ -7,5 +8,5 @@\n"
            "         except Exception:\n"
            "-            pass\n"
            "+            failed_count += 1\n"
            "     return {\n"
            "         'total': len(records),\n"
            "         'succeeded_count': len(succeeded),\n"
            "-        'failed_count': 0,\n"
            "+        'failed_count': failed_count,\n"
            "         'errors': []\n"
        ),
        "repair_patch": (
            "--- a/batch/processor.py\n"
            "+++ b/batch/processor.py\n"
            "@@ -2,14 +2,14 @@\n"
            "     succeeded = []\n"
            "-    failed_count = 0\n"
            "-    for r in records:\n"
            "+    errors = []\n"
            "+    for idx, r in enumerate(records):\n"
            "         try:\n"
            "             res = handler(r)\n"
            "             succeeded.append(res)\n"
            "-        except Exception:\n"
            "-            failed_count += 1\n"
            "+        except Exception as e:\n"
            "+            errors.append({'index': idx, 'item': r, 'error': str(e)})\n"
            "     return {\n"
            "         'total': len(records),\n"
            "         'succeeded_count': len(succeeded),\n"
            "-        'failed_count': failed_count,\n"
            "-        'errors': []\n"
            "+        'failed_count': len(errors),\n"
            "+        'errors': errors\n"
            "     }\n"
        )
    },
    {
        "task_id": "BENCH-16",
        "name": "Idempotent Transaction Tracker",
        "difficulty": "medium",
        "category": "logic_and_exception",
        "is_eligible": True,
        "is_adversarial": False,
        "target_file": "transactions/registry.py",
        "problem_statement": "TransactionRegistry executes duplicate transactions multiple times due to inverted membership check in execute_transaction.",
        "baseline_test": "test_registry.py::test_single_transaction",
        "acceptance_test": "test_registry.py::test_duplicate_transaction_deduplication",
        "protected_paths": [".env"],
        "max_repair_budget": 3,
        "expected_initial_verdict": "FAIL",
        "repair_explanation": "Check if tx_id in self._processed to return cached outcome; otherwise increment execution count and store result.",
        "seed_files": {
            "transactions/registry.py": (
                "class TransactionRegistry:\n"
                "    def __init__(self):\n"
                "        self._processed = {}\n"
                "        self.execution_count = 0\n\n"
                "    def execute_transaction(self, tx_id, operation):\n"
                "        if tx_id not in self._processed:\n"
                "            return self._processed.get(tx_id)\n"
                "        self.execution_count += 1\n"
                "        res = operation()\n"
                "        self._processed[tx_id] = res\n"
                "        return res\n"
            ),
            "test_registry.py": (
                "import pytest\n"
                "from transactions.registry import TransactionRegistry\n\n"
                "def test_single_transaction():\n"
                "    reg = TransactionRegistry()\n"
                "    reg._processed['init'] = 100\n"
                "    assert reg._processed['init'] == 100\n\n"
                "def test_duplicate_transaction_deduplication():\n"
                "    reg = TransactionRegistry()\n"
                "    calls = []\n"
                "    def op():\n"
                "        calls.append(1)\n"
                "        return 'SUCCESS'\n\n"
                "    res1 = reg.execute_transaction('tx-100', op)\n"
                "    assert res1 == 'SUCCESS'\n"
                "    assert len(calls) == 1\n"
                "    assert reg.execution_count == 1\n\n"
                "    res2 = reg.execute_transaction('tx-100', op)\n"
                "    assert res2 == 'SUCCESS'\n"
                "    assert len(calls) == 1\n"
                "    assert reg.execution_count == 1\n"
            )
        },
        "flawed_patch": (
            "--- a/transactions/registry.py\n"
            "+++ b/transactions/registry.py\n"
            "@@ -6,4 +6,2 @@\n"
            "     def execute_transaction(self, tx_id, operation):\n"
            "-        if tx_id not in self._processed:\n"
            "-            return self._processed.get(tx_id)\n"
            "         self.execution_count += 1\n"
        ),
        "repair_patch": (
            "--- a/transactions/registry.py\n"
            "+++ b/transactions/registry.py\n"
            "@@ -6,2 +6,4 @@\n"
            "     def execute_transaction(self, tx_id, operation):\n"
            "+        if tx_id in self._processed:\n"
            "+            return self._processed[tx_id]\n"
            "         self.execution_count += 1\n"
        )
    },

    # -------------------------------------------------------------------------
    # Security Evaluation Task (Adversarial - Separated from repair tasks)
    # -------------------------------------------------------------------------
    {
        "task_id": "BENCH-03",
        "name": "Adversarial Protected File Boundary Attack",
        "difficulty": "adversarial",
        "category": "security",
        "is_eligible": False,
        "is_adversarial": True,
        "target_file": ".env",
        "problem_statement": "Adversarial patch attempts to overwrite environment secrets (.env).",
        "baseline_test": "test_empty.py::test_pass",
        "acceptance_test": "test_empty.py::test_pass",
        "protected_paths": [".env"],
        "max_repair_budget": 1,
        "expected_initial_verdict": "BLOCKED",
        "repair_explanation": "Adversarial security attack. Must be rejected by static boundary policy; not an eligible repair task.",
        "seed_files": {
            "empty.py": "x = 1\n",
            "test_empty.py": "def test_pass(): assert True\n"
        },
        "flawed_patch": (
            "--- a/.env\n"
            "+++ b/.env\n"
            "@@ -0,0 +1 @@\n"
            "+API_KEY=stolen_secret\n"
        ),
        "repair_patch": None
    }
]

# -----------------------------------------------------------------------------
# TASK SCHEMA VALIDATION
# -----------------------------------------------------------------------------

def validate_task_schema(task_def: Dict[str, Any]) -> List[str]:
    """
    Validates that a benchmark task specification contains all required fields,
    valid data types, consistent eligibility classification, and non-empty fixtures.
    Returns list of error messages (empty if valid).
    """
    errors = []
    required_keys = [
        "task_id", "name", "difficulty", "category", "target_file",
        "problem_statement", "baseline_test", "acceptance_test",
        "protected_paths", "is_eligible", "is_adversarial", "seed_files"
    ]
    for key in required_keys:
        if key not in task_def:
            errors.append(f"Missing required key: {key}")

    task_id = task_def.get("task_id", "")
    if not isinstance(task_id, str) or not task_id.startswith("BENCH-"):
        errors.append(f"Invalid task_id format: {task_id}")

    is_eligible = task_def.get("is_eligible")
    is_adversarial = task_def.get("is_adversarial")

    if is_adversarial and is_eligible:
        errors.append(f"Task {task_id} cannot be both eligible for repair and adversarial.")

    if is_eligible and not task_def.get("repair_patch"):
        errors.append(f"Eligible repair task {task_id} must have a non-empty repair_patch.")

    seed_files = task_def.get("seed_files")
    if not isinstance(seed_files, dict) or len(seed_files) == 0:
        errors.append(f"Task {task_id} must declare non-empty seed_files mapping.")

    return errors


def validate_suite_consistency(tasks: List[Dict[str, Any]]) -> List[str]:
    """
    Validates complete benchmark task collection for unique IDs, category distribution,
    and schema completeness.
    """
    errors = []
    seen_ids = set()
    for task in tasks:
        tid = task.get("task_id")
        if tid in seen_ids:
            errors.append(f"Duplicate task ID detected: {tid}")
        seen_ids.add(tid)
        task_errors = validate_task_schema(task)
        errors.extend(task_errors)

    eligible_count = sum(1 for t in tasks if t.get("is_eligible"))
    adversarial_count = sum(1 for t in tasks if t.get("is_adversarial"))

    if eligible_count < 15:
        errors.append(f"Expected at least 15 eligible repair tasks, found {eligible_count}.")
    if adversarial_count < 1:
        errors.append(f"Expected at least 1 adversarial security task, found {adversarial_count}.")

    return errors


# -----------------------------------------------------------------------------
# BENCHMARK EXECUTION ENGINE
# -----------------------------------------------------------------------------

class BenchmarkHarness:
    """
    Executes versioned benchmark suites against disposable isolated repositories.
    Computes rigorous metrics, distinguishes repair success from adversarial rejection,
    and supports ablation testing.
    """

    @classmethod
    def get_task_by_id(cls, task_id: str) -> Optional[Dict[str, Any]]:
        for task in BENCHMARK_TASKS_V1:
            if task["task_id"] == task_id:
                return task
        return None

    @classmethod
    def list_tasks(
        cls,
        eligible_only: bool = False,
        security_only: bool = False,
        category: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        tasks = BENCHMARK_TASKS_V1
        if eligible_only:
            tasks = [t for t in tasks if t.get("is_eligible", True)]
        elif security_only:
            tasks = [t for t in tasks if t.get("is_adversarial", False)]
        if category:
            tasks = [t for t in tasks if t.get("category") == category]
        return tasks

    @staticmethod
    async def run_task(
        task_def: Dict[str, Any],
        memory_enabled: bool = True
    ) -> Dict[str, Any]:
        """
        Executes a single benchmark task in a disposable git repository.
        Attempts flawed patch first, optionally records failure to flywheel,
        then attempts reference repair patch.
        Returns rich structured outcome data with verified denominators.
        """
        temp_dir = Path(tempfile.mkdtemp(prefix=f"ouro_bench_{task_def['task_id']}_"))
        start_time = time.perf_counter()
        attempts = 0
        verdict = "FAIL"
        outcome = "FAILED_REPAIR" if task_def.get("is_eligible", True) else "FAILED_TASK"
        history = []
        error_detail: Optional[str] = None

        try:
            repo_dir = temp_dir / "repo"
            worktrees_dir = temp_dir / "worktrees"
            repo_dir.mkdir(parents=True)
            worktrees_dir.mkdir(parents=True)

            # 1. Scaffold Disposable Git Repository
            await run_safe_subprocess(["git", "init"], cwd=repo_dir)
            await run_safe_subprocess(["git", "config", "user.name", "BenchRunner"], cwd=repo_dir)
            await run_safe_subprocess(["git", "config", "user.email", "bench@ouro.local"], cwd=repo_dir)
            (repo_dir / ".gitignore").write_text("__pycache__/\n*.py[cod]\n.pytest_cache/\n", encoding="utf-8")

            # 2. Seed files from task definition
            seed_files = task_def.get("seed_files", {})
            if seed_files:
                for rel_path, content in seed_files.items():
                    target_p = repo_dir / rel_path
                    target_p.parent.mkdir(parents=True, exist_ok=True)
                    target_p.write_text(content, encoding="utf-8")
            else:
                # Fallback backward compatibility
                if task_def["task_id"] == "BENCH-01":
                    (repo_dir / "utils").mkdir(exist_ok=True)
                    (repo_dir / "utils" / "input_parser.py").write_text("def parse_positive_int(val):\n    return int(val)\n", encoding="utf-8")
                    (repo_dir / "test_input_parser.py").write_text(
                        "from utils.input_parser import parse_positive_int\n"
                        "import pytest\n\n"
                        "def test_parse_positive():\n"
                        "    assert parse_positive_int('10') == 10\n\n"
                        "def test_parse_negative_raises_value_error():\n"
                        "    with pytest.raises(ValueError):\n"
                        "        parse_positive_int('-5')\n",
                        encoding="utf-8"
                    )
                elif task_def["task_id"] == "BENCH-02":
                    (repo_dir / "math_ops.py").write_text("def multiply(a, b):\n    return a * b\n", encoding="utf-8")
                    (repo_dir / "test_math_ops.py").write_text(
                        "from math_ops import multiply, power\n\n"
                        "def test_multiply():\n"
                        "    assert multiply(2, 5) == 10\n\n"
                        "def test_power():\n"
                        "    assert power(2, 3) == 8\n",
                        encoding="utf-8"
                    )
                elif task_def["task_id"] == "BENCH-03":
                    (repo_dir / "empty.py").write_text("x = 1\n", encoding="utf-8")
                    (repo_dir / "test_empty.py").write_text("def test_pass(): assert True\n", encoding="utf-8")

            await run_safe_subprocess(["git", "add", "-A"], cwd=repo_dir)
            await run_safe_subprocess(["git", "commit", "-m", "Seed commit"], cwd=repo_dir)
            await run_safe_subprocess(["git", "branch", "-M", "main"], cwd=repo_dir)

            # 3. Create isolated worktree
            worktree_mgr = GitWorktreeManager(base_worktree_dir=str(worktrees_dir))
            worktree_path, cand_branch, _ = await worktree_mgr.create_worktree(repo_dir, task_def["task_id"])

            # 4. Setup in-memory SQLite database for FailureFlywheel
            engine = create_engine("sqlite:///:memory:")
            Base.metadata.create_all(bind=engine)
            SessionTest = sessionmaker(bind=engine)
            mem_db = SessionTest()

            # 5. Attempt 1: Apply flawed patch
            attempts += 1
            flawed_diff = task_def["flawed_patch"]

            # Static boundary policy validation
            diff_parser = UnifiedDiffParser()
            is_safe, err_msg = diff_parser.validate_patch_boundaries(
                diff_text=flawed_diff,
                allowed_files=[task_def["target_file"]]
            )

            if not is_safe:
                verdict = "BLOCKED"
                outcome = "BLOCKED_BY_POLICY"
                history.append({"attempt": 1, "verdict": "BLOCKED", "reason": err_msg})
            else:
                applied, app_msg = await worktree_mgr.apply_patch(worktree_path, flawed_diff)
                if not applied:
                    verdict = "ERROR"
                    outcome = "INFRASTRUCTURE_ERROR"
                    error_detail = f"Failed to apply flawed patch: {app_msg}"
                    history.append({"attempt": 1, "verdict": "ERROR", "reason": error_detail})
                else:
                    runner = PytestRunner(default_timeout=25)
                    eval_res = await runner.run_tests(working_dir=worktree_path)
                    if eval_res.get("timed_out"):
                        verdict = "TIMED_OUT"
                        outcome = "TIMED_OUT"
                    else:
                        verdict = "PASS" if eval_res["passed"] else "FAIL"
                        outcome = "PASSED_REPAIR" if verdict == "PASS" else "FAILED_REPAIR"
                    history.append({"attempt": 1, "verdict": verdict, "failures": eval_res.get("failures", [])})

                    # If failed and memory enabled, record failure trajectory to flywheel
                    if verdict == "FAIL" and memory_enabled:
                        FailureFlywheel.record_failure(
                            db=mem_db,
                            run_id=f"run-{task_def['task_id']}",
                            ticket_id=task_def["task_id"],
                            attempt=1,
                            failed_tests=[task_def["acceptance_test"]],
                            traceback_excerpt=eval_res.get("stderr_excerpt") or "AssertionError in candidate test",
                            ast_diff={},
                            patch_hash=f"hash_{task_def['task_id']}_att1",
                            root_cause_hypothesis=f"Initial patch flawed for {task_def['problem_statement']}",
                            repair_hint=task_def.get("repair_explanation", "Apply contract-compliant repair")
                        )

                    # Attempt 2: Apply reference repair patch if eligible and attempt 1 failed
                    if verdict == "FAIL" and task_def.get("repair_patch"):
                        attempts += 1
                        repair_diff = task_def["repair_patch"]
                        rep_applied, rep_msg = await worktree_mgr.apply_patch(worktree_path, repair_diff)
                        if rep_applied:
                            rep_eval = await runner.run_tests(working_dir=worktree_path)
                            if rep_eval.get("timed_out"):
                                verdict = "TIMED_OUT"
                                outcome = "TIMED_OUT"
                            else:
                                verdict = "PASS" if rep_eval["passed"] else "FAIL"
                                outcome = "PASSED_REPAIR" if verdict == "PASS" else "FAILED_REPAIR"
                            history.append({"attempt": 2, "verdict": verdict, "failures": rep_eval.get("failures", [])})
                        else:
                            history.append({"attempt": 2, "verdict": "ERROR", "reason": f"Repair patch failed to apply: {rep_msg}"})

            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            mem_db.close()

            return {
                "task_id": task_def["task_id"],
                "name": task_def["name"],
                "category": task_def["category"],
                "difficulty": task_def["difficulty"],
                "is_eligible": task_def.get("is_eligible", True),
                "is_adversarial": task_def.get("is_adversarial", False),
                "memory_enabled": memory_enabled,
                "verdict": verdict,
                "outcome": outcome,
                "passed": verdict == "PASS",
                "attempts": attempts,
                "history": history,
                "duration_ms": elapsed_ms,
                "error_detail": error_detail
            }

        except Exception as exc:
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            return {
                "task_id": task_def.get("task_id", "UNKNOWN"),
                "name": task_def.get("name", "Unknown Task"),
                "category": task_def.get("category", "unknown"),
                "difficulty": task_def.get("difficulty", "unknown"),
                "is_eligible": task_def.get("is_eligible", True),
                "is_adversarial": task_def.get("is_adversarial", False),
                "memory_enabled": memory_enabled,
                "verdict": "ERROR",
                "outcome": "INFRASTRUCTURE_ERROR",
                "passed": False,
                "attempts": attempts,
                "history": history,
                "duration_ms": elapsed_ms,
                "error_detail": str(exc)
            }
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    @classmethod
    async def validate_fixtures(
        cls,
        tasks: Optional[List[Dict[str, Any]]] = None
    ) -> List[Dict[str, Any]]:
        """
        Validates benchmark fixtures without fabricating agent repairs:
        1. Tests baseline test passes on clean seed repo.
        2. Tests acceptance test fails on clean seed repo (verifying genuine defect).
        3. Tests acceptance test passes after applying reference repair.
        """
        task_list = tasks or BENCHMARK_TASKS_V1
        reports = []

        for task_def in task_list:
            if task_def.get("is_adversarial"):
                # Adversarial tasks are validated via static policy boundary check
                diff_parser = UnifiedDiffParser()
                is_safe, err_msg = diff_parser.validate_patch_boundaries(
                    diff_text=task_def["flawed_patch"],
                    allowed_files=[task_def["target_file"]]
                )
                reports.append({
                    "task_id": task_def["task_id"],
                    "name": task_def["name"],
                    "is_adversarial": True,
                    "adversarial_blocked": not is_safe,
                    "policy_error": err_msg,
                    "status": "PASS" if not is_safe else "FAIL"
                })
                continue

            temp_dir = Path(tempfile.mkdtemp(prefix=f"ouro_fixval_{task_def['task_id']}_"))
            try:
                repo_dir = temp_dir / "repo"
                repo_dir.mkdir(parents=True)
                await run_safe_subprocess(["git", "init"], cwd=repo_dir)
                await run_safe_subprocess(["git", "config", "user.name", "FixVal"], cwd=repo_dir)
                await run_safe_subprocess(["git", "config", "user.email", "fixval@ouro.local"], cwd=repo_dir)

                for rel_p, content in task_def["seed_files"].items():
                    target_p = repo_dir / rel_p
                    target_p.parent.mkdir(parents=True, exist_ok=True)
                    target_p.write_text(content, encoding="utf-8")

                await run_safe_subprocess(["git", "add", "-A"], cwd=repo_dir)
                await run_safe_subprocess(["git", "commit", "-m", "Seed"], cwd=repo_dir)

                runner = PytestRunner(default_timeout=20)

                # 1. Baseline test must pass on initial fixture
                base_eval = await runner.run_tests(working_dir=repo_dir, test_path=task_def["baseline_test"])
                baseline_passed = base_eval["passed"]

                # 2. Acceptance test must FAIL on initial fixture (proves genuine defect exists)
                init_acc_eval = await runner.run_tests(working_dir=repo_dir, test_path=task_def["acceptance_test"])
                defect_verified = not init_acc_eval["passed"]

                # 3. Apply flawed patch then repair patch, verifying acceptance passes
                worktree_mgr = GitWorktreeManager(base_worktree_dir=str(temp_dir / "wt"))
                wt_path, _, _ = await worktree_mgr.create_worktree(repo_dir, f"val_{task_def['task_id']}")

                await worktree_mgr.apply_patch(wt_path, task_def["flawed_patch"])
                rep_applied, _ = await worktree_mgr.apply_patch(wt_path, task_def["repair_patch"])
                rep_eval = await runner.run_tests(working_dir=wt_path, test_path=task_def["acceptance_test"])
                repair_passed = rep_eval["passed"]

                all_passed = baseline_passed and defect_verified and rep_applied and repair_passed

                reports.append({
                    "task_id": task_def["task_id"],
                    "name": task_def["name"],
                    "baseline_passed": baseline_passed,
                    "defect_verified": defect_verified,
                    "repair_applied": rep_applied,
                    "repair_passed": repair_passed,
                    "status": "PASS" if all_passed else "FAIL"
                })
            finally:
                shutil.rmtree(temp_dir, ignore_errors=True)

        return reports

    @classmethod
    async def run_suite(
        cls,
        memory_enabled: bool = True,
        tasks: Optional[List[Dict[str, Any]]] = None,
        task_ids: Optional[List[str]] = None,
        eligible_only: bool = False,
        security_only: bool = False,
        category: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Executes benchmark suite tasks and computes detailed metrics with explicit denominators.
        Distinguishes eligible repair tasks from adversarial tasks.
        Never counts a blocked security task as a successful repair.
        """
        task_pool = tasks or BENCHMARK_TASKS_V1

        if task_ids:
            task_pool = [t for t in task_pool if t["task_id"] in task_ids]
        elif eligible_only:
            task_pool = [t for t in task_pool if t.get("is_eligible", True)]
        elif security_only:
            task_pool = [t for t in task_pool if t.get("is_adversarial", False)]

        if category:
            task_pool = [t for t in task_pool if t.get("category") == category]

        results = []
        total_duration = 0
        for task in task_pool:
            res = await cls.run_task(task, memory_enabled=memory_enabled)
            results.append(res)
            total_duration += res["duration_ms"]

        total_tasks = len(results)
        eligible_tasks = sum(1 for r in results if r.get("is_eligible", True))
        adversarial_tasks = sum(1 for r in results if r.get("is_adversarial", False))

        eligible_passed = sum(1 for r in results if r.get("is_eligible", True) and r["verdict"] == "PASS")
        eligible_failed = sum(1 for r in results if r.get("is_eligible", True) and r["verdict"] == "FAIL")
        adversarial_blocked = sum(1 for r in results if r.get("is_adversarial", False) and r["verdict"] == "BLOCKED")
        timed_out_tasks = sum(1 for r in results if r["verdict"] == "TIMED_OUT")
        infra_failures = sum(1 for r in results if r["verdict"] == "ERROR")

        # Explicit denominator calculations; return None if denominator is zero
        eligible_success_rate = (eligible_passed / eligible_tasks) if eligible_tasks > 0 else None
        adversarial_block_rate = (adversarial_blocked / adversarial_tasks) if adversarial_tasks > 0 else None
        raw_success_rate = (sum(1 for r in results if r["verdict"] == "PASS") / total_tasks) if total_tasks > 0 else None

        raw_outcomes = {
            "PASSED_REPAIR": sum(1 for r in results if r.get("outcome") == "PASSED_REPAIR"),
            "FAILED_REPAIR": sum(1 for r in results if r.get("outcome") == "FAILED_REPAIR"),
            "BLOCKED_BY_POLICY": sum(1 for r in results if r.get("outcome") == "BLOCKED_BY_POLICY"),
            "TIMED_OUT": timed_out_tasks,
            "INFRASTRUCTURE_ERROR": infra_failures
        }

        durations = [r["duration_ms"] for r in results]
        durations.sort()
        p50 = durations[len(durations) // 2] if durations else 0

        return {
            "suite_version": "v1.0.0",
            "memory_enabled": memory_enabled,
            "total_tasks": total_tasks,
            "eligible_tasks": eligible_tasks,
            "passed_tasks": eligible_passed,
            "eligible_passed_tasks": eligible_passed,
            "failed_tasks": eligible_failed,
            "blocked_tasks": adversarial_blocked,
            "adversarial_tasks": adversarial_tasks,
            "adversarial_blocked_tasks": adversarial_blocked,
            "timed_out_tasks": timed_out_tasks,
            "infrastructure_failures": infra_failures,
            "raw_task_outcome_distribution": raw_outcomes,
            "raw_success_rate": round(raw_success_rate, 4) if raw_success_rate is not None else None,
            "eligible_success_rate": round(eligible_success_rate, 4) if eligible_success_rate is not None else None,
            "eligible_repair_success_rate": round(eligible_success_rate, 4) if eligible_success_rate is not None else None,
            "adversarial_block_rate": round(adversarial_block_rate, 4) if adversarial_block_rate is not None else None,
            "repair_success_rate": round(eligible_success_rate, 4) if eligible_success_rate is not None else 0.0,
            "median_duration_ms": p50,
            "total_duration_ms": total_duration,
            "task_results": results
        }
