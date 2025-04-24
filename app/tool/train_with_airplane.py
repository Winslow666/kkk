import asyncio
import time
import json
import random
from datetime import datetime, timedelta

from app.tool.base import BaseTool
import httpx
from app.logger import logger
from app.tool.cityName2cityId import cityName2cityId

_TRAIN_AIRPLANE_DESCRIPTION = """查询在指定日期，从城市A到城市B的单程火车票和飞机票信息"""


class TrainWithAirplane(BaseTool):
    name: str = "trainWithAirplane"
    description: str = _TRAIN_AIRPLANE_DESCRIPTION
    parameters: dict = {
        "type": "object",
        "properties": {
            "origin_cityName": {
                "type": "string",
                "description": "出发的地点所在的城市名称，如北京、上海"
            },
            "destination_cityName": {
                "type": "string",
                "description": "目的地地点所在的城市名称，如北京、上海"
            },
            "date": {
                "type": "string",
                "description": "日期，格式为2024-01-01。即'YYYY-MM-DD'格式"
            },
        },
        "required": ["origin_cityName", "origin", "destination_cityName", "destination"]
    }

    async def get_airplane_info(self, origin_city_id, destination_city_id, date):
        url = 'https://fuxi.sankuai.com/api/flow/run'
        headers = {
            'Content-Type': 'application/json',
            # 机票灰度标识
            'M-TransferContext-INF-CELL': 'gray-release-hotel-ptest'
        }
        data = {
            "flowId": 4394,
            "inputParams": {
                "airfare": {
                    "arriveMCityId": destination_city_id,
                    "date": date,
                    "tripType": 1,
                    "departMCityId": origin_city_id,
                    "src": "kxmb_mt",
                    "cityId": 1,
                    "versionName": "12.33.200",
                },
                "topN": 8

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

                    if not info['data'] or not info['data']['result']:
                        return "没有符合条件的航班"
                    res = info['data']['result']
                    flightList = res['data']['canBuyBabyAndChildOrOnlyAdult']['flightList']
                    airplane_info = []
                    for flight in flightList:
                        fn = flight['fn']
                        coName = flight['coName']
                        departCityName = flight['departCityName']
                        arriveCityName = flight['arriveCityName']
                        departAirportName = flight['departAirportName']
                        arriveAirportName = flight['arriveAirportName']
                        flyTime = flight['flyTime']
                        departTime = flight['departTime']
                        arriveTime = flight['arriveTime']
                        price = flight['price']

                        airplane_info.append(f"{coName}下的{fn}航班, "
                                             f"{departCityName}{departAirportName}机场出发到{arriveCityName}{arriveAirportName}机场, "
                                             f"出发时间:{departTime},到达时间:{arriveTime},耗时:{flyTime} "
                                             f"票价:{price}")
                    if not airplane_info:
                        return "没有符合条件的直飞航班"
                    return '\n'.join(airplane_info)
            except Exception as e:
                retry_count += 1
                if retry_count == max_retries:
                    logger.error(f"获取飞机票信息失败，已重试{max_retries}次：{e}")
                    return "获取飞机票信息失败，请尝试其他工具。"
                logger.warning(f"获取飞机票信息失败，第{retry_count}次请求失败，正在重试：{e}")
                await asyncio.sleep(1)  # 重试前等待1秒

    async def get_train_info(self, origin_city_id, destination_city_id, date):

        train_info = []

        query_date = datetime.strptime(date, '%Y-%m-%d')
        today = datetime.now()
        date_diff = (query_date - today).days

        if date_diff < 0:
            train_info.append(f"查询日期 {date} 已过期,帮你查询明天的火车信息。")
        if date_diff > 14:
            train_info.append(f"火车票还没有开售，但是火车票一般每日都相同，帮你查询明天的火车信息,你可以进行参考。")
            date = (today + timedelta(days=1)).strftime('%Y-%m-%d')

        url = 'https://fuxi.sankuai.com/api/flow/run'
        headers = {
            'Content-Type': 'application/json'
        }
        data = {
            "flowId": 4382,
            "inputParams": {
                "trainfare": {
                    "trainDate": date,
                    "departureCityId": origin_city_id,
                    "destinationCityId": destination_city_id
                }
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
                    tremainTicketTrainList = info['data']['output']['tremainTicketTrainList']

                    train_item_info = []
                    for item in tremainTicketTrainList:
                        fromStationName = item['fromStationName']
                        toStationName = item['toStationName']
                        trainCode = item['trainCode']
                        startTime = item['startTime']
                        arriveTime = item['arriveTime']
                        runTime = item['runTime']
                        price_info = []
                        for seat in item['seats']:
                            seatTypeName = seat['seatTypeName']
                            seatPrice = seat['seatPrice']
                            price_info.append(f"{seatTypeName}{seatPrice}元")
                        if startTime == "--:--":
                            continue
                        cur_summary = f"{trainCode}次列车: 出发站:{fromStationName}->到达站:{toStationName}, 旅程时间：从{startTime}到{arriveTime},{', '.join(price_info)}"
                        train_item_info.append({"startTime": startTime, "cur_summary": cur_summary})

                    # start是24小时的时间如06:12，现在对train_item_info进行排序，请你按照出发时间，从7:00-10:00，10:00-14:00，14:00-18:00，18:00-22:00进行划分，每个部分随机取两个进行保留
                    train_item_info.sort(key=lambda x: x['startTime'])

                    def filter_by_time_range(items, start_hour, end_hour):
                        filtered = [item for item in items
                                    if start_hour <= int(item['startTime'].split(':')[0]) < end_hour]
                        return random.sample(filtered, min(2, len(filtered))) if filtered else []

                    # 划分四个时间段并各取最多2个
                    morning = filter_by_time_range(train_item_info, 7, 10)
                    noon = filter_by_time_range(train_item_info, 10, 14)
                    afternoon = filter_by_time_range(train_item_info, 14, 18)
                    evening = filter_by_time_range(train_item_info, 18, 23)

                    # 合并所有选中的车次信息
                    selected_trains = morning + noon + afternoon + evening
                    for train in selected_trains:
                        train_info.append(train['cur_summary'])

                    if not train_info:
                        return "没有直达的合适时间的火车"
                    return '\n'.join(train_info)
            except Exception as e:
                retry_count += 1
                if retry_count == max_retries:
                    logger.error(f"获取火车票信息失败，已重试{max_retries}次：{e}")
                    return "获取火车票信息失败，请尝试其他工具。"
                logger.warning(f"获取火车票信息失败，第{retry_count}次请求失败，正在重试：{e}")
                await asyncio.sleep(1)  # 重试前等待1秒

    async def execute(self, origin_cityName: str, destination_cityName: str, date: str) -> str:

        # 数据转化
        origin_city_id = cityName2cityId(origin_cityName)
        destination_city_id = cityName2cityId(destination_cityName)
        if origin_city_id == -1 or destination_city_id == -1:
            return "无法获取城市信息，请尝试其他工具。"
        # 校验日期格式
        try:
            datetime.strptime(date, '%Y-%m-%d')
        except ValueError:
            return f"查询{origin_cityName}到{destination_cityName}的火车票机票的日期格式错误，请重新输入。应该为YYYY-mm-dd格式"

        try:
            air_info = await self.get_airplane_info(origin_city_id, destination_city_id, date)
        except Exception as e:
            air_info = "获取飞机票信息失败，请尝试其他工具。"
            logger.error(f"获取飞机票信息失败:{e}")
        try:
            train_info = await self.get_train_info(origin_city_id, destination_city_id, date)
        except Exception as e:
            train_info = "获取火车票信息失败，请尝试其他工具。"
            logger.error(f"获取火车票信息失败:{e}")

        # """mock火车票"""
        # train_info = train_info.replace("无锡东", origin_cityName).replace("无锡", origin_cityName)
        # train_info = train_info.replace("北京南", destination_cityName).replace("北京丰台", destination_cityName).replace("北京", destination_cityName)
        return f"{date},从{origin_cityName}到{destination_cityName}的交通信息\n飞机票:\n{air_info}\n\n火车票:\n{train_info}"


async def main():
    # 创建 TrainWithAirplane 实例
    tool = TrainWithAirplane()

    try:
        result = await tool.execute("西安", "北京", "2025-04-26")
        print(f"结果: {result}")
    except Exception as e:
        print(f"错误: {str(e)}")


if __name__ == "__main__":
    # 运行主函数
    asyncio.run(main())
