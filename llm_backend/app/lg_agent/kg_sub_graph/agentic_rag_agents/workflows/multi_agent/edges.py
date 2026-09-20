"""LangGraph edges that are used in multiple workflows."""

from typing import Any, Dict, List, Literal

from langgraph.types import Send

from ...components.state import OverallState, ToolSelectionOutputState
from ...components.text2cypher.state import CypherOutputState


def guardrails_conditional_edge(
    state: OverallState,
) -> Literal["planner", "final_answer"]:
    match state.get("next_action"):
        case "final_answer":
            return "final_answer"
        case "end":
            return "final_answer"
        case "planner":
            return "planner"
        case _:
            return "final_answer"


def tool_select_conditional_edge(
    state: OverallState,
) -> Literal["summarize", "final_answer"]:
    match state.get("next_action"):
        case "summarize":
            return "summarize"
        case "final_answer":
            return "final_answer"
        case _:
            return "final_answer"


def validate_final_answer_router(
    state: OverallState,
) -> Send:
    match state.get("next_action"):
        case "final_answer":
            return Send("final_answer", state)
        case "text2cypher":
            # currently only allow for a single follow up question at a time
            tasks = state.get("tasks", list())
            new_task = tasks[-1]
            return Send("text2cypher", {"task": new_task.question})
        case _:
            return Send("final_answer", state)


def query_mapper_edge(state: OverallState) -> List[Send]:
    """Map each task question to a Text2Cypher subgraph."""

    return [
        Send("text2cypher", {"task": task.question})
        for task in state.get("tasks", list())
    ]


def _records_for_task(task, cyphers: List[CypherOutputState]) -> List[Dict[str, Any]]:
    """找出某个 task 对应的 Cypher 查询结果记录。

    CypherOutputState.task 是一个累加列表（Annotated[list, add]），
    因此优先按问题文本匹配，匹配不上时按顺序回退到同下标的查询结果。
    """

    def _records_of(cypher) -> List[Dict[str, Any]]:
        if isinstance(cypher, dict):
            return cypher.get("records") or []
        return getattr(cypher, "records", None) or []

    def _tasks_of(cypher) -> List[str]:
        if isinstance(cypher, dict):
            raw = cypher.get("task") or []
        else:
            raw = getattr(cypher, "task", None) or []
        return [str(t) for t in raw] if isinstance(raw, list) else [str(raw)]

    question = getattr(task, "question", None) or (task.get("question") if isinstance(task, dict) else None)

    for cypher in cyphers:
        if question and question in _tasks_of(cypher):
            return _records_of(cypher)
    return []


def viz_mapper_edge(state: OverallState) -> List[Send]:
    """把需要图表的任务分发给可视化子图。

    没有任何任务需要可视化时，直接进入 gather_visualizations，
    否则图会在 gather_cypher 之后无路可走。
    """
    tasks = state.get("tasks", list())
    cyphers = state.get("cyphers", list())

    sends = []
    for index, task in enumerate(tasks):
        requires_viz = (
            getattr(task, "requires_visualization", None)
            if not isinstance(task, dict)
            else task.get("requires_visualization")
        )
        if not requires_viz:
            continue

        question = getattr(task, "question", None) if not isinstance(task, dict) else task.get("question")
        records = _records_for_task(task, cyphers)
        if not records and index < len(cyphers):
            # 问题文本对不上时按顺序兜底，避免可视化子图拿到空数据
            records = _records_for_task(cyphers[index], cyphers) or (
                cyphers[index].get("records", []) if isinstance(cyphers[index], dict) else []
            )
        sends.append(Send("visualize", {"task": question or "", "records": records}))

    if not sends:
        sends.append(Send("gather_visualizations", state))
    return sends


def map_reduce_planner_to_tool_selection(state: OverallState) -> List[Send]:
    """Map each identified task in the planner stage to a tool_selection node."""
    return [
        Send(
            "tool_selection",
            {
                "question": task.question,
                "parent_task": task.parent_task,
            },
        )
        for task in state.get("tasks", list())
    ]


def tool_selection_output_router(state: ToolSelectionOutputState) -> Send:
    match state.get("next_action", ""):
        case "text2cypher":
            return Send("text2cypher", {"task": state.get("task", "")})
        case "predefined_cypher":
            return Send(
                "predefined_cypher",
                {
                    "task": state.get("task", ""),
                    "tool_call": state.get("tool_call", dict()),
                },
            )
        case "error":
            return Send("final_answer", dict())
        case _:
            return Send("final_answer", dict())
