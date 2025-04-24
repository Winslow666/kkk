from app.tool.base import BaseTool

_TRAVEL_PLAN_DRAFT_DESCRIPTION = """
在收集完成目的地的信息之后，先对行程进行初步的规划，并生成一个包含【行程概览、往返交通、每日行程安排】行程规划。为最最终版进行参考优化。
"""


class TravelPlanDraftTool(BaseTool):
    name: str = "travel_plan_draft"
    description: str = _TRAVEL_PLAN_DRAFT_DESCRIPTION
    parameters: dict = {
        "type": "object",
        "properties": {
            "draft_plan": {
                "type": "string",
                "description": '按照用户的要求，输出一个包含【行程概览、往返交通、每日行程安排】的初步行程规划，减少自由活动的安排，尽可能安排景点游玩',
            }
        },
        "required": ["draft_plan"],
    }

    async def execute(self, draft_plan: str) -> str:
        """Finish the current execution"""
        return "完成初步的行程计划安排，接下来请你判断是否需要进行行程调整，如行程存在过多的自由活动时间、雨天安排了户外活动，往返时间与景点游玩时间冲突等问题。"
