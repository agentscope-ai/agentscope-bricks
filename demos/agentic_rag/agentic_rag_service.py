# -*- coding: utf-8 -*-
import os
import asyncio
import json
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

import dashscope
from agentscope_bricks.components.RAGs.modelstudio_rag import (
    ModelstudioRag,
    RagInput,
    RagOutput,
)
from agentscope_bricks.components.searches.modelstudio_search_lite import (
    ModelstudioSearchLite,
    SearchLiteInput,
    SearchLiteOutput,
)
from agentscope_bricks.models.llm import BaseLLM
from agentscope_bricks.utils.schemas.oai_llm import (
    UserMessage,
    SystemMessage,
    AssistantMessage,
)
from agentscope_bricks.utils.schemas.modelstudio_llm import (
    ModelstudioChatRequest,
    ModelstudioParameters,
)
from agentscope_bricks.utils.server_utils.fastapi_server import FastApiServer

# 导入响应转换器
try:
    from .response_converter import AgenticRagResponseConverter
except ImportError:
    from response_converter import AgenticRagResponseConverter

# 导入动态任务系统
try:
    from dynamic_task_system import DynamicTaskSystem, DynamicTaskListModule
except ImportError:
    # 如果直接导入失败，尝试相对导入
    from .dynamic_task_system import DynamicTaskSystem, DynamicTaskListModule


# Pydantic models for the four modules output
class ThinkingModule(BaseModel):
    """Thinking process module"""

    process: str = Field(..., description="The thinking process of the model")


class TaskItem(BaseModel):
    """Individual task item"""

    id: int = Field(..., description="Task ID/序号")
    description: str = Field(..., description="Task description/任务描述")
    status: str = Field(
        ...,
        description="Task status: pending, in_progress, completed, "
        "skipped/任务状态",
    )
    reason: Optional[str] = Field(
        None,
        description="Reason for skipping or completion/跳过或完成的原因",
    )


class TaskListModule(BaseModel):
    """Task list planning module"""

    tasks: List[TaskItem] = Field(
        ...,
        description="List of tasks to be executed/任务列表",
    )
    current_task_id: int = Field(
        ...,
        description="Current task ID being executed/当前执行的任务ID",
    )
    total_tasks: int = Field(..., description="Total number of tasks/总任务数")
    executed_tasks: List[int] = Field(
        default_factory=list,
        description="List of executed task IDs/已执行的任务ID列表",
    )


class SearchModule(BaseModel):
    """Web search module"""

    query: str = Field(..., description="The search query")
    results: List[Dict[str, Any]] = Field(..., description="Search results")
    status: int = Field(..., description="Search status (0 for success)")


class RagModule(BaseModel):
    """RAG retrieval module"""

    query: str = Field(..., description="The RAG query")
    chunks: List[Dict[str, Any]] = Field(
        ...,
        description="Retrieved document chunks",
    )
    raw_result: Optional[List[Dict[str, Any]]] = Field(
        None,
        description="Raw RAG results from the service",
    )
    rag_result: Optional[str] = Field(
        None,
        description="Formatted RAG result string",
    )
    status: int = Field(..., description="RAG status (0 for success)")


class AgenticRagResponse(BaseModel):
    """Complete response with all four modules"""

    thinking: Optional[ThinkingModule] = None
    task_list: Optional[DynamicTaskListModule] = None
    search: Optional[SearchModule] = None
    rag: Optional[RagModule] = None
    final_response: str = Field(..., description="Final response to the user")


# System prompt for decision making
DECISION_SYSTEM_PROMPT = """
你是一个智能决策助手，需要根据用户的问题决定采取哪种行动：

1. 如果问题涉及用户私有知识库中的信息，请选择使用RAG
2. 如果问题需要实时网络信息（如新闻、天气、股票等），请选择使用Web搜索
3. 如果问题可以直接回答或需要进一步澄清，请选择直接回答

请只输出以下三种选项之一：
- RAG
- SEARCH
- ANSWER
"""

# System prompt for task planning
PLANNING_SYSTEM_PROMPT = """
你是一个任务规划助手，需要根据用户的问题制定执行计划。

请按照以下格式输出任务列表：
1. 任务1描述
2. 任务2描述
3. 任务3描述

最多列出5个任务，每个任务应该具体且可执行。
"""

# System prompt for thinking process
THINKING_SYSTEM_PROMPT = """
你是一个善于思考的助手，请详细描述你对用户问题的思考过程，包括：
1. 问题分析
2. 解决思路
3. 可能的挑战
4. 解决方案
"""

# System prompt for dynamic task replanning
REPLANNING_SYSTEM_PROMPT = """
你是一个智能任务调度助手，需要根据当前已完成的任务和获取的信息，重新评估剩余任务的必要性。

当前已完成的任务：
{completed_tasks_info}

获取到的信息：
{acquired_info}

剩余待执行的任务：
{pending_tasks}

请分析是否需要调整任务计划：
1. 如果剩余任务已经没有必要执行，请输出: SKIP_ALL_REMAINING|原因说明
2. 如果某些任务已经没有必要执行，请输出: SKIP_TASK|任务ID|原因说明
3. 如果任务计划合理，继续执行，请输出: CONTINUE

只需输出一行结果。
"""

api_key = os.environ.get("DASHSCOPE_API_KEY", "")
dashscope.api_key = api_key
llm = BaseLLM(api_key=api_key)
rag_component = ModelstudioRag()
search_component = ModelstudioSearchLite()

# 初始化动态任务系统
dynamic_task_system = DynamicTaskSystem(llm)

# 初始化响应转换器
response_converter = AgenticRagResponseConverter()


class DecisionInput(BaseModel):
    query: str


class DecisionOutput(BaseModel):
    decision: str  # RAG, SEARCH, or ANSWER


async def make_decision(query: str) -> DecisionOutput:
    """Make a decision on which action to take based on the user query."""
    print(f"【决策模块】开始分析用户查询: {query}")

    decision_messages = [
        SystemMessage(content=DECISION_SYSTEM_PROMPT),
        UserMessage(content=query),
    ]

    parameters = ModelstudioParameters(
        temperature=0.0,  # Use low temperature for consistent decision making
        max_tokens=10,
    )

    response = await llm.arun(
        model="qwen-max",
        messages=decision_messages,
        parameters=parameters,
    )

    decision = response.choices[0].message.content.strip().upper()
    if decision not in ["RAG", "SEARCH", "ANSWER"]:
        decision = "ANSWER"  # Default to ANSWER if unclear

    print(f"【决策模块】决策结果: {decision}")
    return DecisionOutput(decision=decision)


async def generate_thinking_process(query: str) -> ThinkingModule:
    """Generate thinking process for the query."""
    print(f"【思考模块】开始生成思考过程: {query}")

    thinking_messages = [
        SystemMessage(content=THINKING_SYSTEM_PROMPT),
        UserMessage(content=query),
    ]

    parameters = ModelstudioParameters(
        temperature=0.7,
        max_tokens=500,
    )

    response = await llm.arun(
        model="qwen-max",
        messages=thinking_messages,
        parameters=parameters,
    )

    thinking_process = response.choices[0].message.content.strip()
    print("【思考模块】思考过程生成完成")
    print(f"【思考模块】思考过程内容: {thinking_process}")
    return ThinkingModule(process=thinking_process)


async def generate_task_list(query: str) -> TaskListModule:
    """Generate task list for the query."""
    print(f"【任务列表模块】开始生成任务列表: {query}")

    planning_messages = [
        SystemMessage(content=PLANNING_SYSTEM_PROMPT),
        UserMessage(content=query),
    ]

    parameters = ModelstudioParameters(
        temperature=0.5,
        max_tokens=200,
    )

    response = await llm.arun(
        model="qwen-max",
        messages=planning_messages,
        parameters=parameters,
    )

    # Parse the task list from the response
    content = response.choices[0].message.content.strip()
    task_descriptions = [
        task.strip()[3:]
        for task in content.split("\n")
        if task.strip().startswith(("1.", "2.", "3.", "4.", "5."))
    ]

    # Create TaskItem list with IDs and statuses
    task_items = []
    for i, description in enumerate(task_descriptions, 1):
        task_items.append(
            TaskItem(
                id=i,
                description=description,
                status="pending",  # All tasks start as pending
                reason=None,
            ),
        )

    print(
        f"【任务列表模块】"
        f"任务列表生成完成: {[task.description for task in task_items]}",
    )

    # Initially, no task is in progress
    return TaskListModule(
        tasks=task_items,
        current_task_id=0,  # 0 means no task is currently running
        total_tasks=len(task_items),
        executed_tasks=[],
    )


async def process_with_rag(
    messages: List,
    rag_options: Optional[Dict] = None,
) -> RagOutput:
    """Process the query with RAG component."""
    print("【RAG模块】开始处理RAG请求")

    if rag_options:
        rag_input = RagInput(
            messages=messages,
            rag_options=rag_options,
            rest_token=2000,
        )
        rag_output: RagOutput = await rag_component.arun(rag_input)
        print(
            f"【RAG模块】RAG处理完成，召回文档数: {len(rag_output.raw_result)}",
        )
        return rag_output
    else:
        print("【RAG模块】未提供RAG选项，返回空结果")
        return RagOutput(
            raw_result=[],
            rag_result="",
            messages=messages,
        )


async def replan_tasks(
    task_list: TaskListModule,
    completed_info: str,
) -> TaskListModule:
    """Dynamically replan tasks based on acquired information"""
    print("【任务列表模块】开始动态重规划任务")

    # Prepare information for replanning
    completed_tasks_info = []
    pending_tasks_info = []

    for task in task_list.tasks:
        if task.status == "completed":
            completed_tasks_info.append(f"任务{task.id}: {task.description}")
        elif task.status == "pending":
            pending_tasks_info.append(f"任务{task.id}: {task.description}")

    replanning_messages = [
        SystemMessage(
            content=REPLANNING_SYSTEM_PROMPT.format(
                completed_tasks_info="\n".join(completed_tasks_info),
                acquired_info=completed_info,
                pending_tasks="\n".join(pending_tasks_info),
            ),
        ),
        UserMessage(content="请根据以上信息重新评估任务计划"),
    ]

    parameters = ModelstudioParameters(
        temperature=0.3,
        max_tokens=100,
    )

    response = await llm.arun(
        model="qwen-max",
        messages=replanning_messages,
        parameters=parameters,
    )

    replan_result = response.choices[0].message.content.strip()
    print(f"【任务列表模块】重规划结果: {replan_result}")

    # Parse replanning result
    if replan_result.startswith("SKIP_ALL_REMAINING|"):
        reason = replan_result[19:]  # Remove "SKIP_ALL_REMAINING|" prefix
        skipped_task_ids = []
        updated_tasks = []
        for task in task_list.tasks:
            if task.status == "pending":
                skipped_task_ids.append(task.id)
                updated_tasks.append(
                    TaskItem(
                        id=task.id,
                        description=task.description,
                        status="skipped",
                        reason=reason,
                    ),
                )
            else:
                updated_tasks.append(task)
        return TaskListModule(
            tasks=updated_tasks,
            current_task_id=task_list.current_task_id,
            total_tasks=task_list.total_tasks,
            executed_tasks=task_list.executed_tasks,
        )
    elif replan_result.startswith("SKIP_TASK|"):
        parts = replan_result.split("|")
        if len(parts) >= 3:
            try:
                task_id = int(parts[1])
                reason = "|".join(parts[2:])  # Join remaining parts as reason
                skipped_task_ids = [task_id]
                updated_tasks = []
                for task in task_list.tasks:
                    if task.id == task_id and task.status == "pending":
                        updated_tasks.append(
                            TaskItem(
                                id=task.id,
                                description=task.description,
                                status="skipped",
                                reason=reason,
                            ),
                        )
                    else:
                        updated_tasks.append(task)
                return TaskListModule(
                    tasks=updated_tasks,
                    current_task_id=task_list.current_task_id,
                    total_tasks=task_list.total_tasks,
                    executed_tasks=task_list.executed_tasks,
                )
            except ValueError:
                pass  # Invalid task ID, continue with original plan

    # If CONTINUE or invalid format, return original task list
    print("【任务列表模块】继续执行原计划")
    return task_list


async def process_with_search(query: str, count: int = 5) -> SearchLiteOutput:
    """Process the query with web search component."""
    print(f"【搜索模块】开始处理Web搜索请求: {query}")

    search_input = SearchLiteInput(
        query=query,
        count=count,
    )
    search_output: SearchLiteOutput = await search_component.arun(search_input)
    print(f"【搜索模块】Web搜索处理完成，结果数: {len(search_output.pages)}")
    return search_output


def format_search_results_for_frontend(
    search_output: SearchLiteOutput,
) -> List[Dict[str, Any]]:
    """Format search results for frontend display."""
    if not search_output.pages:
        return []

    formatted_results = []
    for page in search_output.pages[:5]:  # Limit to top 5 results
        formatted_results.append(
            {
                "title": page.get("title", "无标题"),
                "snippet": page.get("snippet", "无摘要"),
                "url": page.get("url", "无链接"),
                "hostname": page.get("hostname", ""),
                "hostlogo": page.get("hostlogo", ""),
            },
        )

    return formatted_results


def format_rag_chunks_for_frontend(
    rag_output: RagOutput,
) -> List[Dict[str, Any]]:
    """Format RAG chunks for frontend display."""
    if not rag_output.raw_result:
        return []

    formatted_chunks = []
    for i, chunk in enumerate(
        rag_output.raw_result[:5],
    ):  # Limit to top 5 chunks
        formatted_chunks.append(
            {
                "id": i,
                "content": chunk.get("text", ""),
                "source": chunk.get("source", "未知来源"),
                "score": chunk.get("score", 0.0),
                "metadata": chunk.get("metadata", {}),
            },
        )

    return formatted_chunks


def update_task_list_status(
    task_list: TaskListModule,
    completed_task_ids: List[int],
    current_task_id: int,
    skipped_task_ids: List[int] = [],
) -> TaskListModule:
    """Update task list status"""
    updated_tasks = []
    for task in task_list.tasks:
        if task.id in completed_task_ids:
            updated_tasks.append(
                TaskItem(
                    id=task.id,
                    description=task.description,
                    status="completed",
                    reason=None,
                ),
            )
        elif task.id in skipped_task_ids:
            # Keep the existing reason if already set
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
                TaskItem(
                    id=task.id,
                    description=task.description,
                    status="skipped",
                    reason=reason,
                ),
            )
        elif task.id == current_task_id:
            updated_tasks.append(
                TaskItem(
                    id=task.id,
                    description=task.description,
                    status="in_progress",
                    reason=None,
                ),
            )
        else:
            updated_tasks.append(
                TaskItem(
                    id=task.id,
                    description=task.description,
                    status=task.status,
                    reason=task.reason,
                ),
            )

    # Update executed tasks list
    new_executed_tasks = list(
        set(task_list.executed_tasks + completed_task_ids),
    )

    return TaskListModule(
        tasks=updated_tasks,
        current_task_id=current_task_id,
        total_tasks=task_list.total_tasks,
        executed_tasks=new_executed_tasks,
    )


async def agentic_rag_arun(request: ModelstudioChatRequest):
    """Main agentic RAG service function with dynamic task orchestration."""
    print("【主服务】开始处理用户请求")

    # 立即向前端发送开始处理的响应
    initial_response = AgenticRagResponse(
        thinking=None,
        task_list=None,
        search=None,
        rag=None,
        final_response="【主服务】开始处理用户请求",
    )
    internal_response_dict = initial_response.model_dump()
    for converted_response in response_converter.convert_intermediate_response(
        internal_response_dict,
    ):
        yield f"data: {
            json.dumps(converted_response, default=str, ensure_ascii=False)
        }\n\n"

    # Get user query
    user_query = request.messages[-1].get_text_content()
    print(f"【主服务】用户查询: {user_query}")

    # 向前端发送用户查询内容
    query_response = AgenticRagResponse(
        thinking=None,
        task_list=None,
        search=None,
        rag=None,
        final_response=f"【主服务】用户查询: {user_query}",
    )
    internal_response_dict = query_response.model_dump()
    for converted_response in response_converter.convert_intermediate_response(
        internal_response_dict,
    ):
        yield f"data: {
            json.dumps(
                converted_response,
                default=str, ensure_ascii=False
            )
        }\n\n"

    # Generate thinking process using dynamic task system
    print("【主服务】生成思考过程")

    # 向前端发送正在生成思考过程的消息
    thinking_start_response = AgenticRagResponse(
        thinking=None,
        task_list=None,
        search=None,
        rag=None,
        final_response="【主服务】生成思考过程",
    )
    internal_response_dict = thinking_start_response.model_dump()
    for converted_response in response_converter.convert_intermediate_response(
        internal_response_dict,
    ):
        yield f"data: {json.dumps(converted_response, default=str, ensure_ascii=False)}\n\n"  # noqa E501

    thinking_module = await generate_thinking_process(user_query)
    print(f"【主服务】思考过程生成完成: {thinking_module.process}")

    # 向前端发送思考过程完成的消息
    thinking_complete_response = AgenticRagResponse(
        thinking=thinking_module,
        task_list=None,
        search=None,
        rag=None,
        final_response="【主服务】思考过程生成完成",
    )
    internal_response_dict = thinking_complete_response.model_dump()
    for converted_response in response_converter.convert_intermediate_response(
        internal_response_dict,
    ):
        yield f"data: {
            json.dumps(
                converted_response,
                default=str, ensure_ascii=False
            )
        }\n\n"

    # Generate initial dynamic task plan
    print("【主服务】生成初始动态任务计划")
    task_list_module = await dynamic_task_system.generate_initial_task_plan(
        user_query,
    )
    print(
        f"【主服务】初始任务计划生成完成: "
        f"{[task.description for task in task_list_module.tasks]}",
    )

    # Initialize modules
    search_module = None
    rag_module = None

    # Execute tasks dynamically
    completed_tasks_info = []
    acquired_info = {}

    # Process tasks dynamically
    task_index = 0
    while any(task.status == "pending" for task in task_list_module.tasks):
        # Get next pending task
        next_task = None
        for task in task_list_module.tasks:
            if task.status == "pending":
                next_task = task
                break

        if not next_task:
            break

        # Dynamic task planning
        print("【主服务】动态任务规划")
        task_plan = await dynamic_task_system.dynamic_task_planning(
            user_query,
            "\n".join(completed_tasks_info),
            json.dumps(acquired_info, ensure_ascii=False),
        )

        # Update task type based on dynamic planning
        # Create a new task with updated type
        from dynamic_task_system import DynamicTaskItem

        updated_task = DynamicTaskItem(
            id=next_task.id,
            task_type=task_plan["task_type"],
            description=next_task.description,
            status=next_task.status,
            reason=next_task.reason,
        )

        # Update task status to in_progress
        task_list_module = dynamic_task_system.update_task_status(
            task_list_module,
            [],
            updated_task.id,
        )
        print(
            f"【主服务】任务{updated_task.id}进行中: {updated_task.description} "
            f"(类型: {updated_task.task_type})",
        )

        # Yield intermediate response for task start using response converter
        intermediate_response = AgenticRagResponse(
            thinking=thinking_module,
            task_list=task_list_module,
            search=search_module,
            rag=rag_module,
            final_response="正在处理任务...",
        )
        print(
            f"【主服务】任务开始中间结果输出: {json.dumps(intermediate_response.model_dump(), ensure_ascii=False)}",  # noqa E501
        )

        # 使用响应转换器生成符合agent协议的流式响应
        internal_response_dict = intermediate_response.model_dump()
        for (
            converted_response
        ) in response_converter.convert_intermediate_response(
            internal_response_dict,
        ):
            yield f"data: {
                json.dumps(
                    converted_response,
                    default=str, ensure_ascii=False
                )
            }\n\n"

        # Execute task based on type
        if updated_task.task_type == "RAG" and request.rag_options:
            print(f"【主服务】执行RAG任务: {updated_task.description}")
            rag_messages = [
                SystemMessage(content=""),
                UserMessage(content=user_query),
            ]
            rag_output = await process_with_rag(
                rag_messages,
                request.rag_options,
            )

            # Create RAG module for frontend
            rag_module = RagModule(
                query=user_query,
                chunks=format_rag_chunks_for_frontend(rag_output),
                raw_result=rag_output.raw_result,
                rag_result=rag_output.rag_result,
                status=0 if rag_output.raw_result else 1,
            )

            # Update acquired info
            acquired_info["rag_result"] = (
                f"通过RAG检索到{len(rag_output.raw_result)}个相关文档"
            )
            completed_tasks_info.append(
                f"任务{updated_task.id}: {updated_task.description} - "
                f"完成，{acquired_info['rag_result']}",
            )
            print(
                f"【主服务】RAG模块数据已更新: {len(rag_output.raw_result)}个文档",
            )

        elif updated_task.task_type == "SEARCH":
            print(f"【主服务】执行搜索任务: {updated_task.description}")
            search_output = await process_with_search(user_query)

            # Create Search module for frontend
            search_module = SearchModule(
                query=user_query,
                results=format_search_results_for_frontend(search_output),
                status=search_output.status,
            )

            # Update acquired info
            acquired_info["search_result"] = (
                f"通过搜索获取到{len(search_output.pages)}个结果"
            )
            completed_tasks_info.append(
                f"任务{updated_task.id}: {updated_task.description} -"
                f" 完成，{acquired_info['search_result']}",
            )
            print(
                f"【主服务】搜索模块数据已更新: {len(search_output.pages)}个结果",
            )

        elif updated_task.task_type == "ANSWER":
            print(f"【主服务】执行回答任务: {updated_task.description}")
            # For answer tasks, we just mark them as completed
            completed_tasks_info.append(
                f"任务{updated_task.id}: {updated_task.description} - 完成",
            )

        elif updated_task.task_type == "ANALYZE":
            print(f"【主服务】执行分析任务: {updated_task.description}")
            # For analyze tasks, we just mark them as completed
            completed_tasks_info.append(
                f"任务{updated_task.id}: {updated_task.description} - 完成",
            )

        # Mark task as completed
        task_list_module = dynamic_task_system.update_task_status(
            task_list_module,
            [updated_task.id],
            0,
        )
        print(f"【主服务】任务{updated_task.id}完成")

        # Yield intermediate response for task completion using response
        # converter
        intermediate_response = AgenticRagResponse(
            thinking=thinking_module,
            task_list=task_list_module,
            search=search_module,
            rag=rag_module,
            final_response="正在处理任务...",
        )
        # 先打印完成信息，再推送响应
        print(
            f"【主服务】任务完成中间结果输出: {json.dumps(intermediate_response.model_dump(), ensure_ascii=False)}",  # noqa E501
        )

        # 使用响应转换器生成符合agent协议的流式响应
        internal_response_dict = intermediate_response.model_dump()
        for (
            converted_response
        ) in response_converter.convert_intermediate_response(
            internal_response_dict,
        ):
            yield f"data: {
                json.dumps(
                    converted_response,
                    default=str, ensure_ascii=False
                )
            }\n\n"

        # Dynamic task adjustment
        print("【主服务】动态任务调整")
        task_list_module = await dynamic_task_system.adjust_task_plan(
            task_list_module,
            json.dumps(acquired_info, ensure_ascii=False),
        )

        task_index += 1

    # Generate final response
    print("【主服务】生成最终回答")
    final_messages = [
        SystemMessage(content="请根据提供的信息回答用户问题"),
        UserMessage(content=user_query),
    ]

    parameters = ModelstudioParameters(
        **request.model_dump(exclude_unset=True),
    )

    final_response_text = ""
    async for chunk in llm.astream(
        model="qwen-max",
        messages=final_messages,
        parameters=parameters,
    ):
        if hasattr(chunk, "choices") and chunk.choices:
            delta = chunk.choices[0].delta
            if hasattr(delta, "content") and delta.content:
                final_response_text += delta.content

    # Create final response
    final_response = AgenticRagResponse(
        thinking=thinking_module,
        task_list=task_list_module,
        search=search_module,
        rag=rag_module,
        final_response=final_response_text,
    )

    print(
        f"【主服务】最终结果输出: {
            json.dumps(
                final_response.model_dump(),
                ensure_ascii=False
            )
        }",
    )
    print("【主服务】请求处理完成")

    # 使用响应转换器生成符合agent协议的最终响应
    final_response_dict = final_response.model_dump()
    for converted_response in response_converter.convert_final_response(
        final_response_dict,
    ):
        yield f"data: {
            json.dumps(
                converted_response, default=str,
                ensure_ascii=False
            )
        }\n\n"

    # 注意：convert_final_response已经发送了最终的completed状态，所以不需要再发送[DONE]
    # yield "data: [DONE]\n\n"


server = FastApiServer(
    func=agentic_rag_arun,
    endpoint_path="/api/v1/chat/completions",
    request_model=ModelstudioChatRequest,
)


if __name__ == "__main__":
    server.run(port=8091)
