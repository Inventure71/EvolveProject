
    tools = [
        types.Tool(
            function_declarations=[
                types.FunctionDeclaration(
                    name="calculator",
                    description="This function is used to calculate the operation of two numbers",
                    parameters=genai.types.Schema(
                        type = genai.types.Type.OBJECT,
                        required = ["operation", "number1", "number2"],
                        properties = {
                            "operation": genai.types.Schema(
                                type = genai.types.Type.STRING,
                            ),
                            "number1": genai.types.Schema(
                                type = genai.types.Type.NUMBER,
                            ),
                            "number2": genai.types.Schema(
                                type = genai.types.Type.NUMBER,
                            ),
                        },
                    ),
                ),
            ])
    ]
