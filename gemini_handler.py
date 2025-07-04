# pip install google-genai

import base64
import os
import time
from google import genai
from google.genai import types
from typing import Union
from google.genai.types import FinishReason

from Prompts.system_prompt_tool_calling import sys_promp_tool_calling
from Prompts.system_prompt_main import prompt_main

import sys
import inspect  # for finding functions
import types as py_types  # to avoid conflict with `google.genai.types`
import importlib # for dynamic import
#  importlib.reload(config_module)  # This reloads the module from disk


# Tips for Writing Effective Docstrings (usefull for automatic tool for gemini)
# Start with a clear, concise summary of what the function does.
# Use the Args: and Returns: sections as shown.
# Be specific about formats, units, and constraints in parameter descriptions.
# Mention examples when helpful.


class GeminiHandler:
    def __init__(self):
        self.client = genai.Client(
            api_key=os.environ.get("GEMINI_API_KEY"),
        )
        self.rate_limit_per_minute = 30
        self.last_request_time = time.time()
        self.request_count = 0
        # Retry configuration
        self.max_retries = 5
        self.initial_retry_delay = 5  # seconds
        self.max_retry_delay = 60  # seconds

        self.tools_functions = []
        self.reload_tools()
        self.history = []  # Store last 5 model responses

    def reload_tools(self):
        tools_functions = []
        for file in os.listdir("tools"):
            if file.endswith(".py") and file != "__init__.py":
                module_name = file[:-3]  # Remove .py
                full_module_path = f"tools.{module_name}"

                    # Import the module dynamically
                if full_module_path in sys.modules:
                    mod = importlib.reload(sys.modules[full_module_path])
                else:
                    mod = importlib.import_module(full_module_path)

                print(f"Reloaded {full_module_path}")

                # Get all functions defined in that module
                for name, obj in inspect.getmembers(mod, inspect.isfunction):
                    print(f"Found function: {name}")
                    tools_functions.append(obj)

        self.tools_functions = tools_functions
        print("Tools reloaded")
    
    def handle_rate_limit(self):
        if time.time() - self.last_request_time > 60:
            self.last_request_time = time.time()
            self.request_count = 0
        if self.request_count >= self.rate_limit_per_minute:
            wait_time = 60 - (time.time() - self.last_request_time)
            if wait_time > 0:
                print(f"Rate limit reached. Waiting {wait_time:.2f} seconds...")
                time.sleep(wait_time)
            self.last_request_time = time.time()
            self.request_count = 0
    
    def generate(self, model, contents, generate_content_config):
        self.handle_rate_limit()
        self.request_count += 1
        retry_count = 0
        retry_delay = self.initial_retry_delay
        while True:
            try:
                response = self.client.models.generate_content(
                    model=model,
                    contents=contents,
                    config=generate_content_config,
                )
                return response
            except (genai.errors.ServerError, genai.errors.ClientError) as e:
                error_str = str(e)
                # Handle model overloaded (503) errors
                is_overloaded = "503" in error_str and "overloaded" in error_str.lower()
                # Handle quota exceeded (429) errors
                is_quota_exceeded = "429" in error_str and "quota" in error_str.lower()
                # Extract retry delay suggestion if available
                suggested_delay = None
                if is_quota_exceeded:
                    import re
                    retry_match = re.search(r'retryDelay": "(\\d+)s"', error_str)
                    if retry_match:
                        suggested_delay = int(retry_match.group(1))
                if (is_overloaded or is_quota_exceeded) and retry_count < self.max_retries:
                    retry_count += 1
                    # Use suggested delay if available, otherwise use exponential backoff
                    if suggested_delay:
                        retry_delay = suggested_delay
                        print(f"\n⚠️ Quota exceeded. API suggested waiting {retry_delay} seconds.")
                    else:
                        print(f"\n⚠️ {'Model overloaded' if is_overloaded else 'Quota exceeded'}. Waiting {retry_delay} seconds before retry {retry_count}/{self.max_retries}...")
                    time.sleep(retry_delay)
                    # Exponential backoff with maximum cap for next retry (if needed)
                    if not suggested_delay:
                        retry_delay = min(retry_delay * 1.5, self.max_retry_delay)
                    print("Retrying...")
                else:
                    # Re-raise if error type not handled or we've exceeded max retries
                    error_type = "model overload" if is_overloaded else "quota exceeded" if is_quota_exceeded else "API"
                    print(f"\n❌ {error_type.capitalize()} error after {retry_count} retries: {e}")
                    raise
   
    def _add_to_history(self, entry):
        self.history.append(entry)
        if len(self.history) > 5:
            self.history = self.history[-5:]

    def _extract_text_from_candidate(self, candidate):
        # Extract all text parts from the candidate
        if hasattr(candidate, 'content'):
            parts = candidate.content.parts
        else:
            parts = candidate.parts
        return "".join([p.text for p in parts if hasattr(p, 'text') and p.text])

    def _extract_function_calls(self, candidate):
        # Return all function_call parts from the candidate
        if hasattr(candidate, 'content'):
            parts = candidate.content.parts
        else:
            parts = candidate.parts
        return [p for p in parts if hasattr(p, 'function_call') and p.function_call]

    def _run_tool(self, function_call):
        # Find the function by name
        func_name = function_call.name
        args = function_call.args or {}
        for func in self.tools_functions:
            if func.__name__ == func_name:
                try:
                    result = func(**args)
                    return str(result)
                except Exception as e:
                    return f"Tool '{func_name}' failed: {e}"
        return f"Tool '{func_name}' not found."

    def solve_task(self, prompt, model="gemini-2.0-flash"):
        print("Generating response to: ", prompt, "\n...")
        conversation = []
        finished = False
        while not finished:
            # Compose contents from conversation history
            contents = []
            for entry in conversation:
                if entry['role'] == 'user':
                    contents.append(types.Content(role="user", parts=[types.Part.from_text(text=entry['content'])]))
                elif entry['role'] == 'model':
                    # Model response may be text or tool result
                    contents.append(types.Content(role="model", parts=[types.Part.from_text(text=entry['content'])]))
            if not conversation:
                contents.append(types.Content(role="user", parts=[types.Part.from_text(text=prompt)]))

            generate_content_config = types.GenerateContentConfig(
                stop_sequences=[
                    """!FINISHED_TASK!""",
                ],
                tools=self.tools_functions,
                system_instruction=[
                    types.Part.from_text(text=prompt_main),
                ],
            )

            response = self.generate(model, contents, generate_content_config)
            candidate = response.candidates[0]
            finish_reason = candidate.finish_reason
            text = self._extract_text_from_candidate(candidate)
            function_calls = self._extract_function_calls(candidate)

            if function_calls:
                # There may be multiple tool calls in one response
                tool_results = []
                for fc in function_calls:
                    tool_result = self._run_tool(fc.function_call)
                    tool_results.append(f"Tool call: {fc.function_call.name}({fc.function_call.args})\nResult: {tool_result}")
                # Combine tool call and model follow-up as one history entry
                combined = (text + "\n" if text else "") + "\n".join(tool_results)
                print(combined)
                conversation.append({'role': 'model', 'content': combined})
                self._add_to_history(combined)
            else:
                print(text)
                conversation.append({'role': 'model', 'content': text})
                self._add_to_history(text)

            if finish_reason == FinishReason.STOP or (text and "!FINISHED_TASK!" in text):
                finished = True
            else:
                # Continue the loop, possibly after a short delay
                time.sleep(0.5)

        print("Finished")
        print("\n--- Last 5 model responses (history) ---")
        for idx, h in enumerate(self.history, 1):
            print(f"[{idx}] {h}\n")
            

if __name__ == "__main__":
    #generate("Repeat !FINISHED_TASK!")
    gemini_handler = GeminiHandler()
    #gemini_handler.solve_task("Calculate 5 * 4, then add 3 to the result. Use tools i don't want you to calculate alone.")
    #gemini_handler.solve_task("You want to create a memory system for yourself. This is a one shot operation so you can't talk to anybody to ask confirmation")
    gemini_handler.solve_task("You are now alive")