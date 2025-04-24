import asyncio
import random
import time

from app.tool.base import BaseTool
import httpx
import json

from app.tool.cityName2cityId import cityName2cityId
from app.tool.llm_tools import gpt_request_2

_PoiInfoSearchBATCH_DESCRIPTION = """通过城市名称和景点名称，查询景点的具体介绍信息和门票信息，可以支持一次性查询多个景点信息。"""

"""parameters: dict = {
    "type": "object",
    "properties": {
        "poiList": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "城市名称"
                    },
                    "landmark": {
                        "type": "string",
                        "description": "景点名称"
                    }
                },
                "required": ["city", "landmark"]
            },
            "description": "城市和景点信息列表"
        }
    },
    "required": ["poiList"]
}"""

system_prompt = """
我将给你一些从网络上抓取的景点介绍信息，现在需要你抽取出核心的景点介绍信息、门票价格、特色游玩信息。你的输出格式为一个json字典。如下格式{"introduction":"","ticket_price":"","attractions":""}
introduction：景点介绍信息，约300个字符。
ticket_price：景点门票价格,注意儿童、成人票等区分。同时注意景点与价格的对应关系。
attractions：景点特色游玩信息。约80个字符。
你不能瞎编乱造，仅能通过提供的被===包围的信息中进行抽取
===
{web_info}
===
"""


class PoiInfoSearchBatchTool(BaseTool):
    name: str = "poiInfoSearchBatch"
    description: str = _PoiInfoSearchBATCH_DESCRIPTION
    parameters: dict = {
        "type": "object",
        "properties": {
            "city_with_poi_name": {
                "type": "string",
                "description": '一个json格式list：[["城市名称1"，"景点名称1"],["城市名称2"，"景点名称2"],["城市名称3"，"景点名称3"]]，举个例子:[["北京","天安门"],["大同","华严寺"]]'
            }
        },
        "required": ["city_with_poi_name"],
    }

    async def get_poi_info_web(self, cityName: str, landmark: str) -> str:
        max_retries = 2
        for retry in range(max_retries):
            url = 'https://aigc.sankuai.com/v1/friday/api/search'
            headers = {
                'Authorization': 'Bearer 1845658056894631981',
                'Content-Type': 'application/json'
            }
            query = f"介绍{cityName}{landmark}信息，景区门票信息"
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
                                   "content": system_prompt.replace("{web_info}", web_info)},
                                  {"role": "user", "content": f"当前用户查询的景点是：{query}"}])

                    if gpt_extract:
                        web_poi_info = json.loads(gpt_extract.replace("json", "").replace("```", ""))
                        return "。".join(web_poi_info.values())
                    else:
                        return f"{cityName}{landmark}景点信息检索失败。"
            except Exception as e:
                if retry == max_retries - 1:  # 最后一次重试失败
                    logger.info(f"poi景点信息-bing检索失败，重试{max_retries}次后仍然失败，错误信息：{e}")
                    return "poi景点信息检索失败"
                logger.info(f"poi景点信息-bing检索失败，错误信息：{e}")
                await asyncio.sleep(1)

    async def get_poi_info_fuxi(self, poi_list: list) -> list:
        url = 'https://fuxi.sankuai.com/api/flow/run'
        headers = {
            'Content-Type': 'application/json',
            # 灰度
            'M-TransferContext-INF-CELL': 'gray-release-hotel-ptest'
        }
        data = {
            "flowId": 4400,
            "inputParams": {
                "poilist": poi_list
            }
        }
        # 定义最大重试次数和重试间隔
        max_retries = 3
        retry_count = 0

        while retry_count < max_retries:
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(url, headers=headers, json=data)
                    info = response.json()
                    return info['data']['result']
            except Exception as e:
                retry_count += 1
                if retry_count == max_retries:
                    return []
                await asyncio.sleep(1)  # 重试前等待1秒

    async def execute(self, city_with_poi_name: str) -> str:
        if "'" in city_with_poi_name:
            city_with_poi_name = city_with_poi_name.replace("'", '"')
        city_with_poi_name_list = json.loads(city_with_poi_name)
        # 批量获取城市id,优先调用伏羲获取信息
        cityId_poiName_list = []
        for item in city_with_poi_name_list:
            cityName = item[0]
            landmark = item[1]
            cityId_poiName_list.append([cityName2cityId(cityName), landmark])

        fuxi_retrieve_info = await self.get_poi_info_fuxi(cityId_poiName_list)

        result = {}
        for item in fuxi_retrieve_info:
            if item["summary"] is None:
                continue
            result[f"{item['cityName']}-{item['name']}"] = item["summary"]
        # 判断是否全部获取到,如果是的话，直接返回fuxi检索的知识库
        if len(result) == len(city_with_poi_name_list):
            logger.info(f"fuxi检索结果：{result}")
            return json.dumps(result, ensure_ascii=False)

        # 否则，通过web获取信息
        # 寻找不在fuxi中的poi
        remain_poi = []
        for item in city_with_poi_name_list:
            if f"{item[0]}-{item[1]}" not in result.keys():
                remain_poi.append(item)

        for item in remain_poi:
            cityName = item[0]
            landmark = item[1]
            cur_landmark_info = await self.get_poi_info_web(cityName, landmark)
            result[f"{cityName}-{landmark}"] = cur_landmark_info

        return json.dumps(result, ensure_ascii=False)


async def batch_poi_search():
    # 创建工具实例
    poi_tool = PoiInfoSearchBatchTool()

    # 准备测试数据
    test_data = '[["西宁", "青海湖"], ["西安", "兵马俑"], ["杭州", "西湖"], ["宝鸡", "叮当寺"]]'

    try:
        # 执行批量搜索
        result = await poi_tool.execute(test_data)
        print(f"搜索结果: {result}")
    except Exception as e:
        print(f"测试失败: {str(e)}")


from app.logger import logger

if __name__ == "__main__":
    asyncio.run(batch_poi_search())
