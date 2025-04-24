import asyncio
import pandas as pd
from app.agent.manus import Manus
from app.logger import logger


async def main(prompt):
    agent = Manus()
    try:
        # prompt = input("Enter your prompt: ")
        # prompt = "帮我生成一个从上海去洛阳的四日游旅游攻略，最后请整理成一个完整的四日游攻略，我打算这周六到下周二四天时间"
        # prompt = "我想要制定一个旅行计划，从海口出发，去陵水游玩。我们计划在2025年10月1日到10月4日之间出行，同行的有两位大人和一个三岁小孩。整体预算希望在1万元以内。希望能找到性价比高的酒店，。在饮食方面，我们比较想尝试陵水的特色菜。至于景点，帮我找些适合3三岁孩子的景点。请帮我规划一下这次详细行程，需要给出完整的路线，包括往返交通、每天的游玩安排、就餐安排、酒店安排。"
        # prompt = "介绍洛阳博物馆"
        # prompt  = "帮我生成一个从西安到川西的五日游旅游计划，我打算下周五出发."
        # prompt = "帮我生成一个从西安到兰州的四日游旅游计划，我打算下周三出发."
        # prompt = "帮我生成一个从太原到大同的四日游旅游计划，预算3k"
        if not prompt.strip():
            logger.warning("Empty prompt provided.")
            return

        logger.warning("Processing your request...")
        await agent.run(prompt)
        logger.info("Request processing completed.")
    except KeyboardInterrupt:
        logger.warning("Operation interrupted.")
    finally:
        # Ensure agent resources are cleaned up before exiting
        await agent.cleanup()


if __name__ == "__main__":
    # query_df = pd.read_excel("travel_queries_200.xlsx")
    # query_df = query_df.sample(10, random_state=43)
    # queries = query_df['query'].tolist()

    # print(queries)
    # for query in queries:
    #     asyncio.run(main(query))
    asyncio.run(main("帮我生成一个从上海到苏州的两日游旅游计划，我打算立夏那天出发"))
    asyncio.run(main("我端午节从北京出发去太原玩三天，预算3k，我不想去应县木塔。"))
    asyncio.run(main("计划和同事们从上海去广州游玩3天，有哪些推荐的活动？"))
    asyncio.run(main("我国庆节想从郑州去北京玩3天"))
    asyncio.run(main("帮我生成一个从西安到川西的3日游旅游计划，我打算下周五出发"))
    asyncio.run(main("帮我生成一个从西安到兰州的三日游旅游计划，我打算端午节去."))
    asyncio.run(main("准备去重庆游玩3天，想体验当地的夜生活。"))
    asyncio.run(main("2025年春节，我想在西宁旅行，停留大约3天，希望能体验青海湖的自然风光，尽量安排避开人流密集的景点。"))
    asyncio.run(main("2025年寒假我要去西安，想寻找合适的文化游路线，怎么安排呢？"))

    test_query = ['帮我生成一个从西安到川西的五日游旅游计划，我打算下周五出发',
                  '帮我生成一个从西安到兰州的三日游旅游计划，我打算端午节去.',
                  '帮我生成一个从太原到大同的四日游旅游计划，预算3k，我不想去应县木塔。',
                  '帮我生成一个从上海到苏州的周末游旅游计划',
                  '计划和同事们在广州游玩5天，有哪些推荐的活动？',
                  '准备去重庆游玩3天，想体验当地的夜生活。',
                  '2025年春节，我想在西宁旅行，停留大约5天，希望能体验青海湖的自然风光，尽量安排避开人流密集的景点。',
                  '2025年寒假我要去西安，想寻找合适的文化游路线，怎么安排呢？']
