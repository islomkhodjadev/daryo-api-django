function_declaration = {
    "name": "get_data",
    "description": "Fetches the content by id",
    "parameters": {
        "type": "object",
        "properties": {
            "id": {"type": "integer", "description": "id of the query"},
        },
        "required": [
            "id",
        ],
    },
}


def get_id(id: int):
    """gets the object by id"""
    return object


def get_id_gemin(content: str, user_message: str):
    from api.utils import genai

    model = genai.GenerativeModel(
        model_name="gemini-1.5-flash-latest",
        generation_config=genai.types.GenerationConfigDict(
            {"temperature": 0.7, "max_output_tokens": 500}
        ),
        system_instruction=content,
        tools=[get_id],
    )
    response = model.generate_content(
        user_message,
    )
    return response.text
