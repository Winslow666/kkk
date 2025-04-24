import asyncio
from app.logger import logger

from app.tool.base import BaseTool
import httpx
import json
from app.tool.llm_tools import gpt_request_2

_WEATHER_DESCRIPTION = """通过接入bing连接网络，搜索相关信息."""


class WebSearchTool(BaseTool):
    name: str = "webSearch"
    description: str = _WEATHER_DESCRIPTION
    parameters: dict = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "用户进行网络查询的query，如“北京国庆天气一般怎么样”"
            }
        },
        "required": ["query"],
    }

    async def execute_fuxi(self, query: str) -> str:
        url = 'https://fuxi.sankuai.com/api/flow/run'
        headers = {
            'Content-Type': 'application/json'
        }
        data = {
            "flowId": 4403,
            "inputParams": {
                "query": query,
                "top_k": 2
            }
        }

        max_retries = 3
        for retry in range(max_retries):
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(url, headers=headers, json=data, timeout=200)
                    info = response.json()
                    web_info = info['data']['web_info']

                    res = json.loads(json.loads(web_info))['results']
                    snippet = []
                    content = []
                    url = []
                    for item in res:
                        content.append(item['content'])
                        snippet.append(item['snippet'])
                        url.append(item['link'])
                    logger.info(f"{query}检索URL：{url}")
                    web_info = f"snippet: {snippet} \n content: {content}"

                    gpt_extract =  gpt_request_2(
                        messages=[{"role": "system",
                                   "content": f"""现在通过bing搜索{query}，检索结果如下：\n{web_info}\n你需要通过用户的输入来从检索结果中抽取出相关的文字表达，你抽取的信息要结构清洗，内容全面。尽可能丰富，数据多一些。"""},
                                  {"role": "user", "content": f"当前用户的查询是：{query}"}])
                    # return web_info
                    return gpt_extract

            except Exception as e:
                if retry == max_retries - 1:  # 最后一次重试失败
                    logger.info(f"bing检索失败，重试{max_retries}次后仍然失败，错误信息：{e}")
                    return "bing检索失败"
                logger.info(f"bing检索失败，错误信息：{e}")
                await asyncio.sleep(1)

    async def execute(self, query: str) -> str:
        url = 'https://aigc.sankuai.com/v1/friday/api/search'
        headers = {
            'Authorization': 'Bearer 1845658056894631981',
            'Content-Type': 'application/json'
        }
        data = {
            "query": query,
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

                            if "snippet" in item and "无法提供该页面的具体描述" not in item["snippet"]:
                                snippets.append(item["snippet"])
                            if "content" in item:
                                contents.append(item["content"].replace("\n", "").replace("\t", ""))
                            if len(contents) >= 3:
                                break
                            if "link" in item:
                                url.append(item["link"])

                    logger.info(f"query:{query}-检索URL：{url}")
                    web_info = f"snippets: {snippets} \n contents: {contents}"
                    gpt_extract =  gpt_request_2(
                        messages=[{"role": "system",
                                   "content": f"""现在通过bing搜索{query}，检索结果如下：\n{web_info}\n
                                   你需要通过用户的输入来从检索结果中抽取出相关的文字表达，你抽取的信息内容要丰富全面，与旅行相关的都需要保存，如景点、酒店住宿、餐厅，特色游玩信息等。
                                    不需要抽取电话、联系方式、邮箱、预约电话"""},
                                  {"role": "user", "content": f"当前用户的查询是：{query}"}],
                        max_output=3000)
                    # return web_info
                    return gpt_extract
            except Exception as e:
                if retry == max_retries - 1:  # 最后一次重试失败
                    logger.error(f"bing检索失败，重试{max_retries}次后仍然失败，错误信息：{e}")
                    return "bing检索失败"
                logger.info(f"bing检索失败，错误信息：{e}")
                await asyncio.sleep(1)
