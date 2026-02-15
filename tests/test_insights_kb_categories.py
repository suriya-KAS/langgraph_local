"""
Test: Insights KB category resolution from categories_dataset.json.

When user asks questions about categories, performs operations on the `rows` field,
returns all matching leaf nodes, and passes them to the LLM to generate a human response.
"""
import asyncio
import json
import os
import sys
import pytest
from typing import List, Dict, Any

# Project root for importing src.categories.insights_kb
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# Path to dataset
DATASET_PATH = os.path.join(os.path.dirname(__file__), "categories_dataset.json")

# Schema indices from taxonomy_test_nodes.tuple_schema
ROOT_NODE_IDX = 0
SUB_CATEGORY_IDX = 1
LEAF_NODE_IDX = 2
DEPTH_LEVEL_IDX = 3
EXAMPLE_ID_IDX = 4
METADATA_RULES_IDX = 5


def load_dataset() -> Dict[str, Any]:
    """Load categories_dataset.json."""
    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def rows_to_leaf_nodes(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Get all leaf nodes from taxonomy_test_nodes.rows using tuple_schema.
    Each row is one leaf; full path = root_node > sub_category > leaf_node.
    """
    taxonomy = data.get("taxonomy_test_nodes", {})
    schema = taxonomy.get("tuple_schema", [])
    rows = taxonomy.get("rows", [])

    leaf_nodes = []
    for row in rows:
        if len(row) < 3:
            continue
        root = row[ROOT_NODE_IDX]
        sub = row[SUB_CATEGORY_IDX]
        leaf = row[LEAF_NODE_IDX]
        full_path = f"{root} > {sub} > {leaf}"
        leaf_nodes.append({
            "full_path": full_path,
            "root_node": root,
            "sub_category": sub,
            "leaf_node": leaf,
            "depth_level": row[DEPTH_LEVEL_IDX] if len(row) > DEPTH_LEVEL_IDX else None,
            "example_id": row[EXAMPLE_ID_IDX] if len(row) > EXAMPLE_ID_IDX else None,
            "metadata_rules": row[METADATA_RULES_IDX] if len(row) > METADATA_RULES_IDX else None,
            "row": row,
        })
    return leaf_nodes


def get_leaf_nodes_for_query(data: Dict[str, Any], category_name: str) -> List[Dict[str, Any]]:
    """
    Given any category name, return all leaf nodes that match.

    Matches if category_name (case-insensitive) appears anywhere in the path:
    root_node, sub_category, leaf_node, or the full path string.
    So any category name (e.g. "Electronics", "Laptop", "Gaming", "Footwear")
    returns all leaf nodes under that category.
    """
    all_leaves = rows_to_leaf_nodes(data)
    q = category_name.lower().strip()
    if not q:
        return all_leaves
    return [
        node for node in all_leaves
        if q in node["root_node"].lower()
        or q in node["sub_category"].lower()
        or q in node["leaf_node"].lower()
        or q in node["full_path"].lower()
    ]


def get_human_response_for_category(category_name: str) -> str:
    """
    When user asks for a root/category node:
    1. Load dataset and get all matching leaf nodes.
    2. Pass to InsightsKBCategory.process_query.
    3. Return the reply (includes content + components for UI).
    """
    from src.categories.insights_kb import InsightsKBCategory

    category = InsightsKBCategory()
    result = asyncio.run(category.process_query(category_name, context={}))
    return result["reply"]


# --- Tests ---


def test_load_dataset():
    """Dataset loads and has taxonomy_test_nodes with rows."""
    data = load_dataset()
    assert "taxonomy_test_nodes" in data
    assert "tuple_schema" in data["taxonomy_test_nodes"]
    assert "rows" in data["taxonomy_test_nodes"]
    assert len(data["taxonomy_test_nodes"]["rows"]) >= 1


def test_rows_to_leaf_nodes_returns_all_leaves():
    """All rows are converted to leaf node dicts with full_path."""
    data = load_dataset()
    leaves = rows_to_leaf_nodes(data)
    rows = data["taxonomy_test_nodes"]["rows"]
    assert len(leaves) == len(rows)
    for node in leaves:
        assert "full_path" in node
        assert " > " in node["full_path"]
        assert node["root_node"] and node["sub_category"] and node["leaf_node"]


def test_get_leaf_nodes_for_query_laptop():
    """Query 'laptop' returns only laptop-related leaf nodes."""
    data = load_dataset()
    matches = get_leaf_nodes_for_query(data, "laptop")
    assert len(matches) >= 1
    for node in matches:
        path_lower = node["full_path"].lower()
        assert "laptop" in path_lower


def test_get_leaf_nodes_for_query_footwear():
    """Query 'footwear' returns Fashion > Footwear leaf."""
    data = load_dataset()
    matches = get_leaf_nodes_for_query(data, "footwear")
    assert len(matches) >= 1
    assert any("Footwear" in n["full_path"] for n in matches)


def test_get_leaf_nodes_for_query_electronics():
    """Query 'electronics' returns all Electronics leaf nodes."""
    data = load_dataset()
    matches = get_leaf_nodes_for_query(data, "electronics")
    assert len(matches) >= 1
    for node in matches:
        assert "Electronics" in node["root_node"]


def test_get_leaf_nodes_for_query_empty_returns_all():
    """Empty query returns all leaf nodes."""
    data = load_dataset()
    all_leaves = rows_to_leaf_nodes(data)
    from_empty = get_leaf_nodes_for_query(data, "")
    assert len(from_empty) == len(all_leaves)


def test_get_leaf_nodes_for_query_no_match_returns_empty():
    """Query with no match returns empty list."""
    data = load_dataset()
    matches = get_leaf_nodes_for_query(data, "xyznonexistentcategory123")
    assert matches == []


def test_leaf_node_structure():
    """Each leaf node has full_path, root_node, sub_category, leaf_node, depth, example_id, metadata_rules."""
    data = load_dataset()
    leaves = rows_to_leaf_nodes(data)
    assert len(leaves) > 0
    first = leaves[0]
    assert first["full_path"] == "Electronics > Laptops & Computing > RTX 4090 Series Gaming Units"
    assert first["root_node"] == "Electronics"
    assert first["sub_category"] == "Laptops & Computing"
    assert first["leaf_node"] == "RTX 4090 Series Gaming Units"
    assert first["depth_level"] == 3
    assert first["example_id"] == "e1"


@pytest.mark.parametrize("category_name", [
    "Electronics",
    "Laptop",
    "Fashion",
    "Footwear",
    "Luggage",
    "Industrial",
    "Home",
    "Kitchen",
    "Security",
    "Gaming",
    "Travel",
    "Formal",
    "Office",
    "Bakery",
    "RAM",
    "Motherboard",
])
def test_any_category_name_returns_matching_leaf_nodes(category_name: str):
    """Any category name returns all leaf nodes that contain that name in the path."""
    data = load_dataset()
    leaves = get_leaf_nodes_for_query(data, category_name)
    q = category_name.lower()
    if leaves:
        for node in leaves:
            path_lower = node["full_path"].lower()
            assert q in path_lower, f"Expected '{category_name}' in path: {node['full_path']}"
    # If no match, that's valid (e.g. "Office" might match "Office Supplies" or "Rolling Office Bags")
    # We only assert that when we get results, every result contains the category name
    assert isinstance(leaves, list)


def test_get_human_response_for_category_electronics():
    """Asking for root 'Electronics' returns human LLM response that includes the category and leaf list."""
    response = get_human_response_for_category("Electronics")
    assert isinstance(response, str)
    assert len(response) > 0
    assert "electronics" in response.lower()
    # Should mention selection or categories (LLM asks which to explore)
    assert "category" in response.lower() or "categories" in response.lower() or "explore" in response.lower()


def test_get_human_response_for_category_no_match():
    """Asking for a non-existent category returns a friendly message without calling LLM."""
    response = get_human_response_for_category("xyznonexistent123")
    assert "couldn't find" in response.lower() or "try another" in response.lower()
    assert "xyznonexistent123" in response


if __name__ == "__main__":
    category_name = sys.argv[1] if len(sys.argv) > 1 else ""
    if not category_name:
        print("Usage: python test_insights_kb_categories.py <category_name>")
        print("Example: python test_insights_kb_categories.py Electronics")
        print("\nGets leaf nodes for that category and prints LLM-generated human response.")
        sys.exit(0)

    response = get_human_response_for_category(category_name)
    print(response)
