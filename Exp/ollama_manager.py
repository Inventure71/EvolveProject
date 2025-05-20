# main_ollama_tool_calling.py

import openai
import os
import inspect
import importlib
import sys
import json
import re
from typing import Any, Dict, List, Callable, Union

# --- Helper function for type conversion ---
def get_python_type_to_json_type(py_type: Any) -> str:
    """Converts Python type annotations to JSON schema types."""
    if py_type is str:
        return "string"
    if py_type is int:
        return "integer"
    if py_type is float:
        return "number"
    if py_type is bool:
        return "boolean"
    # Basic support for list and dict; could be enhanced for typed lists/dicts
    if py_type is list or getattr(py_type, '__origin__', None) is list:
        return "array"
    if py_type is dict or getattr(py_type, '__origin__', None) is dict:
        return "object"
    
    # Default for unmapped or complex types (e.g., custom classes, Any, Union)
    # The model might handle 'string' representation for these, or you might need more specific mapping.
    return "string"


class OllamaHandler:
    def __init__(self, base_url="http://localhost:11434/v1", api_key="ollama", tools_dir="tools"):
        """
        Initializes the OllamaHandler.

        Args:
            base_url (str): The base URL for the Ollama OpenAI-compatible API.
            api_key (str): The API key for Ollama (conventionally 'ollama').
            tools_dir (str): The directory name where tool Python files are located.
        """
        try:
            self.client = openai.OpenAI(base_url=base_url, api_key=api_key)
            # Test connection
            self.client.models.list() 
            print(f"Successfully connected to Ollama at {base_url}")
        except openai.APIConnectionError as e:
            print(f"Fatal: Could not connect to Ollama at {base_url}. Please ensure Ollama is running.")
            print(f"Error details: {e}")
            sys.exit(1)
            
        self.tools_dir = tools_dir
        self.tool_schemas = []
        self.callable_tools = {}  # Stores name -> function object
        self.reload_tools()

    def _get_parameter_descriptions_from_docstring(self, docstring: str) -> Dict[str, str]:
        """
        Parses a docstring to extract parameter descriptions.
        Assumes an "Args:" section like:
        Args:
            param_name (type): Description of param.
            param_name: Description of param. (if type is omitted in description line)
        """
        if not docstring:
            return {}
        
        descriptions = {}
        # Regex to find "Args:" section and capture its content
        args_section_match = re.search(r"Args:\s*\n((?:.|\n)*?)(?=\n\s*\w+:|$)", docstring, re.DOTALL)
        
        if args_section_match:
            args_content = args_section_match.group(1)
            # Regex for each parameter line: captures name and description
            # Handles "param_name (type): description" or "param_name: description"
            # Updated regex to better handle complex type hints like List[str] or Union[int, float]
            param_matches = re.finditer(r"^\s*(\w+)\s*(?:\([\w.:\s,\[\]\<\>\|]+\))?:\s*(.+)$", args_content, re.MULTILINE)
            for match in param_matches:
                param_name = match.group(1)
                description = match.group(2).strip()
                descriptions[param_name] = description
        return descriptions

    def convert_function_to_ollama_tool_schema(self, func: Callable) -> Dict[str, Any]:
        """
        Converts a Python function into the Ollama/OpenAI tool JSON schema.
        Parses the function's signature for parameters and types, and its
        docstring for overall description and parameter descriptions.
        """
        func_name = func.__name__
        docstring = inspect.getdoc(func)
        
        main_description = ""
        if docstring:
            # Use the first paragraph of the docstring as the main description
            main_description = docstring.split('\n\n')[0].strip()

        param_descriptions_from_docstring = self._get_parameter_descriptions_from_docstring(docstring)

        sig = inspect.signature(func)
        parameters = sig.parameters
        
        schema_parameters_properties = {}
        required_params = []

        for name, param in parameters.items():
            param_type_annotation = param.annotation
            if param_type_annotation is inspect.Parameter.empty:
                # If no type hint, default to string or try to infer if possible.
                # For simplicity, defaulting to string.
                json_param_type = "string"
                print(f"Warning: Parameter '{name}' in function '{func_name}' has no type hint. Defaulting to 'string'.")
            else:
                json_param_type = get_python_type_to_json_type(param_type_annotation)

            param_description = param_descriptions_from_docstring.get(name, f"Parameter '{name}'")

            schema_parameters_properties[name] = {
                "type": json_param_type,
                "description": param_description,
            }
            if param.default is inspect.Parameter.empty:
                required_params.append(name)
        
        tool_parameters_schema = {
            "type": "object",
            "properties": schema_parameters_properties
        }
        if required_params:
            tool_parameters_schema["required"] = required_params

        return {
            "type": "function",
            "function": {
                "name": func_name,
                "description": main_description,
                "parameters": tool_parameters_schema,
            },
        }

    def reload_tools(self):
        """
        Scans the `tools_dir` for Python files, imports functions,
        and converts them to tool schemas.
        """
        self.tool_schemas = []
        self.callable_tools = {}
        
        if not os.path.exists(self.tools_dir) or not os.path.isdir(self.tools_dir):
            print(f"Tools directory '{self.tools_dir}' not found or is not a directory. No tools will be loaded.")
            return

        # Ensure tools_dir is in sys.path to allow direct import if needed
        # and for importlib to find modules within it correctly.
        if self.tools_dir not in sys.path:
             sys.path.insert(0, self.tools_dir) # Prepend for higher priority
        
        # Parent directory of tools_dir also needs to be in sys.path for "from tools import X"
        parent_tools_dir = os.path.abspath(os.path.join(self.tools_dir, os.pardir))
        if parent_tools_dir not in sys.path:
            sys.path.insert(0, parent_tools_dir)


        for file_name in os.listdir(self.tools_dir):
            if file_name.endswith(".py") and file_name != "__init__.py":
                module_name_on_disk = file_name[:-3] # e.g., "my_tool_file"
                
                # Construct module path for importlib, assuming tools_dir is a package name
                # e.g., if tools_dir is "tools", then "tools.my_tool_file"
                # This requires tools_dir to be discoverable by Python's import system
                # (e.g., it's in PYTHONPATH, or the script runs from one level above tools_dir)
                
                # We will use the name of the directory itself as the package name
                # e.g. if self.tools_dir = "tools", then "tools.module_name"
                module_package_name = os.path.basename(os.path.normpath(self.tools_dir))
                full_module_path = f"{module_package_name}.{module_name_on_disk}"


                try:
                    if full_module_path in sys.modules:
                        module = importlib.reload(sys.modules[full_module_path])
                        print(f"Reloaded tool module: {full_module_path}")
                    else:
                        module = importlib.import_module(full_module_path)
                        print(f"Loaded tool module: {full_module_path}")

                    for name, obj in inspect.getmembers(module, inspect.isfunction):
                        # Ensure the function is defined in the loaded module, not imported into it.
                        if obj.__module__ == module.__name__:
                            print(f"  Found function: {name} in {module_name_on_disk}")
                            try:
                                schema = self.convert_function_to_ollama_tool_schema(obj)
                                self.tool_schemas.append(schema)
                                self.callable_tools[obj.__name__] = obj
                                print(f"    Converted and added tool: {obj.__name__}")
                            except Exception as e_convert:
                                print(f"    Error converting function {name} to schema: {e_convert}")
                except ImportError as e_import:
                    print(f"Error importing module {full_module_path} from {file_name}: {e_import}")
                    print(f"  Ensure '{self.tools_dir}' and its parent directory are structured correctly and in PYTHONPATH if needed.")
                except Exception as e_load:
                    print(f"Error loading tools from {file_name}: {e_load}")
        
        print(f"Tools reloaded. {len(self.tool_schemas)} tools available: {list(self.callable_tools.keys())}")

    def chat_with_tools(self, prompt: str, model: str = "llama3.1", system_message: str = None, max_tool_iterations: int = 5):
        """
        Sends a prompt to the Ollama model, manages tool calls, and returns the final response.

        Args:
            prompt (str): The user's prompt.
            model (str): The Ollama model to use (e.g., "llama3.1").
            system_message (str, optional): An optional system message to guide the assistant.
            max_tool_iterations (int): Maximum number of tool call iterations to prevent infinite loops.

        Returns:
            str: The final textual response from the assistant.
        """
        messages = []
        if system_message:
            messages.append({"role": "system", "content": system_message})
        messages.append({"role": "user", "content": prompt})

        print(f"\nUser: {prompt}")

        for iteration in range(max_tool_iterations):
            print(f"\n--- Iteration {iteration + 1} ---")
            try:
                current_tools = self.tool_schemas if self.tool_schemas else openai.NOT_GIVEN
                # print(f"DEBUG: Sending to Ollama - Messages: {json.dumps(messages, indent=2)}")
                # print(f"DEBUG: Sending to Ollama - Tools: {json.dumps(current_tools, indent=2) if current_tools is not openai.NOT_GIVEN else 'None'}")

                response = self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    tools=current_tools,
                    tool_choice="auto" 
                )
            except openai.APIError as e: # Catches various API errors from Ollama
                print(f"Error calling Ollama API: {e}")
                return f"Sorry, I encountered an API error while processing your request: {e.type if hasattr(e, 'type') else type(e).__name__}"
            except Exception as e: # Catch any other unexpected error during API call
                print(f"An unexpected error occurred calling Ollama: {e}")
                return "Sorry, an unexpected error occurred."

            response_message = response.choices[0].message
            # print(f"DEBUG: Ollama Raw Response Message: {response_message}")

            messages.append(response_message) # Add assistant's response (or tool_calls) to history

            if response_message.tool_calls:
                print(f"Assistant requested tool calls: {[tc.function.name for tc in response_message.tool_calls]}")
                
                for tool_call in response_message.tool_calls:
                    function_name = tool_call.function.name
                    function_args_json = tool_call.function.arguments
                    
                    if function_name not in self.callable_tools:
                        print(f"  Error: Model tried to call unknown function '{function_name}'")
                        tool_response_content = f"Error: Tool '{function_name}' not found or not callable."
                        messages.append({
                            "tool_call_id": tool_call.id,
                            "role": "tool",
                            "name": function_name,
                            "content": tool_response_content,
                        })
                        continue 

                    actual_function = self.callable_tools[function_name]
                    print(f"  Executing tool: {function_name}")
                    print(f"    Arguments (raw JSON from model): {function_args_json}")

                    try:
                        function_args = json.loads(function_args_json)
                        # Validate arguments against function signature (optional but good practice)
                        sig = inspect.signature(actual_function)
                        valid_args = {}
                        missing_required_args = []
                        for p_name, p_val in sig.parameters.items():
                            if p_name in function_args:
                                valid_args[p_name] = function_args[p_name]
                            elif p_val.default is inspect.Parameter.empty:
                                missing_required_args.append(p_name)
                        
                        if missing_required_args:
                            raise ValueError(f"Missing required arguments: {', '.join(missing_required_args)}")

                        # Only pass arguments defined in the function signature
                        # This prevents errors if the LLM hallucinates extra arguments.
                        filtered_args = {k: v for k, v in function_args.items() if k in sig.parameters}

                        function_response = actual_function(**filtered_args)
                        tool_response_content = str(function_response) # Ensure response is a string
                        print(f"    Tool '{function_name}' executed. Response: {tool_response_content[:200]}{'...' if len(tool_response_content) > 200 else ''}")
                        
                    except json.JSONDecodeError:
                        print(f"    Error: Could not decode arguments for {function_name}: {function_args_json}")
                        tool_response_content = f"Error: Invalid arguments format for {function_name}. Expected valid JSON."
                    except TypeError as e: # Catches issues with missing/extra arguments if not pre-validated thoroughly
                         print(f"    Error: Type error calling function {function_name} with args {function_args}: {e}")
                         tool_response_content = f"Error: Mismatch in arguments for tool {function_name}: {str(e)}"
                    except Exception as e:
                        print(f"    Error executing function {function_name} with args {function_args}: {e}")
                        tool_response_content = f"Error: Failed to execute tool {function_name}: {str(e)}"

                    messages.append({
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": function_name, # Name of the function that was called
                        "content": tool_response_content, # Result from the function
                    })
                # After processing all tool calls for this turn, loop back to send results to model
            
            elif response_message.content:
                # No tool calls, model provided a direct textual answer
                final_answer = response_message.content
                print(f"Assistant: {final_answer}")
                return final_answer
            
            else:
                # No tool_calls and no content, unusual state.
                print("Warning: Model response had no tool calls and no content. Ending interaction.")
                return "I'm sorry, I could not produce a response."

        print("Max tool iterations reached. Unable to complete the request fully.")
        # Try to get the last message from the assistant if available
        last_assistant_message = next((m['content'] for m in reversed(messages) if m['role'] == 'assistant' and m['content']), None)
        return last_assistant_message or "Sorry, I couldn't complete the request using tools within the allowed iterations."


if __name__ == "__main__":
    # --- Setup: Create dummy tools directory and tool files for testing ---
    TOOLS_DIR_NAME = "my_ollama_tools" # Using a distinct name for clarity
    if not os.path.exists(TOOLS_DIR_NAME):
        os.makedirs(TOOLS_DIR_NAME)
    
    # Create __init__.py in the tools directory to make it a package
    # This is important for importlib.import_module to work correctly with "package.module"
    with open(os.path.join(TOOLS_DIR_NAME, "__init__.py"), "w") as f:
        pass 

    # Create a sample tool file
    sample_tool_file_path = os.path.join(TOOLS_DIR_NAME, "calculators_and_weather.py")
    with open(sample_tool_file_path, "w") as f:
        f.write("""# my_ollama_tools/calculators_and_weather.py
import json

def add_numbers(a: int, b: int) -> int:
    \"\"\"
    Adds two integer numbers together.

    Args:
        a (int): The first integer.
        b (int): The second integer.

    Returns:
        int: The sum of the two integers.
    \"\"\"
    print(f"[Tool log: add_numbers] Called with a={a}, b={b}")
    return a + b

def get_city_weather(city_name: str) -> str:
    \"\"\"
    Retrieves the current weather for a specified city.
    This is a mock function and provides predefined weather for a few cities.

    Args:
        city_name (str): The name of the city for which to get the weather. 
                         Example: "London", "Paris", "Tokyo".

    Returns:
        str: A JSON string describing the weather (e.g., 
             '{"city": "London", "temperature_celsius": 15, "condition": "Cloudy"}') 
             or an error message if the city is not found.
    \"\"\"
    print(f"[Tool log: get_city_weather] Called with city_name='{city_name}'")
    city_name_lower = city_name.lower()
    weather_data = {}
    if city_name_lower == "london":
        weather_data = {"city": "London", "temperature_celsius": 15, "condition": "Cloudy"}
    elif city_name_lower == "paris":
        weather_data = {"city": "Paris", "temperature_celsius": 18, "condition": "Sunny"}
    elif city_name_lower == "tokyo":
        weather_data = {"city": "Tokyo", "temperature_celsius": 22, "condition": "Rainy"}
    elif city_name_lower == "toronto": # From user's context
         weather_data = {"city": "Toronto", "temperature_celsius": 25, "condition": "Sunny", "details": "High of 25C"}
    else:
        weather_data = {"error": f"Weather information not available for {city_name}."}
    return json.dumps(weather_data) # Return as JSON string as per docstring
""")
    print(f"Sample tool file created at: {os.path.abspath(sample_tool_file_path)}")
    print(f"Current working directory: {os.getcwd()}")
    print(f"Sys.path: {sys.path}")


    # --- Initialize and Use OllamaHandler ---
    # Ensure Ollama is running: `ollama serve`
    # Ensure you have a tool-capable model: `ollama pull llama3.1` (or mistral-nemo etc.)
    
    # IMPORTANT: Run this script from the directory *containing* `my_ollama_tools`
    # or ensure `my_ollama_tools`'s parent directory is in PYTHONPATH.
    # For this example, if main_ollama_tool_calling.py is in /project/ and
    # my_ollama_tools is in /project/my_ollama_tools/, this should work.
    
    try:
        handler = OllamaHandler(tools_dir=TOOLS_DIR_NAME) 
        
        print("\n--- Generated Tool Schemas ---")
        if handler.tool_schemas:
            print(json.dumps(handler.tool_schemas, indent=2))
        else:
            print("No tool schemas were generated. Check tools directory and file content.")

        if not handler.callable_tools:
            print("\nNo tools were loaded. Aborting chat tests. Check console for errors during tool loading.")
        else:
            print("\n--- Test 1: Simple weather query ---")
            # Note: llama3.1 is a good choice if available and supports tool calling.
            # Some smaller models might struggle with complex tool use or JSON formatting.
            # model_to_use = "llama3.1" # Recommended
            model_to_use = "mistral-nemo" # Another option, generally smaller than Llama 3.1 70B
            # model_to_use = "phi3:medium" # Phi-3 models might also support tool calling
            
            # Ensure you have pulled the model: `ollama pull <model_to_use>`
            print(f"Using model: {model_to_use}")
            
            handler.chat_with_tools(
                prompt="What is the weather like in Toronto?", 
                model=model_to_use,
                system_message="You are a helpful assistant. When asked for weather, use the get_city_weather tool."
            )

            print("\n--- Test 2: Simple calculation ---")
            handler.chat_with_tools(
                prompt="Can you calculate 123 plus 789 for me?", 
                model=model_to_use,
                system_message="You are a helpful assistant. For calculations, use available tools."
            )

            print("\n--- Test 3: Multi-step reasoning with tools (model dependent) ---")
            handler.chat_with_tools(
                prompt="My friend is in Paris. I want to know its weather. Then, I want to add 10 to its temperature in Celsius.",
                model=model_to_use,
                system_message="You are a helpful assistant. Break down complex requests. Use tools for weather and calculations. The weather tool returns JSON, extract temperature_celsius for calculations."
            )
            
            print("\n--- Test 4: Tool for a city not in the mock data ---")
            handler.chat_with_tools(
                prompt="What's the weather in Berlin?",
                model=model_to_use
            )

    except openai.APIConnectionError as e:
        print(f"\n\nFATAL ERROR: Could not connect to Ollama. Please ensure Ollama is running and accessible at the specified base_url.")
        print(f"Details: {e}")
    except Exception as e:
        print(f"\n\nAn unexpected error occurred in the main execution block: {e}")
        import traceback
        traceback.print_exc()