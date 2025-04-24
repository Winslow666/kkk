import os

import aiofiles

from app.tool.base import BaseTool


class FileSaver(BaseTool):
    name: str = "file_saver"
    description: str = """将内容保存到指定路径的本地文件。当您需要将文本、代码或生成的内容保存到本地文件系统上的文件中时，请使用此工具。该工具接受内容和文件路径，并将内容保存到该位置。"""
    parameters: dict = {
        "type": "object",
        "properties": {
            "content": {
                "type": "string",
                "description": "(required) 写入文件的正文内容。",
            },
            "file_path": {
                "type": "string",
                "description": "(required) 文件写入的路径和文件名，要包含后缀.",
            },
            "mode": {
                "type": "string",
                "description": "(optional) The file opening mode. Default is 'w' for write. Use 'a' for append.",
                "enum": ["w", "a"],
                "default": "w",
            },
        },
        "required": ["content", "file_path"],
    }

    async def execute(self, content: str, file_path: str, mode: str = "w") -> str:
        """
        Save content to a file at the specified path.

        Args:
            content (str): The content to save to the file.
            file_path (str): The path where the file should be saved.
            mode (str, optional): The file opening mode. Default is 'w' for write. Use 'a' for append.

        Returns:
            str: A message indicating the result of the operation.
        """
        try:
            # Ensure the directory exists
            directory = os.path.dirname(file_path)
            if directory and not os.path.exists(directory):
                os.makedirs(directory)

            # Write directly to the file
            async with aiofiles.open(file_path, mode, encoding="utf-8") as file:
                await file.write(content)

            return f"Content successfully saved to {file_path}"
        except Exception as e:
            return f"Error saving file: {str(e)}"
