import asyncio
import json
import re
from typing import Any, List, Optional, Union

from openai.types.chat import ChatCompletionMessageToolCall
from openai.types.chat.chat_completion_message_tool_call import Function
from pydantic import Field

from app.agent.react import ReActAgent
from app.exceptions import TokenLimitExceeded
from app.logger import logger
from app.prompt.manus import select_single_tools, add_think
from app.prompt.toolcall import NEXT_STEP_PROMPT, SYSTEM_PROMPT
from app.schema import TOOL_CHOICE_TYPE, AgentState, Message, ToolCall, ToolChoice
from app.tool import CreateChatCompletion, Terminate, ToolCollection

TOOL_CALL_REQUIRED = "Tool calls required but none provided"


class ToolCallAgent(ReActAgent):
    """Base agent class for handling tool/function calls with enhanced abstraction"""

    name: str = "toolcall"
    description: str = "an agent that can execute tool calls."

    system_prompt: str = SYSTEM_PROMPT
    next_step_prompt: str = NEXT_STEP_PROMPT

    available_tools: ToolCollection = ToolCollection(
        CreateChatCompletion(), Terminate()
    )
    tool_choices: TOOL_CHOICE_TYPE = ToolChoice.AUTO  # type: ignore
    special_tool_names: List[str] = Field(default_factory=lambda: [Terminate().name])

    tool_calls: List[ToolCall] = Field(default_factory=list)
    _current_base64_image: Optional[str] = None

    max_steps: int = 30
    max_observe: Optional[Union[int, bool]] = None

    async def think(self) -> bool:
        """Process current state and decide next actions using tools"""
        # if self.next_step_prompt:
        #     user_msg = Message.user_message(self.next_step_prompt)
        #     self.messages += [user_msg]

        # system_msgs = (
        #     [Message.system_message(self.system_prompt)]
        #     if self.system_prompt
        #     else None
        # )
        """code-fix-begin"""
        system_msg = self.system_prompt if self.system_prompt else ""
        next_step_prompt = self.next_step_prompt if self.next_step_prompt else ""
        if system_msg in self.messages[0].content:
            next_step_prompt = Message.user_message(next_step_prompt)
            self.messages += [next_step_prompt]
            self.memory.add_reasoning_trace(next_step_prompt)
        else:
            self.messages = [Message.user_message(system_msg)] + self.messages + [Message.user_message(next_step_prompt)]
            self.memory.reasoning_trace.insert(0, Message.user_message(system_msg))
            self.memory.add_reasoning_trace(Message.user_message(next_step_prompt))

        """code-fix-end"""

        try:
            # Get response with tool options
            # response = await self.llm.ask_tool(
            #     messages=self.messages,
            #     system_msgs=(
            #         [Message.system_message(self.system_prompt)]
            #         if self.system_prompt
            #         else None
            #     ),
            #     tools=self.available_tools.to_params(),
            #     tool_choice=self.tool_choices,
            # )
            """code-fix-begin"""
            # 删除过往历史中的next_step_prompt
            cur_llm_msg = []
            for msg in self.messages:
                if msg.role == "user" and self.next_step_prompt in msg.content:
                    continue
                cur_llm_msg.append(msg)
            cur_llm_msg = cur_llm_msg + [Message.user_message(self.next_step_prompt)]

            """code-fix-end"""

            response = await self.llm.ask_tool(
                messages=cur_llm_msg,
                system_msgs=None,
                tools=self.available_tools.to_params(),
                tool_choice=self.tool_choices,
            )
        except ValueError:
            raise
        except Exception as e:
            # Check if this is a RetryError containing TokenLimitExceeded
            if hasattr(e, "__cause__") and isinstance(e.__cause__, TokenLimitExceeded):
                token_limit_error = e.__cause__
                logger.error(
                    f"🚨 Token limit error (from RetryError): {token_limit_error}"
                )
                self.memory.add_message(
                    Message.assistant_message(
                        f"Maximum token limit reached, cannot continue execution: {str(token_limit_error)}"
                    )
                )
                self.state = AgentState.FINISHED
                return False
            raise

        if self.llm.model == "QwQ-32B-Friday":
            if response and response.model_extra:
                logger.info(response.model_extra.get("reasoning_content", ""))
            content_qwq = response.content.split('</tool_call>')[0].replace("\n", "").replace("<tool_call>", "").replace("</tool_call>", "")
            logger.info("------")
            logger.info(content_qwq, "手动解析")
            logger.info("------")
            try:
                content_qwq = json.loads(content_qwq)
                name = content_qwq['name']
                arguments = json.dumps(content_qwq['arguments'], ensure_ascii=False)
                self.tool_calls = [ChatCompletionMessageToolCall(id='call_9c1MFxhEKORFYuFERaJVl0ML',
                                                                 type="function", function=Function(name=name, arguments=arguments))]
                response.tool_calls = self.tool_calls
                tool_calls = self.tool_calls
            except Exception as e:
                logger.info(f"qwq parse error:{e}")
                pattern = r'"name":\s*"(\w+)",\s*"arguments":\s*\{([^}]+)\}'
                match = re.search(pattern, content_qwq)
                if match:
                    # 提取name
                    name = match.group(1)
                    # 提取arguments，并转换为字典
                    arguments_str = "{" + match.group(2) + "}"
                    self.tool_calls = [ChatCompletionMessageToolCall(id='call_9c1MFxhEKORFYuFERaJVl0ML',
                                                                     type="function", function=Function(name=name, arguments=arguments_str))]
                    response.tool_calls = self.tool_calls
                    tool_calls = self.tool_calls
                self.tool_calls = tool_calls = []
        else:
            # self.tool_calls = tool_calls = (
            #     response.tool_calls if response and response.tool_calls else []
            # )

            """code-fix-begin：terminate只能单独出现"""
            tool_calls_filter1 = (
                response.tool_calls if response and response.tool_calls else []
            )
            if select_single_tools:
                # 只选择一个tools
                logger.info(f"选择前工具的数量:{len(tool_calls_filter1)}")
                tool_calls_filter1 = tool_calls_filter1[:1]
                logger.info(f"选择后工具的数量:{len(tool_calls_filter1)}")

            tool_calls_filter2 = []
            # 先过滤掉terminate
            if len(tool_calls_filter1) > 1:
                # 如果当前有多个tool_call,那么过滤掉terminate
                for call in tool_calls_filter1:
                    if call.function.name != "terminate":
                        tool_calls_filter2.append(call)
            elif len(tool_calls_filter1) == 1:
                tool_calls_filter2 = tool_calls_filter1
            else:
                tool_calls_filter2 = []
            self.tool_calls = tool_calls = tool_calls_filter2
            """code-fix-end"""

        """code-fix-begin：解析terminate"""

        """code-fix-end：解析terminate"""

        """code-fix-begin：解析reasoning_content、content"""
        reasoning_content = None
        if response and response.model_extra:
            reasoning_content = response.model_extra.get("reasoning_content", "")
            logger.info("✨reasoning_content-BEGIN:" + str(reasoning_content) + "✨reasoning_content-END\n")
        content = response.content if response and response.content else ""
        logger.info(f"✨content-BEGIN: {content} -content-END")
        """code-fix-end"""

        logger.info(
            f"🛠️ {self.name} selected {len(tool_calls) if tool_calls else 0} tools to use"
        )
        if tool_calls:
            # logger.info(
            #     f"🧰 Tools being prepared: {[call.function.name for call in tool_calls]}"
            # )
            #
            # logger.info(f"🔧 Tool arguments: {tool_calls[0].function.arguments}")
            logger.info("---Function-Select-BEGIN----")
            for call in tool_calls:
                logger.info(str(call.function.name) + str(call.function.arguments))
            logger.info("---Function-Select-END----")

        try:
            # 增加think的内容到memory

            if response is None:
                raise RuntimeError("No response received from the LLM")

            # Handle different tool_choices modes
            # 正常应该是AUTO; NONE和REQUIRED目前不使用
            if self.tool_choices == ToolChoice.NONE:
                if tool_calls:
                    logger.warning(
                        f"🤔 Hmm, {self.name} tried to use tools when they weren't available!"
                    )
                if content:
                    self.memory.add_message(Message.assistant_message(content))
                    return True
                return False

            # Create and add assistant message
            """code-fix-begin： add-think-content to memory"""
            assistant_msg = (
                Message.assistant_message(content=f"assistant思考的内容<think>:{reasoning_content}<\\think>")
            )
            # 增加think的内容到memory
            if add_think and reasoning_content:
                self.memory.add_message(assistant_msg)
            if not add_think and reasoning_content:
                self.memory.add_reasoning_trace(assistant_msg)
            # 增加content的内容到memory-丢弃：content会和tool一起加入
            # if content and content!="\n\n":
            #     content_msg = Message.assistant_message(content=f"assistant正文内容<content>:{content}<\\content>")
            #     self.memory.add_reasoning_trace(content_msg)
            """code-fix-end:add-think-content to memory"""
            assistant_msg = (
                Message.from_tool_calls(content=content, tool_calls=self.tool_calls)
                if self.tool_calls
                else Message.assistant_message(content)
            )
            self.memory.add_message(assistant_msg)
            # code-fix-begin:保存reasoning_trace
            await self.parse_reasoning_trace(gpt4o_summary=False)

            if self.tool_choices == ToolChoice.REQUIRED and not self.tool_calls:
                return True  # Will be handled in act()

            # For 'auto' mode, continue with content if no commands but content exists
            if self.tool_choices == ToolChoice.AUTO and not self.tool_calls:
                return bool(content)

            return bool(self.tool_calls)
        except Exception as e:
            logger.error(f"🚨 Oops! The {self.name}'s thinking process hit a snag: {e}")
            self.memory.add_message(
                Message.assistant_message(
                    f"Error encountered while processing: {str(e)}"
                )
            )
            return False

    async def act(self) -> str:
        """Execute tool calls and handle their results"""
        if not self.tool_calls:
            if self.tool_choices == ToolChoice.REQUIRED:
                raise ValueError(TOOL_CALL_REQUIRED)

            # Return last message content if no tool calls
            return self.messages[-1].content or "No content or commands to execute"

        results = []
        for command in self.tool_calls:
            # Reset base64_image for each tool call
            self._current_base64_image = None

            result = await self.execute_tool(command)

            if self.max_observe:
                result = result[: self.max_observe]

            logger.info(
                f"🎯 Tool '{command.function.name}'-''{command.function.arguments}'' completed its mission! Result: {result}"
            )

            # Add tool response to memory
            tool_msg = Message.tool_message(
                content=result,
                tool_call_id=command.id,
                name=command.function.name,
                base64_image=self._current_base64_image,
            )
            self.memory.add_message(tool_msg)
            results.append(result)

        return "\n\n".join(results)

    async def execute_tool(self, command: ToolCall) -> str:
        """Execute a single tool call with robust error handling"""
        if not command or not command.function or not command.function.name:
            return "Error: Invalid command format"

        name = command.function.name
        if name not in self.available_tools.tool_map:
            return f"Error: Unknown tool '{name}'"

        try:
            # Parse arguments
            args = json.loads(command.function.arguments or "{}")

            # Execute the tool
            logger.info(f"🔧 Activating tool: '{name}'...")
            result = await self.available_tools.execute(name=name, tool_input=args)
            # Handle special tools
            await self._handle_special_tool(name=name, result=result)
            # Check if result is a ToolResult with base64_image
            if hasattr(result, "base64_image") and result.base64_image:
                # Store the base64_image for later use in tool_message
                self._current_base64_image = result.base64_image

                # Format result for display
                observation = (
                    f"Observed output of cmd `{name}` executed:\n{result}"
                    if result
                    else f"Cmd `{name}` completed with no output"
                )
                return observation

            # Format result for display (standard case)

            if name == "terminate" and "攻略不合格" in result:
                args['status'] = "failure"
            show_args = json.dumps(args, ensure_ascii=False, indent=4)
            observation = (
                f"Observed output of cmd {name}:{show_args} \n executed:\n{result}"
                if result
                else f"Cmd `{name}{args}` completed with no output"
            )

            """code-fix-begin：AgentState.RUNNING"""
            if name == "terminate" and args.get("status") == "failure":
                self.state = AgentState.RUNNING
            """code-fix-end：AgentState.RUNNING"""

            return observation
        except json.JSONDecodeError:
            error_msg = f"Error parsing arguments for {name}: Invalid JSON format"
            logger.error(
                f"📝 Oops! The arguments for '{name}' don't make sense - invalid JSON, arguments:{command.function.arguments}"
            )
            return f"Error: {error_msg}"
        except Exception as e:
            error_msg = f"⚠️ Tool '{name}' encountered a problem: {str(e)}"
            logger.exception(error_msg)
            return f"Error: {error_msg}"

    async def _handle_special_tool(self, name: str, result: Any, **kwargs):
        """Handle special tool execution and state changes"""
        if not self._is_special_tool(name):
            return

        if self._should_finish_execution(name=name, result=result, **kwargs):
            # Set agent state to finished
            logger.info(f"🏁 Special tool '{name}' has completed the task!")
            self.state = AgentState.FINISHED

    @staticmethod
    def _should_finish_execution(**kwargs) -> bool:
        """Determine if tool execution should finish the agent"""
        return True

    def _is_special_tool(self, name: str) -> bool:
        """Check if tool name is in special tools list"""
        return name.lower() in [n.lower() for n in self.special_tool_names]

    async def cleanup(self):
        """Clean up resources used by the agent's tools."""
        logger.info(f"🧹 Cleaning up resources for agent '{self.name}'...")
        for tool_name, tool_instance in self.available_tools.tool_map.items():
            if hasattr(tool_instance, "cleanup") and asyncio.iscoroutinefunction(
                    tool_instance.cleanup
            ):
                try:
                    logger.debug(f"🧼 Cleaning up tool: {tool_name}")
                    await tool_instance.cleanup()
                except Exception as e:
                    logger.error(
                        f"🚨 Error cleaning up tool '{tool_name}': {e}", exc_info=True
                    )
        logger.info(f"✨ Cleanup complete for agent '{self.name}'.")

    async def run(self, request: Optional[str] = None) -> str:
        """Run the agent with cleanup when done."""
        try:
            return await super().run(request)
        finally:
            await self.cleanup()
