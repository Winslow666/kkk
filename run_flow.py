import asyncio
import time

from app.agent.manus import Manus
from app.flow.flow_factory import FlowFactory, FlowType
from app.logger import logger


async def run_flow():
    agents = {
        "manus": Manus(),
    }

    try:
        prompt = input("Enter your prompt: ")
        # prompt = "帮我生成五一假期一个从北京去洛阳的五日游旅游攻略。我要在第一天中午出发，第五天下午回北京。。一个人预算4000块钱。请你将最终的攻略保存到一个txt文件"
        prompt = "我想要制定一个旅行计划，从海口出发，去陵水游玩。我们计划在五一期间出行，同行的有两位大人和一个三岁小孩。整体预算希望在1万元以内。希望能找到性价比高的酒店。在饮食方面，我们比较想尝试陵水的特色菜。至于景点，帮我找些适合3三岁孩子的景点。请帮我规划一下这次行程。"

        if prompt.strip().isspace() or not prompt:
            logger.warning("Empty prompt provided.")
            return

        flow = FlowFactory.create_flow(
            flow_type=FlowType.PLANNING,
            agents=agents,
        )
        logger.warning("Processing your request...")

        try:
            start_time = time.time()
            result = await asyncio.wait_for(
                flow.execute(prompt),
                timeout=3600,  # 60 minute timeout for the entire execution
            )
            elapsed_time = time.time() - start_time
            logger.info(f"Request processed in {elapsed_time:.2f} seconds")
            logger.info(result)
        except asyncio.TimeoutError:
            logger.error("Request processing timed out after 1 hour")
            logger.info(
                "Operation terminated due to timeout. Please try a simpler request."
            )

    except KeyboardInterrupt:
        logger.info("Operation cancelled by user.")
    except Exception as e:
        logger.error(f"Error: {str(e)}")


if __name__ == "__main__":
    asyncio.run(run_flow())
