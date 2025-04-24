from app.tool.base import BaseTool

# _TERMINATE_DESCRIPTION = """Terminate the interaction when the request is met OR if the assistant cannot proceed further with the task.
# When you have finished all the tasks, call this tool to end the work."""

_SUMMARY_DESCRIPTION = """
生成最终的答案，即针对用的问题，返回给用户的最终的攻略行程安排。
"""


class Summary(BaseTool):
    name: str = "summary"
    description: str = _SUMMARY_DESCRIPTION
    parameters: dict = {
        "type": "object",
        "description": "一份关于某地的详细行程安排攻略",
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
                                        "description": "行程时间段，格式为‘hh:mm-hh:mm’,如‘10:00-12:00’"
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
                                                "description": "如果type是就餐，说明推荐就餐的区域，而不是具体的餐厅名称，如‘推荐在南京东路附近就餐，有本地特色的本帮菜系，醉蟹等’"
                                            }
                                        ]
                                    },
                                    "description": {
                                        "type": "string",
                                        "description": "行程活动的描述信息"
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
                                    "description": "酒店入住日期"
                                },
                                "check_out_date": {
                                    "type": "string",
                                    "format": "date",
                                    "description": "酒店退房日期"
                                },
                                "recommendation_reason": {
                                    "type": "string",
                                    "description": "说明居住在什么地方周围、给出推荐理由。"
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
            }
        },
        "required": ["schedule", "budget"]
    }

    async def execute(self, schedule: str, budget: str) -> dict:
        """Finish the current execution"""
        return {"schedule": schedule, "budget": budget}
