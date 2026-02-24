"""
Show LangGraph structure as an image.

Builds the current chatbot workflow, renders its graph to a PNG,
saves it to the project root (or a given path), and opens it in the
default image viewer.

Usage:
    python scripts/show_langgraph_structure.py
    python scripts/show_langgraph_structure.py -o my_graph.png
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Render LangGraph workflow as PNG and open it.")
    parser.add_argument(
        "-o", "--output",
        default=None,
        help="Output PNG path (default: langgraph_structure.png in project root)",
    )
    args = parser.parse_args()

    out_path = Path(args.output) if args.output else project_root / "langgraph_structure.png"
    out_path = out_path.resolve()

    # Build workflow and get graph
    from src.graph.workflow import build_workflow

    print("Building workflow…")
    workflow = build_workflow()
    graph = workflow.get_graph()

    print("Rendering graph to PNG…")
    png_bytes = graph.draw_mermaid_png()

    out_path.write_bytes(png_bytes)
    print(f"Saved: {out_path}")

    # Open with default viewer
    import platform
    import subprocess

    system = platform.system()
    if system == "Darwin":
        subprocess.run(["open", str(out_path)], check=True)
    elif system == "Linux":
        subprocess.run(["xdg-open", str(out_path)], check=True)
    elif system == "Windows":
        subprocess.run(["start", "", str(out_path)], shell=True, check=True)
    else:
        print("Open the file manually:", out_path)

    return 0


if __name__ == "__main__":
    sys.exit(main())

#python3 scripts/show_langgraph_structure.py -o my_graph.png