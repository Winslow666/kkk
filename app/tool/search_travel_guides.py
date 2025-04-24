import asyncio
from app.logger import logger

from app.tool.base import BaseTool
import httpx
import json
from app.tool.llm_tools import gpt_request_2

_SEARCH_TRAVEL_DESCRIPTION = """查找一份已有的旅游攻略，需要输入一个查询query词，如“北京五日游攻略”。然后返回一份可以用于参考的旅游攻略，query词不要出发城市，"""""


class SearchTravelGuideTool(BaseTool):
    name: str = "searchTravelGuide"
    description: str = _SEARCH_TRAVEL_DESCRIPTION
    parameters: dict = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "一个查询词可以返回一些参考的旅游攻略，query词不要出发城市，如禁止出现‘北京到上海三日游攻略’的表达，因为出现了出发城市北京，正确的搜索词是“上海三日游攻略”，即【城市+天数】的形式"
            }
        },
        "required": ["query"],
    }

    async def execute(self, query: str) -> str:
        url = 'https://aigc.sankuai.com/v1/friday/api/search'
        headers = {
            'Authorization': 'Bearer 1845658056894631981',
            'Content-Type': 'application/json'
        }
        data = {
            "query": "小红书、携程网" + query,
            "api": "bing-search",
            "is_fast": False,
            "top_k": 3
        }

        max_retries = 3
        for retry in range(max_retries):
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(url, headers=headers, json=data, timeout=200)
                    snippets, contents, url = [], [], []
                    if response.status_code == 200:
                        cur_result = response.json()['results']
                        for item in cur_result:

                            # if "snippet" in item and "无法提供该页面的具体描述" not in item["snippet"]:
                            #     snippets.append(item["snippet"])
                            if "content" in item:
                                contents.append(item["content"].replace("\n", "").replace("\t", "")[:3000])
                            if "link" in item:
                                url.append(item["link"])

                    logger.info(f"query:{query}-检索URL：{url}")
                    web_info = "\n".join(contents)
                    gpt_extract = gpt_request_2(
                        messages=[{"role": "user",
                                   "content": f"""现在通过网络搜索{query}，检索结果如下：\n{web_info}\n，
                                   请你根据{query}总结一份用于参考的攻略，但是你不可以瞎编乱造，你输出攻略的所有信息都要依赖于检索结果。并且你输出的内容要详细丰富，
                                   一定要保留往返交通、高铁、火车、景点的详细介绍、餐厅、酒店等重要信息信息。信息越丰富越好"""}],
                        max_output=3000,
                        model="LongCat-Large-32K-Chat")
                    gpt_extract = gpt_extract.replace("\t", "")
                    return f"这是一份可以参考的旅游攻略，你可以进行参考这份攻略的每日景点安排：{gpt_extract}"
            except Exception as e:
                if retry == max_retries - 1:  # 最后一次重试失败
                    logger.info(f"searchTravelGuide失败，重试{max_retries}次后仍然失败，错误信息：{e}")
                    return "searchTravelGuide"
                logger.info(f"searchTravelGuide，错误信息：{e}")
                await asyncio.sleep(1)


async def main():
    # 创建工具实例
    search_tool = SearchTravelGuideTool()

    # 测试查询
    test_queries = [
        "大同四日游攻略"
    ]

    # 测试每个查询
    for query in test_queries:
        print(f"\n正在搜索: {query}")
        try:
            result = await search_tool.execute(query)
            print(f"搜索结果:\n{result}\n")
            print("-" * 50)
        except Exception as e:
            print(f"搜索失败: {e}")


if __name__ == "__main__":
    # 运行异步主函数
    asyncio.run(main())
