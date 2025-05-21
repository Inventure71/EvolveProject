from typing import Union
def calculator(operation: str, number1: int, number2: int) -> Union[float, str]:
    """
    Performs a basic arithmetic operation between two numbers.

    Args:
        operation: The operation to perform (e.g., 'add', 'subtract', 'multiply', 'divide').
        number1: The first number to operate on.
        number2: The second number to operate on.

11:
12:     Returns:
12.1:         A float containing the result of the operation or an error message.
    """

    if operation == "add":
        result = number1 + number2
    elif operation == "subtract":
        result = number1 - number2
    elif operation == "multiply":
        result = number1 * number2
    elif operation == "divide":
        result = number1 / number2
    else:
        result = "Invalid operation"
    print(result)
    
    return {"result:": result}