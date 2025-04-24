import json

from app.tool.base import BaseTool

# _TERMINATE_DESCRIPTION = """Terminate the interaction when the request is met OR if the assistant cannot proceed further with the task.
# When you have finished all the tasks, call this tool to end the work."""

_TERMINATE_DESCRIPTION = """
此次任务已经可以完成，无需再进行更多的处理，就调用此工具来结束流程。
"""


class Terminate(BaseTool):
    name: str = "terminate"
    description: str = _TERMINATE_DESCRIPTION
    parameters: dict = {
        "type": "object",
        "description": "一份关于某地的详细行程安排攻略，用户要求安排n日的旅游攻略，schedule字段就得一次性输出n天的带有午餐和晚餐的旅游攻略安排。",
        "properties": {
            "schedule": {
                "type": "array",
                "description": "N天的旅程行程详细安排",
                "items": {
                    "type": "object",
                    "properties": {
                        "day": {
                            "type": "integer",
                            "description": "行程中的第几天，如1、2、3、4、5、6、7"
                        },
                        "date": {
                            "type": "string",
                            "format": "date",
                            "description": "行程的具体日期，格式为“yyyy-mm-dd”,如“2025-01-01”"
                        },
                        "weather": {
                            "type": ["string", "null"],
                            "description": "天气信息，如果date与今天的日期范围在7天内，可以获取可靠的天气，否则设置为null即可"
                        },
                        "schedule_item": {
                            "type": "array",
                            "description": "每天具体行程安排",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "time": {
                                        "type": "string",
                                        "pattern": "^\\d{2}:\\d{2}-\\d{2}:\\d{2}$",
                                        "description": "行程时间段，格式为‘hh:mm-hh:mm’,如‘10:00-12:00’，午餐时间应该在11:00-14:00之间，晚餐时间应该在17:00-20:00点之间"
                                    },
                                    "type": {
                                        "type": "string",
                                        "enum": ["火车/飞机", "景点-游玩", "就餐"],
                                        "description": "行程类型"
                                    },
                                    "activity": {
                                        "type": "string",
                                        "description": "行程活动",
                                        "oneOf": [
                                            {
                                                "type": "string",
                                                "pattern": "^.+?-(火车|飞机)-.+?$",
                                                "description": "如果type是火车/飞机，那么activity是：fromCity-交通方式-targetCity，fromCity和targetCity是中国大陆城市名称，如北京、上海"
                                            },
                                            {
                                                "type": "string",
                                                "description": "如果type是景点-游玩，那么activity是景点名称或者游玩项目的名称，如“黄浦江游船”，“天安门”"
                                            },
                                            {
                                                "type": "string",
                                                "enum": ["午餐时间", "晚餐时间"],
                                                "description": "说明是午餐还是晚餐时间。"
                                            }
                                        ]
                                    },
                                    "description": {
                                        "type": "string",
                                        "description": "行程活动的描述信息",
                                        "minLength": 100,
                                        "oneOf": [
                                            {
                                                "type": "string",
                                                "description": "当type是景点-游玩时：需要详细介绍对应的活动，包含基本信息介绍-门票价格-推荐理由-特色游玩项目"
                                            },
                                            {
                                                "type": "string",
                                                "description": "当type是火车/飞机时：火车的话需要说明班次-始发站-终点站-费用-耗时等信息, 飞机需要航班号、起飞机场、到达机场、预估费用等信息"
                                            },
                                            {
                                                "type": "string",
                                                "description": "当type是就餐，说明推荐就餐的区域，和推理理由即可。而不是具体的餐厅名称，如‘推荐在南京东路附近就餐，有本地特色的本帮菜系，醉蟹等’，如果是一整天游玩某个景点，也可以是自带食物或者景区内就餐"
                                            }
                                        ]
                                    },
                                    "next_stop_transportation": {
                                        "type": "string",
                                        "description": "前往下一站的交通方式"
                                    }
                                },
                                "required": ["time", "type", "activity", "description", "next_stop_transportation"]
                            }
                        },
                        "hotelArea": {
                            "type": "object",
                            "description": "推荐入住的酒店区域信息，而不是具体的酒店名称和酒店信息，如“建议住在望京附近、建议住在鸟巢周围”",
                            "properties": {
                                "check_in_date": {
                                    "type": "string",
                                    "format": "date",
                                    "description": "酒店入住日期,一日游设置为None即可"
                                },
                                "check_out_date": {
                                    "type": "string",
                                    "format": "date",
                                    "description": "酒店退房日期，一日游设置为None即可"
                                },
                                "recommendation_reason": {
                                    "type": "string",
                                    "description": "说明居住在什么地方周围、给出推荐理由。100个中文字符",
                                    "minLength": 100
                                },
                                "tips": {
                                    "type": "string",
                                    "description": "预订酒店时对用户的提示事项，如：因行程中有小孩，推荐入住带有亲子房型的酒店"
                                }
                            },
                            "required": ["check_in_date", "check_out_date", "recommendation_reason", "tips"]
                        }
                    },
                    "required": ["day", "date", "schedule_item", "hotel"]
                }
            },
            "budget": {
                "type": "string",
                "description": "对整个行程的费用预算估计，包括酒店、机票火车票、景点门票、餐饮和其他开销等"
            },
            "status": {
                "type": "string",
                "description": "是否可以结束当前的状态，即summary工具生成的数据符合要求，如果存在不合理的地方，请你设置为false，继续进行优化。",
                "enum": ["success", "failure"]
            },
            "nDays": {
                "type": "integer",
                "description": "用户query中，要求是一个几天的旅行规划"
            }
        },
        "required": ["schedule", "budget", "status", "nDays"]
    }

    async def execute(self, schedule: list, budget: str, status: str, nDays: int) -> str:
        """Finish the current execution"""
        # 校验天数
        if not schedule or nDays != len(schedule):
            complete_days = [day["day"] for day in schedule]
            return f"攻略不合格，你只安排了第{complete_days}这{len(schedule)}天的攻略，但是用户需要{nDays}天。你应该一次性返回{nDays}天的行程安排。你偷懒了！我很愤怒。"

        # 校验就餐安排
        eat_info = []
        for day_guide in schedule:
            if not day_guide["schedule_item"]:
                return "攻略不合格，schedule_item字段没有数据。"
            day = day_guide["day"]
            schedule_item = day_guide["schedule_item"]
            no_lunch = False
            no_dinner = False
            have_transport = False # 是否有火车/飞机,此时对午餐晚饭不做强制要求。
            for item in schedule_item:
                if item["type"] == "就餐" and item["activity"] == "午餐时间":
                    no_lunch = True
                elif item["type"] == "就餐" and item["activity"] == "晚餐时间":
                    no_dinner = True
                elif item["type"] == "火车/飞机":
                    have_transport = True
            if not have_transport and (not no_lunch or not no_dinner):
                cur_day_eat_info = f"第{day}天没有安排"
                if not no_lunch:
                    cur_day_eat_info += "午餐"
                if not no_dinner:
                    cur_day_eat_info += "晚餐"
                eat_info.append(cur_day_eat_info)
        if eat_info:
            return f"攻略不合格，你{eat_info}。你应该一次性返回{nDays}天的带有午餐和晚餐的行程安排。你偷懒了！我很愤怒。"
        # 校验status状态
        if status == "failure":
            return "攻略不合格"

        return "攻略合格"
