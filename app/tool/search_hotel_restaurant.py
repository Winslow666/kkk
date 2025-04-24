import asyncio
import time

from app.logger import logger

from app.tool.base import BaseTool
import httpx
import json

from app.tool.cityName2cityId import cityName2cityId

_SEARCH_HOTEL_RES_DESCRIPTION = """根据用户输入的query搜索酒店和餐厅信息,你的查询要具体（城市名称+景点+描述）"""


class SearchHotelAndRestaurant(BaseTool):
    name: str = "search_hotel_restaurant"
    description: str = _SEARCH_HOTEL_RES_DESCRIPTION
    parameters: dict = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "查询酒店和餐厅的query，你的查询要具体（城市名称+景点+描述），如“北京望京周边的烤鸭店”，“北京颐和园附近的三星级酒店“"
            },
            "cityName": {
                "type": "string",
                "description": "搜索哪个城市，如北京、上海、天津"
            },
            "types": {
                "type": "string",
                "description": "搜索酒店还是美食",
                "enum": ["hotel", "restaurant"]
            }
        },
        "required": ["query", "cityName", "types"],
    }

    async def execute(self, query: str, cityName: str, types: str) -> str:
        url = 'https://fuxi.sankuai.com/api/flow/run'
        headers = {
            'Content-Type': 'application/json'
        }

        sourceInfo = {
            "query": query,
            "latitude": "39.999631",
            "longitude": "116.273933",
            "curLocCityId": "1",
            "curLocCityName": "北京",
            "desCityId": str(cityName2cityId(cityName)),
            "desCityName": str(cityName),
            "mtUserId": "00000000000009A9F22220E644657AB01F1DC28BB7C4DA167659613188055416",
            "uuid": "1679788116"
        }

        data = {
            "flowId": 4020,
            "inputParams": {
                "shortTermProfile": "",
                "sourceInfo": sourceInfo,
                "midTermProfile": "",
                "sourceType": "fmq_generate_data",
                "query": query,
                "longTermProfile": "",
                "sessionId": "",
                "isHistory": ""
            }
        }

        max_retries = 3
        for retry in range(max_retries):
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(url, headers=headers, json=data, timeout=200)
                    info = response.json()['data']

                    if not info['result']:
                       return "没有符合要求的酒店和餐厅"
                    result_dict = {}
                    if '2-restaurant' in info['result']:
                        dasou_response = info['result']['2-restaurant'][0]['dasou_response']
                        if not dasou_response:
                            return "周围没有符合要求的餐厅"

                        for item in dasou_response:
                            poiName = item['itemName']
                            poi_detail_info = item['poi_detail_info']['jsonItem']

                            avgPrice = str(poi_detail_info['avgPrice']) + "元"
                            # address = poi_detail_info['address']
                            areas = None
                            if 'areas' in poi_detail_info and poi_detail_info['areas']:
                                areas = poi_detail_info['areas'][0].get("name", "暂无数据")
                            summary = poi_detail_info['summary']

                            deals = poi_detail_info['deals']
                            deals_list = []
                            for deal in deals:
                                if 'title' in deal and 'sellPrice' in deal:
                                    title = deal['title']
                                    sellPrice = deal['sellPrice']
                                    deals_list.append(f"{title}: {sellPrice}元")
                            deals_str = '\n'.join(deals_list[:5])

                            result_dict[poiName] = {
                                '人均': avgPrice,
                                '基本信息': summary,
                                '菜品或者套餐': deals_str,
                                '商圈': areas
                            }
                            # result_dict['就餐推荐'] = areas
                        return json.dumps(result_dict, ensure_ascii=False)

                    elif '4-hotel' in info['result']:
                        dasou_response = info['result']['4-hotel'][0]['dasou_response']
                        if not dasou_response:
                            return "周围没有符合要求的酒店"
                        for item in dasou_response:
                            poiName = item['itemName']
                            poi_detail_info = item['poi_detail_info']['jsonItem']
                            # address = poi_detail_info['address']
                            summary = poi_detail_info['summary']
                            rooms = poi_detail_info['rooms']
                            typeName = poi_detail_info['typeName']  # 几星级
                            # 商圈
                            areas = None
                            if 'areas' in poi_detail_info and poi_detail_info['areas']:
                                areas0 = poi_detail_info['areas'][0].get("name", "暂无数据")
                                areas1 = poi_detail_info['areas'][1].get("name", "暂无数据")
                                areas = f" {areas1}{areas0}"
                            rooms_list = []
                            for room in rooms[:10]:
                                if 'title' in room and 'sellPrice' in room:
                                    title = room['title']
                                    sellPrice = room['sellPrice']
                                    rooms_list.append(f"{title}: 约{sellPrice}元")
                            rooms_str = '\n'.join(rooms_list[:5])

                            if 'ugcAdvantages' in poi_detail_info:
                                ugcAdvantages = poi_detail_info['ugcAdvantages']
                                result_dict[poiName] = {
                                    '信息': summary,
                                    '酒店级别': typeName,
                                    '优点': ugcAdvantages,
                                    '房间价格信息': rooms_str,
                                    '商圈': areas
                                }
                            else:
                                result_dict[poiName] = {
                                    '信息': summary,
                                    '酒店级别': typeName,
                                    '房间价格信息': rooms_str,
                                    '商圈': areas
                                }
                            # result_dict['入住推荐'] = areas
                        return json.dumps(result_dict, ensure_ascii=False)

                    else:
                        return "周围没有符合要求的餐厅和酒店"

            except Exception as e:
                if retry == max_retries - 1:  # 最后一次重试失败
                    logger.error(f"搜索周围的酒店、餐厅信息失败，重试{max_retries}次后仍然失败，错误信息：{e}")
                    return "搜索周围的酒店、餐厅信息失败"
                logger.info(f"搜索周围的酒店、餐厅信息失败，错误信息：{e}")
                await asyncio.sleep(1)


async def search():
    # 创建实例
    search_tool = SearchHotelAndRestaurant()

    # 测试参数
    query = "大同华严寺周围酒店"
    city_name = "大同"

    # 执行搜索
    start_time = time.time()
    result = await search_tool.execute(query=query, cityName=city_name, types="hotel")
    elapsed_time = time.time() - start_time
    print(f"搜索耗时: {elapsed_time:.2f}秒")
    print(result)


# 运行测试
if __name__ == "__main__":
    asyncio.run(search())
