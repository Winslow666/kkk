import asyncio
import random
import time

from app.logger import logger

from app.tool.base import BaseTool
import httpx
import json
from app.tool.llm_tools import gpt_request_2

_PoiInfoSearch_DESCRIPTION = """通过城市名称和景点名称，查询景点的介绍信息，注意这个工具不能查询餐厅和酒店的信息"""


class PoiInfoSearchTool(BaseTool):
    name: str = "poiInfoSearch"
    description: str = _PoiInfoSearch_DESCRIPTION
    parameters: dict = {
        "type": "object",
        "properties": {
            "landmark": {
                "type": "string",
                "description": "查询景厅的名称。如天安门、颐和园、故宫"
            },
            "cityName": {
                "type": "string",
                "description": "城市名称，如北京、天津。"
            }
        },
        "required": ["cityName", "landmark"],
    }

    async def execute(self, cityName: str, landmark: str) -> str:

        max_retries = 3
        for retry in range(max_retries):
            url = 'https://aigc.sankuai.com/v1/friday/api/search'
            headers = {
                'Authorization': 'Bearer 1845658056894631981',
                'Content-Type': 'application/json'
            }
            query = f"{cityName}{landmark} 信息，门票价格"
            data = {
                "query": query,
                "api": "bing-search",
                "is_fast": False,
                "top_k": 2
            }
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(url, headers=headers, json=data, timeout=200)
                    snippets, contents, url = [], [], []
                    if response.status_code == 200:
                        cur_result = response.json()['results']
                        for item in cur_result:
                            if "snippet" in item and "无法提供该页面的具体描述" not in item["snippet"]:
                                snippets.append(item["snippet"])
                            if "content" in item:
                                contents.append(item["content"].replace("\n", "").replace("\t", "")[:3000])
                            if "link" in item:
                                url.append(item["link"])
                    else:
                        time.sleep(5)
                        continue

                    logger.info(f"query:{query}-检索URL：{url}")
                    web_info = f"snippets: {'[sep]'.join(snippets)} \n contents: {'[sep]'.join(contents)}"
                    gpt_extract = gpt_request_2(
                        messages=[{"role": "system",
                                   "content": f"""现在搜索【{query}】，检索结果如下：\n{web_info}\n你需要通过用户的输入来从检索结果中抽取出相关的文字表达，你抽取的景点介绍信息内容要丰富全面，。"""},
                                  {"role": "user", "content": f"当前用户的查询是：{query}"}])

                    if gpt_extract:
                        return gpt_extract
                    else:
                        return f"poi景点信息检索失败。"
            except Exception as e:
                if retry == max_retries - 1:  # 最后一次重试失败
                    logger.info(f"poi景点信息-bing检索失败，重试{max_retries}次后仍然失败，错误信息：{e}")
                    return "poi景点信息检索失败"
                logger.info(f"poi景点信息-bing检索失败，错误信息：{e}")
                await asyncio.sleep(1)


# 陵水乐天归心居、介绍陵水分界洲岛 携程
async def test_poi_search():
    # 创建工具实例
    poi_tool = PoiInfoSearchTool()

    city_name = "长沙"
    landmark = "岳麓山"

    try:
        # 执行搜索
        result = await poi_tool.execute(cityName=city_name, landmark=landmark)
        print(f"搜索结果: {result}")
    except Exception as e:
        print(f"测试失败: {str(e)}")


if __name__ == "__main__":
    asyncio.run(test_poi_search())
