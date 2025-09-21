# -*- coding: utf-8 -*-
"""
灵活的任务编排系统示例
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class FlexibleTaskItem(BaseModel):
    """灵活的任务项，支持动态调整"""

    id: int = Field(..., description="任务ID")
    description: str = Field(..., description="任务描述")
    status: str = Field(
        ...,
        description="任务状态: pending, in_progress, completed, skipped",
    )
    reason: Optional[str] = Field(None, description="状态变更原因")


class FlexibleTaskListModule(BaseModel):
    """灵活的任务列表模块"""

    tasks: List[FlexibleTaskItem] = Field(..., description="任务列表")
    current_task_id: int = Field(
        ...,
        description="当前执行的任务ID，0表示无任务执行",
    )
    total_tasks: int = Field(..., description="初始任务总数")
    executed_tasks: List[int] = Field(
        default_factory=list,
        description="已执行的任务ID列表",
    )


async def dynamic_task_scheduler(
    task_list: FlexibleTaskListModule,
    completed_task_info: dict,
) -> FlexibleTaskListModule:
    """
    动态任务调度器

    Args:
        task_list: 当前任务列表
        completed_task_info: 已完成任务的信息，用于决策是否需要跳过后续任务

    Returns:
        更新后的任务列表
    """
    print("【动态调度器】开始分析任务执行情况")

    # 示例逻辑：根据已完成任务的信息判断是否需要跳过后续任务
    # 这里可以根据实际需求实现更复杂的逻辑

    # 检查是否已经获取到足够信息
    if should_skip_remaining_tasks(completed_task_info):
        print("【动态调度器】信息已足够，跳过剩余任务")
        return skip_remaining_tasks(
            task_list,
            "已获取足够信息，无需执行后续任务",
        )

    # 检查特定任务是否可以跳过
    task_to_skip = check_specific_task_to_skip(task_list, completed_task_info)
    if task_to_skip:
        print(f"【动态调度器】跳过任务 {task_to_skip}")
        return skip_specific_task(
            task_list,
            task_to_skip,
            "根据已获取信息，此任务不再必要",
        )

    print("【动态调度器】继续执行原计划")
    return task_list


def should_skip_remaining_tasks(completed_task_info: dict) -> bool:
    """判断是否应该跳过剩余任务"""
    # 示例逻辑：如果RAG找到了足够信息，就不需要执行搜索任务
    if completed_task_info.get("rag_documents_found", 0) > 3:
        return True
    return False


def check_specific_task_to_skip(
    task_list: FlexibleTaskListModule,
    completed_task_info: dict,
) -> Optional[int]:
    """检查是否有特定任务可以跳过"""
    # 示例逻辑：如果RAG已经找到了相关信息，就不需要执行市场调研任务
    if completed_task_info.get(
        "rag_relevant_info",
        False,
    ) and has_market_research_task(task_list):
        return get_market_research_task_id(task_list)
    return None


def skip_remaining_tasks(
    task_list: FlexibleTaskListModule,
    reason: str,
) -> FlexibleTaskListModule:
    """跳过剩余所有任务"""
    updated_tasks = []
    for task in task_list.tasks:
        if task.status == "pending":
            updated_tasks.append(
                FlexibleTaskItem(
                    id=task.id,
                    description=task.description,
                    status="skipped",
                    reason=reason,
                ),
            )
        else:
            updated_tasks.append(task)

    return FlexibleTaskListModule(
        tasks=updated_tasks,
        current_task_id=task_list.current_task_id,
        total_tasks=task_list.total_tasks,
        executed_tasks=task_list.executed_tasks,
    )


def skip_specific_task(
    task_list: FlexibleTaskListModule,
    task_id: int,
    reason: str,
) -> FlexibleTaskListModule:
    """跳过特定任务"""
    updated_tasks = []
    for task in task_list.tasks:
        if task.id == task_id and task.status == "pending":
            updated_tasks.append(
                FlexibleTaskItem(
                    id=task.id,
                    description=task.description,
                    status="skipped",
                    reason=reason,
                ),
            )
        else:
            updated_tasks.append(task)

    return FlexibleTaskListModule(
        tasks=updated_tasks,
        current_task_id=task_list.current_task_id,
        total_tasks=task_list.total_tasks,
        executed_tasks=task_list.executed_tasks,
    )


def has_market_research_task(task_list: FlexibleTaskListModule) -> bool:
    """检查是否存在市场调研任务"""
    for task in task_list.tasks:
        if "市场" in task.description or "调研" in task.description:
            return True
    return False


def get_market_research_task_id(
    task_list: FlexibleTaskListModule,
) -> Optional[int]:
    """获取市场调研任务ID"""
    for task in task_list.tasks:
        if "市场" in task.description or "调研" in task.description:
            return task.id
    return None


# 使用示例
async def example_usage():
    """使用示例"""
    # 初始化任务列表
    initial_tasks = [
        FlexibleTaskItem(id=1, description="分析技术特点", status="pending"),
        FlexibleTaskItem(id=2, description="市场调研", status="pending"),
        FlexibleTaskItem(id=3, description="数据统计", status="pending"),
        FlexibleTaskItem(id=4, description="撰写报告", status="pending"),
    ]

    task_list = FlexibleTaskListModule(
        tasks=initial_tasks,
        current_task_id=0,
        total_tasks=4,
        executed_tasks=[],
    )

    # 模拟完成任务1（分析技术特点）
    task_list.current_task_id = 1
    # 更新任务状态为完成
    updated_tasks = []
    for task in task_list.tasks:
        if task.id == 1:
            updated_tasks.append(
                FlexibleTaskItem(
                    id=task.id,
                    description=task.description,
                    status="completed",
                ),
            )
        else:
            updated_tasks.append(task)

    task_list.tasks = updated_tasks
    task_list.executed_tasks.append(1)
    task_list.current_task_id = 0

    # 动态调度：根据任务1的结果决定是否跳过其他任务
    completed_info = {
        "rag_documents_found": 5,  # 找到了5个相关文档
        "rag_relevant_info": True,  # 找到了相关信息
    }

    task_list = await dynamic_task_scheduler(task_list, completed_info)

    # 输出结果
    for task in task_list.tasks:
        status_icon = {
            "completed": "✅",
            "in_progress": "⏳",
            "skipped": "⏭️",
            "pending": "⏸️",
        }.get(task.status, "❓")
        reason = f" ({task.reason})" if task.reason else ""
        print(
            f"{status_icon} 任务{task.id}: {task.description} [{task.status}]{reason}",  # noqa E501
        )
