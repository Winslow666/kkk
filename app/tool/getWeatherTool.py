import asyncio
from datetime import datetime, timedelta

from app.tool.base import BaseTool
import httpx

from app.logger import logger
from app.tool.llm_tools import gpt_request_2

_WEATHER_DESCRIPTION = """通过城市名称获取,从今天开始未来10天的天气情况"""


class GetWeather(BaseTool):
    name: str = "getWeather"
    description: str = _WEATHER_DESCRIPTION
    parameters: dict = {
        "type": "object",
        "properties": {
            "cityName": {
                "type": "string",
                "description": "中国境内的城市名称，如北京、上海、天津、南京，注意不是景点名称，你要输入对应的城市名称。"
            },
            "date": {
                "type": "string",
                "description": "日期，查询从哪天开始的天气(会返回当天以及连续10天后的天气信息)，格式为YYYY-MM-DD"
            }
        },
        "required": ["cityName", "date"],
    }

    async def execute(self, cityName: str, date: str) -> str:
        url = 'https://fuxi.sankuai.com/api/flow/run'
        headers = {
            'Content-Type': 'application/json'
        }
        data = {
            "flowId": 4369,
            "inputParams": {
                "cityName": cityName,
                "days": 10
            }
        }
        # 计算date与当前时间的差值
        now = datetime.now()
        date = datetime.strptime(date, "%Y-%m-%d")
        delta = abs(date - now)
        try:
            if delta.days > 10:
                return "时间过于久远，无法获取准确天气信息"
                # logger.info("差值大于7，调用大模型获取天气")
                # month = date.month
                # llm_pred_weather = gpt_request_2(
                #     messages=[{"role": "user", "content": f"{cityName}在{month}月的天气怎么样"}],
                #     max_output=200,
                #     model="LongCat-Large-32K-Chat")
                # llm_pred_weather = llm_pred_weather.replace("\n\n", "\n")
                # pred_weather = f"由于预测日期距离今天比较远，无法得到准确的天气情况，因此只能提供过往月份的天气进行参考：{llm_pred_weather}"
                # return pred_weather
            else:
                async with httpx.AsyncClient() as client:
                    response = await client.post(url, headers=headers, json=data)
                    info = response.json()
                    return str(info['data']['weatherInfo'])
        except Exception as e:
            logger.error(f"获取天气信息失败: {e}")
            return "无法获取天气信息，请尝试其他工具"


async def main():
    # 创建 TrainWithAirplane 实例
    tool = GetWeather()

    # 测试用例
    test_cases = [
        {
            "cityName": "洛阳",
            "date": "2025-05-01"
        }
        ,
        {
            "cityName": "洛阳",
            "date": "2025-04-15"
        }
    ]

    # 执行测试
    for case in test_cases:
        print(f"\n测试用例: {case}")
        try:
            result = await tool.execute(
                cityName=case["cityName"],
                date=case["date"]
            )
            print(f"结果: {result}")
        except Exception as e:
            print(f"错误: {str(e)}")


if __name__ == "__main__":
    # 运行主函数
    asyncio.run(main())
