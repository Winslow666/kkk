import asyncio
import time

from app.tool.base import BaseTool
import httpx
from app.logger import logger

_MapGuide_DESCRIPTION = """可以是同一个城市，也可以是不同的城市，搜索出发地点前往目的地的导航路线，包括步行、驾车、公交路线。"""


class MapGuide(BaseTool):
    name: str = "mapGuide"
    description: str = _MapGuide_DESCRIPTION
    parameters: dict = {
        "type": "object",
        "properties": {
            "origin_cityName": {
                "type": "string",
                "description": "出发的地点所在的城市名称，如北京、上海"
            },
            "origin": {
                "type": "string",
                "description": "出发的地点，如颐和园、xx酒店、xx餐厅"
            },
            "destination_cityName": {
                "type": "string",
                "description": "目的地地点所在的城市名称，如北京、上海"
            }, "destination": {
                "type": "string",
                "description": "目的地点，如颐和园、xx酒店、xx餐厅"
            },
        },
        "required": ["origin_cityName", "origin", "destination_cityName", "destination"]
    }

    async def execute(self, origin_cityName: str, origin: str, destination_cityName: str, destination: str) -> str:
        url = 'https://fuxi.sankuai.com/api/flow/run'
        headers = {
            'Content-Type': 'application/json'
        }
        data = {
            "flowId": 4431,
            "inputParams": {
                "source": origin_cityName + origin,
                "target": destination_cityName + destination
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
                    return str(info['data']['output'])
            except Exception as e:
                retry_count += 1
                if retry_count == max_retries:
                    logger.error(f"获取导航信息失败，已重试{max_retries}次：{e}")
                    return "无法获取导航信息，请尝试其他工具。"
                logger.warning(f"第{retry_count}次请求失败，正在重试：{e}")
                await asyncio.sleep(1)  # 重试前等待1秒
