# -*- coding: utf-8 -*-
import asyncio
import time
import os
import json
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from dotenv import load_dotenv

from datetime import datetime
from computer_use_agent_base import ComputerUseAgent

from cua_utils_base import init_output_dir, init_sandbox, cleanup_sandbox
import uuid


load_dotenv()

app = FastAPI(title="Computer Use Agent Backend", version="1.0.0")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Memory cache for session_id storage
SESSION_CACHE = {}
PHONE_SESSION_CACHE = {}


# Status queue management
class StatusQueue:
    def __init__(self):
        self.queue = asyncio.Queue()
        self.subscribers = set()

    async def put_status(self, status_data: dict):
        """Add status to queue"""
        try:
            await self.queue.put(status_data)
        except Exception as e:
            print(f"Error putting status to queue: {e}")

    async def get_status(self):
        """Get status from queue"""
        return await self.queue.get()

    def add_subscriber(self):
        """Add subscriber"""
        subscriber_id = id(asyncio.current_task())
        self.subscribers.add(subscriber_id)
        return subscriber_id

    def remove_subscriber(self, subscriber_id):
        """Remove subscriber"""
        self.subscribers.discard(subscriber_id)


# Global task management
class TaskManager:
    def __init__(self):
        self.current_task = None
        self.is_running = False
        self.equipment = None
        self.sandbox = None
        self.agent = None
        self.output_dir = None
        self.task_id = None
        self.sandbox_type = None
        self.last_status = {
            "status": "idle",
            "message": "Ready to start",
            "type": "SYSTEM",
            "timestamp": time.time(),
        }
        self.equipment_web_url = None
        self.instance_manager = None
        self.background_tasks: Optional[asyncio.Task] = None

    def start_task(self, task_data: dict) -> dict:
        """Start new task"""
        try:
            if self.is_running:
                raise HTTPException(
                    status_code=409,
                    detail="A task is already running",
                )
            self.output_dir = init_output_dir(lambda id: f"./output/run_{id}")
            self.task_id = os.path.basename(self.output_dir)
            self.sandbox_type = task_data.get("config").sandbox_type
            if self.sandbox_type == "e2b-desktop":
                self.equipment = init_sandbox()
                if self.equipment.device:
                    self.sandbox = self.equipment.device
                self.current_task = task_data
                self.is_running = True

                return {
                    "task_id": self.task_id,
                    "output_dir": self.output_dir,
                    # "equipment_web_url": equipment_web_url,
                    # "equipment_web_sdk_info": equipment_web_sdk_info,
                    "sandbox_id": self.sandbox.sandbox_id,
                    "sandbox_url": self.sandbox.stream.get_url(),
                }

        except Exception as e:
            print(f"Error start task: {e}")

    def stop_task(self):
        """Stop current task"""
        self.is_running = False
        if self.equipment:
            if self.sandbox_type == "e2b-desktop":
                try:
                    cleanup_sandbox(self.equipment)
                except Exception as e:
                    print(f"Error stopping sandbox: {e}")
        self.equipment = None
        self.agent = None
        self.current_task = None
        self.output_dir = None
        self.task_id = None
        self.last_status = {
            "status": "idle",
            "message": "Ready to start",
            "type": "SYSTEM",
            "equipment_web_url": self.equipment_web_url,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "uuid": str(uuid.uuid4()),
        }

    def update_status(self, status_data: dict):
        """Update task status"""
        self.last_status = {
            **status_data,
            "uuid": str(uuid.uuid4()),
            "task_id": self.task_id,
        }


# Global instances
status_queue = StatusQueue()
task_manager = TaskManager()


# Request/Response models
class MessageContent(BaseModel):
    type: str
    text: Optional[str] = None
    image: Optional[str] = None


class Message(BaseModel):
    role: str
    content: List[MessageContent]


class AgentConfig(BaseModel):
    mode: str = "qwen_vl"  # qwen_vl or pc_use
    sandbox_type: str = "e2b-desktop"  # e2b-desktop or wuyin
    save_logs: bool = True
    timeout: int = 120
    pc_use_addon_info: str = ""
    max_steps: int = 10
    static_url: str = ""


class RunRequest(BaseModel):
    messages: List[Message]
    config: Optional[AgentConfig] = AgentConfig()


class SessionRunRequest(BaseModel):
    session_id: str = ""
    sandbox_type: str = ""


class StatusResponse(BaseModel):
    uuid: str
    status: str
    type: str
    timestamp: Optional[str] = ""
    message: Optional[str] = ""
    task_id: Optional[str] = ""
    data: Optional[Dict[str, Any]] = {}


# SSE endpoint
@app.get("/sse/status")
async def status_stream():
    """SSE endpoint for real-time status updates"""

    async def event_stream():
        subscriber_id = status_queue.add_subscriber()
        try:
            # Send current status
            current_status = task_manager.last_status
            yield f"data: {json.dumps(current_status)}\n\n"

            # Continue sending status updates
            while True:
                try:
                    # Get status updates from queue
                    status_data = await asyncio.wait_for(
                        status_queue.get_status(),
                        timeout=30.0,
                    )
                    yield f"data: {json.dumps(status_data)}\n\n"
                except asyncio.TimeoutError:
                    # Send heartbeat to keep connection alive
                    _data = json.dumps(
                        {
                            "type": "heartbeat",
                            "timestamp": time.time(),
                        },
                    )
                    yield f"data: {_data}\n\n"
                except Exception as e:
                    print(f"Error in event stream: {e}")
                    break
        except Exception as e:
            print(f"SSE connection error: {e}")
        finally:
            status_queue.remove_subscriber(subscriber_id)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Cache-Control",
        },
    )


# Status callback function
async def status_callback(status_data: dict):
    """Status callback - update status and add to queue"""
    task_manager.update_status(status_data)
    await status_queue.put_status(task_manager.last_status)


async def run_task_background(task: str, config: AgentConfig):
    """Execute task in background"""
    try:
        # Update status: starting
        config_dict = (
            config.dict() if hasattr(config, "dict") else config.__dict__
        )
        config_without_static_url = {
            k: v for k, v in config_dict.items() if k != "static_url"
        }

        await status_callback(
            {
                "status": "starting",
                "type": "SYSTEM",
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "message": f"Initializing agent: task={task}, "
                f"config={config_without_static_url}",
            },
        )
        # Create agent
        if config.sandbox_type == "e2b-desktop":
            task_manager.agent = ComputerUseAgent(
                task_manager.equipment,
                task_manager.output_dir,
                sandbox_type=config.sandbox_type,
                status_callback=status_callback,
                mode=config.mode,
                pc_use_add_info=config.pc_use_addon_info,
                max_steps=config.max_steps,
            )
        else:
            raise ValueError()

        await asyncio.sleep(2)  # Wait 2 seconds for sandbox initialization

        # Set agent cancellation flag
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, task_manager.agent.run, task)

        # Task completed
        await status_callback(
            {
                "status": "completed",
                "type": "SYSTEM",
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "message": "Task completed successfully, output_dir: "
                + task_manager.output_dir,
            },
        )

    except Exception as e:
        # Task failed
        await status_callback(
            {
                "status": "error",
                "type": "SYSTEM",
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "message": "Task failed: " + str(e),
            },
        )
    finally:
        # Clean up resources
        task_manager.stop_task()


# API endpoints
@app.post("/cua/run", response_model=dict)
async def run_task(request: RunRequest):
    """Start new task"""
    try:
        # Extract task content
        if not request.messages:
            raise HTTPException(status_code=400, detail="No messages provided")

        task_text = request.messages[-1].content[0].text
        if not task_text:
            raise HTTPException(
                status_code=400,
                detail="No task text provided",
            )

        # Start task
        task_info = task_manager.start_task(
            {
                "task": task_text,
                "config": request.config,
            },
        )
        time.sleep(8)
        # Run task in background
        background_task = asyncio.create_task(
            run_task_background(task_text, request.config),
        )
        task_manager.background_tasks = background_task

        return {
            "success": True,
            "message": "Task started successfully",
            **task_info,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start task: {str(e)}",
        )


@app.get("/cua/status", response_model=StatusResponse)
async def get_status():
    """Get current task status"""
    return StatusResponse(**task_manager.last_status)


@app.post("/cua/stop")
async def stop_task():
    """Stop current task"""
    if not task_manager.is_running:
        raise HTTPException(
            status_code=409,
            detail="No task is currently running",
        )

    try:
        background_task = task_manager.background_tasks
        if background_task and not background_task.done():
            background_task.cancel()  # Cancel task
            task_manager.agent.stop()
            try:
                await background_task  # Wait for task cancellation
                print("Stopping task from API")
            except asyncio.CancelledError:
                pass
        task_manager.stop_task()
        await status_callback(
            {
                "status": "stopped",
                "message": "Task stopped by user request",
            },
        )
        return {"success": True, "message": "Task stopped successfully"}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to stop task: {str(e)}",
        )


@app.post("/cua/interrupt_wait")
async def interrupt_wait_task():
    """Interrupt current task waiting"""
    if not task_manager.is_running:
        raise HTTPException(
            status_code=409,
            detail="No task is currently running",
        )

    try:
        background_task = task_manager.background_tasks
        if background_task:
            task_manager.agent.interrupt_wait()
        await status_callback(
            {
                "status": "interrupt_wait_task",
                "message": "Task interrupt wait",
            },
        )
        return {"success": True, "message": "Task interrupt wait successfully"}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to stop task: {str(e)}",
        )


@app.get("/cua/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "is_running": task_manager.is_running,
        "task_id": task_manager.task_id,
        "has_sandbox": task_manager.sandbox is not None,
    }


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Computer Use Agent Backend",
        "status": "running",
        "endpoints": {
            "run_task": "/cua/run",
            "get_status": "/cua/status",
            "stop_task": "/cua/stop",
            "health": "/cua/health",
            "status_stream": "/sse/status",
        },
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend_base:app", host="0.0.0.0", port=8002, reload=True)
