from openai import OpenAI
from api.utils import client


def get_content_and_user_message(content, user_message):
    tools = [
        {
            "type": "function",
            "function": {
                "name": "getData",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                    },
                    "required": [
                        "id",
                    ],
                    "additionalProperties": False,
                },
            },
        }
    ]

    # Call the GPT API
    completion = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": content + "Use the supplied tools to assist the user.",
            },
            {"role": "user", "content": user_message},
        ],
        tools=tools,
    )

    # Extract and return the tool calls and user message
    return completion.choices[0].message.content
