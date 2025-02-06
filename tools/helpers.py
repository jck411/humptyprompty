import inspect
from typing import Callable, Dict, Tuple
import json

def check_args(function: Callable, args: dict) -> bool:
    sig = inspect.signature(function)
    params = sig.parameters
    for name in args:
        if name not in params:
            return False
    for name, param in params.items():
        if param.default is param.empty and name not in args:
            return False
    return True

def get_function_and_args(tool_call: dict, available_functions: dict) -> Tuple[Callable, dict]:
    function_name = tool_call["function"]["name"]
    function_args = json.loads(tool_call["function"]["arguments"])
    if function_name not in available_functions:
        raise ValueError(f"Function '{function_name}' not found")
    function_to_call = available_functions[function_name]
    if not check_args(function_to_call, function_args):
        raise ValueError(f"Invalid arguments for function '{function_name}'")
    return function_to_call, function_args
