import hashlib
import json
import os
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from typing import List, Optional

import pandas as pd
from pydantic import BaseModel, Field, model_validator

from app.llm import LLM
from app.logger import logger
from app.prompt.manus import summary_llm_model_name, GPT4_SYSTEM_PROMPT
from app.sandbox.client import SANDBOX_CLIENT
from app.schema import ROLE_TYPE, AgentState, Memory, Message
from app.tool.llm_tools import gpt_request_2


class BaseAgent(BaseModel, ABC):
    """Abstract base class for managing agent state and execution.

    Provides foundational functionality for state transitions, memory management,
    and a step-based execution loop. Subclasses must implement the `step` method.
    """

    # Core attributes
    name: str = Field(..., description="Unique name of the agent")
    description: Optional[str] = Field(None, description="Optional agent description")

    # Prompts
    system_prompt: Optional[str] = Field(
        None, description="System-level instruction prompt"
    )
    next_step_prompt: Optional[str] = Field(
        None, description="Prompt for determining next action"
    )

    # Dependencies
    llm: LLM = Field(default_factory=LLM, description="Language model instance")
    memory: Memory = Field(default_factory=Memory, description="Agent's memory store")
    state: AgentState = Field(
        default=AgentState.IDLE, description="Current agent state"
    )

    # Execution control
    max_steps: int = Field(default=10, description="Maximum steps before termination")
    current_step: int = Field(default=0, description="Current step in execution")

    duplicate_threshold: int = 2

    class Config:
        arbitrary_types_allowed = True
        extra = "allow"  # Allow extra fields for flexibility in subclasses

    @model_validator(mode="after")
    def initialize_agent(self) -> "BaseAgent":
        """Initialize agent with default settings if not provided."""
        if self.llm is None or not isinstance(self.llm, LLM):
            self.llm = LLM(config_name=self.name.lower())
        if not isinstance(self.memory, Memory):
            self.memory = Memory()
        return self

    @asynccontextmanager
    async def state_context(self, new_state: AgentState):
        """Context manager for safe agent state transitions.

        Args:
            new_state: The state to transition to during the context.

        Yields:
            None: Allows execution within the new state.

        Raises:
            ValueError: If the new_state is invalid.
        """
        if not isinstance(new_state, AgentState):
            raise ValueError(f"Invalid state: {new_state}")

        previous_state = self.state
        self.state = new_state
        try:
            yield
        except Exception as e:
            self.state = AgentState.ERROR  # Transition to ERROR on failure
            raise e
        finally:
            self.state = previous_state  # Revert to previous state

    def update_memory(
            self,
            role: ROLE_TYPE,  # type: ignore
            content: str,
            base64_image: Optional[str] = None,
            **kwargs,
    ) -> None:
        """Add a message to the agent's memory.

        Args:
            role: The role of the message sender (user, system, assistant, tool).
            content: The message content.
            base64_image: Optional base64 encoded image.
            **kwargs: Additional arguments (e.g., tool_call_id for tool messages).

        Raises:
            ValueError: If the role is unsupported.
        """
        message_map = {
            "user": Message.user_message,
            "system": Message.system_message,
            "assistant": Message.assistant_message,
            "tool": lambda content, **kw: Message.tool_message(content, **kw),
        }

        if role not in message_map:
            raise ValueError(f"Unsupported message role: {role}")

        # Create message with appropriate parameters based on role
        kwargs = {"base64_image": base64_image, **(kwargs if role == "tool" else {})}
        self.memory.add_message(message_map[role](content, **kwargs))

    async def use_gpt4o_for_summary(self, request: str, cur_reasoning_trace) -> str:
        cur_reasoning_trace2 = cur_reasoning_trace[:]

        gpt_corpus = []
        cur_guide = []
        for msg in cur_reasoning_trace2:
            if msg["role"] == "user":
                gpt_corpus.append(f"用户: {msg['content']}")
            elif msg["role"] == "obv" and "terminate" not in msg["content"]:
                gpt_corpus.append(f"助手: {msg['content']}")
            # elif msg["role"] == "obv" and "terminate" in msg["content"] and "输出最终版" in msg["content"]:
            #     cur_guide = msg['content']
            else:
                continue
        corpus = "\n".join(gpt_corpus)

        messages = [{"role": "system", "content": GPT4_SYSTEM_PROMPT},
                    {"role": "user", "content": f"用户当前的问题是:{request},你所有的回复都必须基于这里的参考材料：{corpus}"}]
        gpt_extract = gpt_request_2(messages=messages, model=summary_llm_model_name, max_output=5000)
        gpt_extract = gpt_extract.replace("(required)", "")
        return gpt_extract

    async def parse_reasoning_trace(self, request: str = None, gpt4o_summary: bool = True):
        # 解析保存路径推理路径
        cur_reasoning_trace = []
        for msg in self.memory.reasoning_trace:
            if msg.role == "user":
                if self.system_prompt in msg.content:
                    cur_reasoning_trace.append({"role": "system_prompt", "content": msg.content, "loss": False})
                elif self.next_step_prompt in msg.content:
                    cur_reasoning_trace.append({"role": "next_step_prompt", "content": msg.content, "loss": False})
                else:
                    cur_reasoning_trace.append({"role": "user", "content": msg.content, "loss": False})
                    if not request:
                        request = msg.content
            elif msg.role == "assistant":
                tool_calls = msg.tool_calls if msg.tool_calls else None
                content = msg.content if msg.content and msg.content != '' else None
                if not content and not tool_calls:
                    continue
                if content and content != "\n\n":
                    # think
                    cur_reasoning_trace.append({"role": "think", "content": content, "loss": True})
                if tool_calls:
                    # act
                    acts = []

                    for tool_call in tool_calls:
                        acts.append({"function": tool_call.function.name, "arguments": tool_call.function.arguments})
                    cur_reasoning_trace.append({"role": "act", "content": acts, "loss": True})
            elif msg.role == "tool":
                # obv
                cur_reasoning_trace.append({"role": "obv", "content": msg.content, "loss": False})
            else:
                logger.info(f"未知角色: {msg.role}")

        if gpt4o_summary:
            gpt4o_summary = await self.use_gpt4o_for_summary(request, cur_reasoning_trace)
            cur_reasoning_trace.append({"role": "gpt4o_summary", "content": gpt4o_summary, "loss": False})

        SAVE_PATH = "/Users/winslow/Desktop/travel_agent/travelplanagent/OpenManus_pro/Reasoning_trajectory"
        if not os.path.exists(SAVE_PATH):
            os.makedirs(SAVE_PATH)
        # 将request进行映射为一个可逆的数字
        hashed_query = hashlib.md5(request.encode()).hexdigest()
        # 保存为json文件
        with open(os.path.join(SAVE_PATH, f"{hashed_query}.json"), "w") as f:
            json.dump(cur_reasoning_trace, f, ensure_ascii=False, indent=4)

        df = pd.DataFrame(cur_reasoning_trace)
        df.to_excel(os.path.join(SAVE_PATH, f"{hashed_query}.xlsx"), index=False)

    async def run(self, request: Optional[str] = None) -> str:
        """Execute the agent's main loop asynchronously.

        Args:
            request: Optional initial user request to process.

        Returns:
            A string summarizing the execution results.

        Raises:
            RuntimeError: If the agent is not in IDLE state at start.
        """
        if self.state != AgentState.IDLE:
            raise RuntimeError(f"Cannot run agent from state: {self.state}")

        if request:
            self.update_memory("user", request)

        results: List[str] = []
        async with self.state_context(AgentState.RUNNING):
            while (
                    self.current_step < self.max_steps and self.state != AgentState.FINISHED
            ):
                self.current_step += 1
                logger.info(f"Executing step {self.current_step}/{self.max_steps}")
                step_result = await self.step()

                # Check for stuck state
                if self.is_stuck():
                    self.handle_stuck_state()

                results.append(f"Step {self.current_step}: {step_result}")

            """code-fix-begin-解析reasoning_trace"""
            await self.parse_reasoning_trace(request)
            """code-fix-bend-解析reasoning_trace"""

            if self.current_step >= self.max_steps:
                self.current_step = 0
                self.state = AgentState.IDLE
                results.append(f"Terminated: Reached max steps ({self.max_steps})")
        await SANDBOX_CLIENT.cleanup()
        return "\n".join(results) if results else "No steps executed"

    @abstractmethod
    async def step(self) -> str:
        """Execute a single step in the agent's workflow.

        Must be implemented by subclasses to define specific behavior.
        """

    def handle_stuck_state(self):
        """Handle stuck state by adding a prompt to change strategy"""
        stuck_prompt = "\
        Observed duplicate responses. Consider new strategies and avoid repeating ineffective paths already attempted."
        self.next_step_prompt = f"{stuck_prompt}\n{self.next_step_prompt}"
        logger.warning(f"Agent detected stuck state. Added prompt: {stuck_prompt}")

    def is_stuck(self) -> bool:
        """Check if the agent is stuck in a loop by detecting duplicate content"""
        if len(self.memory.messages) < 2:
            return False

        last_message = self.memory.messages[-1]
        if not last_message.content:
            return False

        # Count identical content occurrences
        duplicate_count = sum(
            1
            for msg in reversed(self.memory.messages[:-1])
            if msg.role == "assistant" and msg.content == last_message.content
        )

        return duplicate_count >= self.duplicate_threshold

    @property
    def messages(self) -> List[Message]:
        """Retrieve a list of messages from the agent's memory."""
        return self.memory.messages

    @messages.setter
    def messages(self, value: List[Message]):
        """Set the list of messages in the agent's memory."""
        self.memory.messages = value
