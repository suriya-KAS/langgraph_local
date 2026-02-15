"""
Pure-matplotlib version of the LangGraph architecture diagrams.

No Graphviz binaries are required.

Usage:
    pip install matplotlib
    python graph.py

This will generate:
    - main_graph.png
    - analytics_graph.png
in the current directory.
"""

import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, FancyArrow


def _add_box(ax, xy, width, height, text, facecolor="#b0b0b0"):
    """Helper to add a labeled rectangle."""
    x, y = xy
    rect = Rectangle((x, y), width, height,
                     facecolor=facecolor, edgecolor="black")
    ax.add_patch(rect)
    ax.text(
        x + width / 2,
        y + height / 2,
        text,
        ha="center",
        va="center",
        fontsize=9,
        wrap=True,
    )
    return rect


def _add_arrow(ax, start, end, text=None, style="simple", linestyle="-"):
    """Helper to add an arrow with optional label."""
    x1, y1 = start
    x2, y2 = end
    arrow = FancyArrow(
        x1,
        y1,
        x2 - x1,
        y2 - y1,
        width=0.02,
        head_width=0.15,
        head_length=0.25,
        length_includes_head=True,
        linewidth=0.8,
        linestyle=linestyle,
        color="black",
    )
    ax.add_patch(arrow)

    if text:
        tx = (x1 + x2) / 2
        ty = (y1 + y2) / 2 + 0.15
        ax.text(tx, ty, text, ha="center", va="bottom", fontsize=7, wrap=True)


def build_main_graph_png(filename: str = "main_graph.png") -> None:
    """Draw the main orchestrator + subgraph overview."""
    fig, ax = plt.subplots(figsize=(10, 4))

    # Coordinates layout (x, y) with y increasing upwards
    box_w, box_h = 1.8, 1.0

    # Nodes
    start_pos = (0.0, 0.0)
    uie_pos = (2.2, 0.0)
    router_pos = (4.4, 0.0)

    analytics_pos = (6.8, 1.5)
    pd_pos = (6.8, 0.5)
    rec_pos = (6.8, -0.5)
    oos_pos = (6.8, -1.5)

    assembler_pos = (9.2, 0.0)
    end_pos = (11.4, 0.0)

    _add_box(ax, start_pos, box_w, box_h, "Start\n(user input)", "#d0d0d0")
    _add_box(ax, uie_pos, box_w, box_h, "User Intent\nEnricher")
    _add_box(ax, router_pos, box_w, box_h, "Intent Router /\nOrchestrator", "#a0a0a0")

    _add_box(ax, analytics_pos, box_w, box_h, "Analytics\nSubgraph", "#c0e0ff")
    _add_box(ax, pd_pos, box_w, box_h, "Product Detail\nSubgraph", "#c0e0ff")
    _add_box(ax, rec_pos, box_w, box_h, "Recommendation\nSubgraph", "#c0e0ff")
    _add_box(ax, oos_pos, box_w, box_h, "Out Of Scope\nSubgraph", "#c0e0ff")

    _add_box(ax, assembler_pos, box_w, box_h, "Response\nAssembler", "#d0d0d0")
    _add_box(ax, end_pos, box_w, box_h, "Final\nanswer", "#d0ffd0")

    # Arrow anchor points (center of right/left sides)
    def right_center(pos):
        return (pos[0] + box_w, pos[1] + box_h / 2)

    def left_center(pos):
        return (pos[0], pos[1] + box_h / 2)

    # Edges
    _add_arrow(
        ax,
        right_center(start_pos),
        left_center(uie_pos),
        "State: user_query",
    )
    _add_arrow(
        ax,
        right_center(uie_pos),
        left_center(router_pos),
        "State: +intent",
    )

    _add_arrow(
        ax,
        right_center(router_pos),
        left_center(analytics_pos),
        "if intent == analytics_reporting",
    )
    _add_arrow(
        ax,
        right_center(router_pos),
        left_center(pd_pos),
        "if intent == product_detail",
    )
    _add_arrow(
        ax,
        right_center(router_pos),
        left_center(rec_pos),
        "if intent == recommendation",
    )
    _add_arrow(
        ax,
        right_center(router_pos),
        left_center(oos_pos),
        "fallback / oos",
    )

    _add_arrow(
        ax,
        right_center(analytics_pos),
        left_center(assembler_pos),
        "State: +analytics_insights\n(+product_suggestions?)",
    )
    _add_arrow(
        ax,
        right_center(pd_pos),
        left_center(assembler_pos),
        "State: +product_detail",
    )
    _add_arrow(
        ax,
        right_center(rec_pos),
        left_center(assembler_pos),
        "State: +recommendations",
    )
    _add_arrow(
        ax,
        right_center(oos_pos),
        left_center(assembler_pos),
        "State: +oos_reason",
    )

    _add_arrow(
        ax,
        right_center(assembler_pos),
        left_center(end_pos),
        "compose from state.*",
    )

    # Final styling
    ax.set_xlim(-0.5, 13.0)
    ax.set_ylim(-2.5, 3.0)
    ax.axis("off")
    plt.tight_layout()
    fig.savefig(filename, dpi=150)
    plt.close(fig)


def build_analytics_graph_png(filename: str = "analytics_graph.png") -> None:
    """Draw the analytics subgraph with product-detail helper."""
    fig, ax = plt.subplots(figsize=(10, 3.5))

    box_w, box_h = 2.0, 1.0

    entry_pos = (0.0, 0.0)
    ws_pos = (2.4, 0.0)
    analytics_pos = (4.8, 0.0)
    pd_helper_pos = (7.2, 1.0)
    assembler_pos = (7.2, -1.0)
    exit_pos = (9.6, -1.0)

    _add_box(ax, entry_pos, box_w, box_h, "Entry from\nIntent Router", "#c0e0ff")
    _add_box(ax, ws_pos, box_w, box_h, "Work Status\nValidator\n(+enrich query)")
    _add_box(ax, analytics_pos, box_w, box_h, "Analytics\nReporting Agent")
    _add_box(ax, pd_helper_pos, box_w, box_h, "Product Detail\nHelper\n(uses analytics context)")
    _add_box(ax, assembler_pos, box_w, box_h, "Analytics\nResponse Assembler", "#d0d0d0")
    _add_box(ax, exit_pos, box_w, box_h, "Return to\nMain Graph", "#c0e0ff")

    def right_center(pos):
        return (pos[0] + box_w, pos[1] + box_h / 2)

    def left_center(pos):
        return (pos[0], pos[1] + box_h / 2)

    # Edges
    _add_arrow(
        ax,
        right_center(entry_pos),
        left_center(ws_pos),
        "State: user_query,\nintent == analytics_reporting",
    )
    _add_arrow(
        ax,
        right_center(ws_pos),
        left_center(analytics_pos),
        "State: +work_status",
    )

    # Optional branch to product-detail helper
    _add_arrow(
        ax,
        right_center(analytics_pos),
        left_center(pd_helper_pos),
        "if analytics_insights\nneeds suggestions",
    )

    # From analytics directly to assembler (dashed)
    _add_arrow(
        ax,
        right_center(analytics_pos),
        left_center(assembler_pos),
        "else",
        linestyle="--",
    )

    _add_arrow(
        ax,
        right_center(pd_helper_pos),
        left_center(assembler_pos),
        "State: +product_suggestions",
    )

    _add_arrow(
        ax,
        right_center(assembler_pos),
        left_center(exit_pos),
        "State: +analytics_insights,\n+product_suggestions?",
    )

    ax.set_xlim(-0.5, 11.0)
    ax.set_ylim(-2.5, 2.8)
    ax.axis("off")
    plt.tight_layout()
    fig.savefig(filename, dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    build_main_graph_png("main_graph.png")
    build_analytics_graph_png("analytics_graph.png")
    print("main_graph.png and analytics_graph.png have been written to the current directory.")
