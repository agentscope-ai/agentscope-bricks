# -*- coding: utf-8 -*-
"""
动态任务编排系统
"""

import json
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from agentscope_bricks.models.llm import BaseLLM
from agentscope_bricks.utils.schemas.oai_llm import (
    UserMessage,
    SystemMessage,
)
from agentscope_bricks.utils.schemas.modelstudio_llm import (
    ModelstudioParameters,
)

# 动态任务编排系统提示词
DYNAMIC_TASK_PLANNING_PROMPT = """
你是一个智能任务规划助手，需要根据用户的问题和已获取的信息动态规划和调整任务。

当前用户问题：
{user_query}

已完成的任务信息：
{completed_tasks_info}

已获取的信息：
{acquired_info}

请根据以上信息，决定下一步应该执行什么任务，或者是否应该结束任务执行。

可选的任务类型：
1. RAG - 使用RAG检索私有知识库
2. SEARCH - 使用Web搜索获取实时信息
3. ANSWER - 直接回答用户问题
4. ANALYZE - 分析已获取的信息
5. PLAN - 重新规划任务
6. END - 结束任务执行

请只输出一个单词，表示任务类型：RAG、SEARCH、ANSWER、ANALYZE、PLAN 或 END
"""

DYNAMIC_TASK_ADJUSTMENT_PROMPT = """
你是一个智能任务调整助手，需要根据当前执行情况和获取的信息，决定是否需要调整任务计划。

当前任务列表：
{task_list}

已完成的任务信息：
{completed_tasks_info}

已获取的信息：
{acquired_info}

请分析是否需要调整任务计划：
1. 如果已获取足够信息，可以结束任务执行，请输出: END|原因说明
2. 如果某些任务已经没有必要执行，请输出: SKIP_TASK|任务ID|原因说明
3. 如果需要添加新任务，请输出: ADD_TASK|任务描述
4. 如果需要修改某个任务，请输出: MODIFY_TASK|任务ID|新描述
5. 如果任务计划合理，继续执行，请输出: CONTINUE

只需输出一行结果。
"""


class DynamicTaskItem(BaseModel):
    """动态任务项"""

    id: int = Field(..., description="任务ID")
    task_type: str = Field(..., description="任务类型")
    description: str = Field(..., description="任务描述")
    status: str = Field(
        ...,
        description="任务状态: pending, in_progress, completed, skipped",
    )
    reason: Optional[str] = Field(None, description="状态变更原因")


class DynamicTaskListModule(BaseModel):
    """动态任务列表模块"""

    tasks: List[DynamicTaskItem] = Field(..., description="任务列表")
    current_task_id: int = Field(
        ...,
        description="当前执行的任务ID，0表示无任务执行",
    )
    total_tasks: int = Field(..., description="初始任务总数")
    executed_tasks: List[int] = Field(
        default_factory=list,
        description="已执行的任务ID列表",
    )


class DynamicTaskSystem:
    """动态任务编排系统"""

    def __init__(self, llm: BaseLLM):
        self.llm = llm

    async def generate_initial_task_plan(
        self,
        query: str,
    ) -> DynamicTaskListModule:
        """生成初始任务计划"""
        print(f"【动态任务系统】开始生成初始任务计划: {query}")

        # 生成思考过程
        thinking_messages = [
            SystemMessage(
                content="你是一个善于思考的助手，请分析用户问题并制定执行计划。",
            ),
            UserMessage(content=query),
        ]

        parameters = ModelstudioParameters(
            temperature=0.5,
            max_tokens=300,
        )

        response = await self.llm.arun(
            model="qwen-max",
            messages=thinking_messages,
            parameters=parameters,
        )

        thinking_process = response.choices[0].message.content.strip()
        print(f"【动态任务系统】思考过程: {thinking_process}")

        # 基于思考过程生成初始任务计划
        task_planning_messages = [
            SystemMessage(
                content="你是一个任务规划助手，请根据问题分析制定具体的执行任务。最多列出3个任务。",
            ),
            UserMessage(content=f"问题分析: {thinking_process}"),
        ]

        response = await self.llm.arun(
            model="qwen-max",
            messages=task_planning_messages,
            parameters=parameters,
        )

        # 解析任务计划
        content = response.choices[0].message.content.strip()
        task_descriptions = [
            task.strip() for task in content.split("\n") if task.strip()
        ]

        # 创建任务项
        task_items = []
        for i, description in enumerate(
            task_descriptions[:3],
            1,
        ):  # 最多3个任务
            # 简单判断任务类型
            task_type = "ANALYZE"  # 默认类型
            if (
                "搜索" in description
                or "查找" in description
                or "网络" in description
                or "web" in description.lower()
            ):
                task_type = "SEARCH"
            elif (
                "知识库" in description
                or "文档" in description
                or "rag" in description.lower()
                or "库" in description
            ):
                task_type = "RAG"
            elif (
                "回答" in description
                or "总结" in description
                or "分析" in description
            ):
                task_type = "ANSWER"

            task_items.append(
                DynamicTaskItem(
                    id=i,
                    task_type=task_type,
                    description=description,
                    status="pending",
                    reason=None,
                ),
            )

        print(
            f"【动态任务系统】初始任务计划生成完成: {[task.description for task in task_items]}",
        )

        return DynamicTaskListModule(
            tasks=task_items,
            current_task_id=0,
            total_tasks=len(task_items),
            executed_tasks=[],
        )

    async def dynamic_task_planning(
        self,
        user_query: str,
        completed_tasks_info: str,
        acquired_info: str,
    ) -> Dict[str, Any]:
        """动态任务规划"""
        print("【动态任务系统】开始动态任务规划")

        planning_messages = [
            SystemMessage(
                content=DYNAMIC_TASK_PLANNING_PROMPT.format(
                    user_query=user_query,
                    completed_tasks_info=completed_tasks_info,
                    acquired_info=acquired_info,
                ),
            ),
            UserMessage(content="请根据以上信息规划下一步任务"),
        ]

        parameters = ModelstudioParameters(
            temperature=0.3,
            max_tokens=10,
        )

        response = await self.llm.arun(
            model="qwen-max",
            messages=planning_messages,
            parameters=parameters,
        )

        # 直接解析LLM返回的关键字
        content = response.choices[0].message.content.strip().upper()
        print(f"【动态任务系统】LLM返回内容: {content}")

        # 验证返回的任务类型是否有效
        valid_task_types = [
            "RAG",
            "SEARCH",
            "ANSWER",
            "ANALYZE",
            "PLAN",
            "END",
        ]
        if content not in valid_task_types:
            print("【动态任务系统】无效的任务类型，使用默认类型: ANALYZE")
            content = "ANALYZE"

        # 返回简单的任务结构
        return {
            "task_type": content,
            "task_description": f"执行{content}任务",
            "reason": "LLM决策",
        }

    async def adjust_task_plan(
        self,
        task_list: DynamicTaskListModule,
        completed_info: str,
    ) -> DynamicTaskListModule:
        """调整任务计划"""
        print("【动态任务系统】开始调整任务计划")

        # 准备调整信息
        completed_tasks_info = []
        for task in task_list.tasks:
            if task.status == "completed":
                completed_tasks_info.append(
                    f"任务{task.id}: {task.description}",
                )

        adjustment_messages = [
            SystemMessage(
                content=DYNAMIC_TASK_ADJUSTMENT_PROMPT.format(
                    task_list=json.dumps(
                        [task.model_dump() for task in task_list.tasks],
                        ensure_ascii=False,
                    ),
                    completed_tasks_info="\n".join(completed_tasks_info),
                    acquired_info=completed_info,
                ),
            ),
            UserMessage(content="请根据以上信息调整任务计划"),
        ]

        parameters = ModelstudioParameters(
            temperature=0.3,
            max_tokens=100,
        )

        response = await self.llm.arun(
            model="qwen-max",
            messages=adjustment_messages,
            parameters=parameters,
        )

        adjustment_result = response.choices[0].message.content.strip()
        print(f"【动态任务系统】任务计划调整结果: {adjustment_result}")

        # 解析调整结果
        if adjustment_result.startswith("END|"):
            reason = adjustment_result[4:]  # Remove "END|" prefix
            # 标记所有未完成任务为跳过
            updated_tasks = []
            for task in task_list.tasks:
                if task.status == "pending":
                    updated_tasks.append(
                        task.model_copy(
                            update={"status": "skipped", "reason": reason},
                        ),
                    )
                else:
                    updated_tasks.append(task)
            return DynamicTaskListModule(
                tasks=updated_tasks,
                current_task_id=task_list.current_task_id,
                total_tasks=task_list.total_tasks,
                executed_tasks=task_list.executed_tasks,
            )
        elif adjustment_result.startswith("SKIP_TASK|"):
            parts = adjustment_result.split("|")
            if len(parts) >= 3:
                try:
                    task_id = int(parts[1])
                    reason = "|".join(
                        parts[2:],
                    )  # Join remaining parts as reason
                    updated_tasks = []
                    for task in task_list.tasks:
                        if task.id == task_id and task.status == "pending":
                            updated_tasks.append(
                                task.model_copy(
                                    update={
                                        "status": "skipped",
                                        "reason": reason,
                                    },
                                ),
                            )
                        else:
                            updated_tasks.append(task)
                    return DynamicTaskListModule(
                        tasks=updated_tasks,
                        current_task_id=task_list.current_task_id,
                        total_tasks=task_list.total_tasks,
                        executed_tasks=task_list.executed_tasks,
                    )
                except ValueError:
                    pass  # Invalid task ID, continue with original plan
        elif adjustment_result.startswith("ADD_TASK|"):
            task_description = adjustment_result[
                9:
            ]  # Remove "ADD_TASK|" prefix
            # 添加新任务
            new_task_id = (
                max([task.id for task in task_list.tasks], default=0) + 1
            )
            new_task = DynamicTaskItem(
                id=new_task_id,
                task_type="ANALYZE",  # 默认类型
                description=task_description,
                status="pending",
                reason="动态添加",
            )
            updated_tasks = task_list.tasks + [new_task]
            return DynamicTaskListModule(
                tasks=updated_tasks,
                current_task_id=task_list.current_task_id,
                total_tasks=task_list.total_tasks + 1,
                executed_tasks=task_list.executed_tasks,
            )
        elif adjustment_result.startswith("MODIFY_TASK|"):
            parts = adjustment_result.split("|")
            if len(parts) >= 3:
                try:
                    task_id = int(parts[1])
                    new_description = "|".join(
                        parts[2:],
                    )  # Join remaining parts as new description
                    updated_tasks = []
                    for task in task_list.tasks:
                        if task.id == task_id:
                            updated_tasks.append(
                                task.model_copy(
                                    update={"description": new_description},
                                ),
                            )
                        else:
                            updated_tasks.append(task)
                    return DynamicTaskListModule(
                        tasks=updated_tasks,
                        current_task_id=task_list.current_task_id,
                        total_tasks=task_list.total_tasks,
                        executed_tasks=task_list.executed_tasks,
                    )
                except ValueError:
                    pass  # Invalid task ID, continue with original plan

        # 如果CONTINUE或解析失败，返回原始任务列表
        print("【动态任务系统】继续执行原计划")
        return task_list

    @staticmethod
    def update_task_status(
        task_list: DynamicTaskListModule,
        completed_task_ids: List[int],
        current_task_id: int,
        skipped_task_ids: List[int] = None,
    ) -> DynamicTaskListModule:
        """更新任务状态"""
        if skipped_task_ids is None:
            skipped_task_ids = []

        updated_tasks = []
        for task in task_list.tasks:
            if task.id in completed_task_ids:
                updated_tasks.append(
                    task.model_copy(update={"status": "completed"}),
                )
            elif task.id in skipped_task_ids:
                # 保持现有的原因如果已设置
                existing_task = next(
                    (t for t in task_list.tasks if t.id == task.id),
                    None,
                )
                reason = (
                    existing_task.reason
                    if existing_task and existing_task.reason
                    else "动态跳过"
                )
                updated_tasks.append(
                    task.model_copy(
                        update={"status": "skipped", "reason": reason},
                    ),
                )
            elif task.id == current_task_id:
                updated_tasks.append(
                    task.model_copy(update={"status": "in_progress"}),
                )
            else:
                updated_tasks.append(task)

        # 更新已执行任务列表
        new_executed_tasks = list(
            set(task_list.executed_tasks + completed_task_ids),
        )

        return DynamicTaskListModule(
            tasks=updated_tasks,
            current_task_id=current_task_id,
            total_tasks=task_list.total_tasks,
            executed_tasks=new_executed_tasks,
        )
