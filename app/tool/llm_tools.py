from openai import OpenAI
import time
from app.logger import logger

client = OpenAI(
    api_key="1900073409313378360",
    base_url="https://aigc.sankuai.com/v1/openai/native"
)


def gpt_request_2(messages, model="LongCat-8B-128K-Chat", temperature=0.0, n=1, max_output=2000):
    max_try = 3
    try_cnt = 0
    while True:
        try:
            try_cnt += 1
            if try_cnt > max_try:
                break
            response = client.chat.completions.create(
                messages=messages,
                model=model,
                max_tokens=max_output,
                temperature=temperature,
                n=n
            )
            if n == 1:
                return response.choices[0].message.content
            else:
                return [response.choices[i].message.content for i in range(n)]

        except Exception as e:
            error_str = str(e)
            logger.error(error_str)
            if "内容含有违规信息" in error_str or "违规内容" in  error_str:
                return "查询失败，请通过其他渠道获取信息"
            time.sleep(5)
    return None
