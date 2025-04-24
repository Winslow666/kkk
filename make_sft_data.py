# -*- coding: utf-8 -*-
import jsonlines
import json
import copy
import os

# todo ：function call 的定义加入 system prompt
FC_DEFINE = """"""


class CoADataMultiFC:
    def __init__(self):
        self.COA_DATA = []

    def pre_process_single_data(self, trace: dict):
        # 使用gpt-4o的summary mock deepseek的数据
        trace_pre = trace[:-3]
        act = trace[-3]
        obv = trace[-2]
        gpt_4o = trace[-1]

        mock_terminate = {
            "summary": gpt_4o['content'],
            "status": "success",
            "optimizationPoint": "输出最终版",
        }
        new_act = [
            {
                "role": "act",
                "content": [
                    {
                        "function": "terminate",
                        "arguments": json.dumps(mock_terminate, ensure_ascii=False)
                    }
                ],
                "loss": True
            }
        ]
        new_obv = [
            {
                "role": "obv",
                "content": f"Observed output of cmd `terminate{mock_terminate}` executed:\n本次总结的攻略符合预期",
                "loss": False
            }
        ]

        stop = [
            {
                "role": "stop",
                "content": "stop",
                "loss": False
            }
        ]

        mock_trace = trace_pre + new_act + new_obv + stop
        return mock_trace

    def make_single_COA_data(self, part_trace: list):
        """
        :param part_trace: [{"role": str, "content": str, "loss": bool}]
        :return:
        """
        if not part_trace:
            return None

        # 校验：如果没有loss等于True的，不做任何处理
        save_loss_true = False
        for item in part_trace:
            if item['loss']:
                save_loss_true = True
                break
        if not save_loss_true:
            return None

        # 构造sft数据
        # 从后往前遍历，找到所有loss为True的节点，并记录其index
        loss_index = len(part_trace) - 1
        while loss_index >= 0 and part_trace[loss_index]['loss']:
            loss_index -= 1

        input_part = part_trace[:loss_index + 1]
        output_part = part_trace[loss_index + 1:]

        # 构造input-user
        input_content = []
        for index, item in enumerate(input_part):
            if item['role'] == 'system_prompt':
                input_content.append(f"{item['content']}")
            elif item['role'] == 'user':
                input_content.append(f"用户输入问题是：{item['content']}")
            elif item['role'] == 'next_step_prompt':
                input_content.append(f"{item['content']}")
            elif item['role'] == 'think':
                think = item['content'].replace('assistant思考的内容', '')
                input_content.append(f"{think}")
            elif item['role'] == 'act':
                content = item['content']
                all_tools = []
                for fc in content:
                    function = fc['function']
                    try:
                        arguments = json.loads(fc['arguments'])
                    except:
                        arguments = fc['arguments']
                    fc_maps = {"name": function, "arguments": arguments}
                    all_tools.append(fc_maps)
                all_tools = "<tool_call>" + json.dumps(all_tools, ensure_ascii=False) + "</tool_call>"
                input_content.append(f"{all_tools}")
            elif item['role'] == 'obv':
                input_content.append(f"{item['content']}")

        # 构造output-Assistant
        output_content = []
        for item in output_part:
            if item['role'] == 'think':
                think = item['content'].replace('assistant思考的内容', '')
                output_content.append(f"{think}")
            if item['role'] == 'act':
                content = item['content']
                all_tools = []
                for fc in content:
                    function = fc['function']
                    try:
                        arguments = json.loads(fc['arguments'])
                    except:
                        arguments = fc['arguments']
                    fc_maps = {"name": function, "arguments": arguments}
                    all_tools.append(fc_maps)
                all_tools = "<tool_call>" + json.dumps(all_tools, ensure_ascii=False) + "</tool_call>"
                output_content.append(f"{all_tools}")

        self.COA_DATA.append({"messages": [{"role": "user", "content": "\n".join(input_content)},
                                           {"role": "assistant", "content": "\n".join(output_content)}]})

    def make_single_sft_data(self, reasoning_trace: dict):

        # mock gpt-4o的结果为最终攻略
        reasoning_trace = self.pre_process_single_data(reasoning_trace)

        cur_info = []
        i = 0
        while i < len(reasoning_trace):
            cur_info.append(copy.deepcopy(reasoning_trace[i]))
            role = reasoning_trace[i]['role']
            content = reasoning_trace[i]['content']
            loss = reasoning_trace[i]['loss']
            if role != 'act':
                i += 1
                continue
            else:
                self.make_single_COA_data(cur_info)
                i += 1

    def save_data(self, save_path: str):
        # 将list保存为jsonlines文件
        with jsonlines.open("train_coa.jsonl", mode='w') as writer:
            writer.write_all(self.COA_DATA)


if __name__ == '__main__':
    # 0071
    # with jsonlines.open('CoA_data_5k.jsonl') as reader:
    #     data = list(reader)

    coa_data = CoADataMultiFC()

    path = "reasoning_trace_train"
    for file in os.listdir(path):
        if file.endswith('.json'):
            file_path = os.path.join(path, file)
            with open(file_path, 'r') as f:
                reasoning_trace = json.load(f)
                coa_data.make_single_sft_data(reasoning_trace)
        coa_data.save_data('train_coa.jsonl')

    # print(coa_data.COA_DATA)
