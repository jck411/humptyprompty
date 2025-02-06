import json
import re
from typing import Any, AsyncIterator, Dict, List, Optional, Sequence, Union
import asyncio
from fastapi import HTTPException

from config import CONFIG, conditional_print
from tools import get_tools, get_available_functions, get_function_and_args

def extract_content_from_openai_chunk(chunk: Any) -> Optional[str]:
    try:
        return chunk.choices[0].delta.content
    except (IndexError, AttributeError):
        return None

def compile_delimiter_pattern(delimiters: List[str]) -> Optional[re.Pattern]:
    if not delimiters:
        return None
    sorted_delims = sorted(delimiters, key=len, reverse=True)
    escaped = map(re.escape, sorted_delims)
    pattern = "|".join(escaped)
    return re.compile(pattern)

async def process_chunks(chunk_queue: asyncio.Queue,
                       phrase_queue: asyncio.Queue,
                       delimiter_pattern: Optional[re.Pattern],
                       use_segmentation: bool,
                       character_max: int):
    working_string = ""
    chars_processed = 0
    segmentation_active = use_segmentation

    while True:
        chunk = await chunk_queue.get()
        if chunk is None:
            if working_string.strip():
                phrase = working_string.strip()
                await phrase_queue.put(phrase)
                conditional_print(f"Final Segment: {phrase}", "segment")
            await phrase_queue.put(None)
            break

        content = extract_content_from_openai_chunk(chunk)
        if content:
            working_string += content
            if segmentation_active and delimiter_pattern:
                while True:
                    match = delimiter_pattern.search(working_string)
                    if match:
                        end_idx = match.end()
                        phrase = working_string[:end_idx].strip()
                        if phrase:
                            await phrase_queue.put(phrase)
                            chars_processed += len(phrase)
                            conditional_print(f"Segment: {phrase}", "segment")
                        working_string = working_string[end_idx:]
                        if chars_processed >= character_max:
                            segmentation_active = False
                            break
                    else:
                        break

async def validate_messages_for_ws(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not isinstance(messages, list):
        raise HTTPException(status_code=400, detail="'messages' must be a list.")
    prepared = []
    for idx, msg in enumerate(messages):
        if not isinstance(msg, dict):
            raise HTTPException(status_code=400, detail=f"Message at index {idx} must be a dictionary.")
        sender = msg.get("sender")
        text = msg.get("text")
        if not sender or not isinstance(sender, str):
            raise HTTPException(status_code=400, detail=f"Message at index {idx} missing valid 'sender'.")
        if not text or not isinstance(text, str):
            raise HTTPException(status_code=400, detail=f"Message at index {idx} missing valid 'text'.")

        if sender.lower() == 'user':
            role = 'user'
        elif sender.lower() == 'assistant':
            role = 'assistant'
        else:
            raise HTTPException(status_code=400, detail=f"Invalid sender at index {idx}.")

        prepared.append({"role": role, "content": text})

    system_prompt = {"role": "system", "content": "You are a helpful assistant. Users live in Orlando, Fl"}
    prepared.insert(0, system_prompt)
    return prepared

async def stream_openai_completion(client, model: str, messages: Sequence[Dict[str, Union[str, Any]]], 
                                 phrase_queue: asyncio.Queue,
                                 stop_event: asyncio.Event) -> AsyncIterator[str]:
    delimiter_pattern = compile_delimiter_pattern(CONFIG["PROCESSING_PIPELINE"]["DELIMITERS"])
    use_segmentation = CONFIG["PROCESSING_PIPELINE"]["USE_SEGMENTATION"]
    character_max = CONFIG["PROCESSING_PIPELINE"]["CHARACTER_MAXIMUM"]

    chunk_queue = asyncio.Queue()
    chunk_processor_task = asyncio.create_task(
        process_chunks(chunk_queue, phrase_queue, delimiter_pattern, use_segmentation, character_max)
    )

    try:
        response = await client.chat.completions.create(
            model=model,
            messages=messages,
            tools=get_tools(),
            tool_choice="auto",
            stream=True,
            temperature=0.7,
            top_p=1.0,
        )

        tool_calls = []

        async for chunk in response:
            if stop_event.is_set():
                try:
                    await response.close()
                except Exception as e:
                    conditional_print(f"Error closing streaming response: {e}", "default")
                break

            delta = chunk.choices[0].delta if chunk.choices and chunk.choices[0].delta else None
            if delta and delta.content:
                yield delta.content
                await chunk_queue.put(chunk)
            elif delta and delta.tool_calls:
                tc_list = delta.tool_calls
                for tc_chunk in tc_list:
                    while len(tool_calls) <= tc_chunk.index:
                        tool_calls.append({"id": "", "type": "function", "function": {"name": "", "arguments": ""}})

                    tc = tool_calls[tc_chunk.index]
                    if tc_chunk.id:
                        tc["id"] += tc_chunk.id
                    if tc_chunk.function.name:
                        tc["function"]["name"] += tc_chunk.function.name
                    if tc_chunk.function.arguments:
                        tc["function"]["arguments"] += tc_chunk.function.arguments

        if not stop_event.is_set() and tool_calls:
            messages.append({"role": "assistant", "tool_calls": tool_calls})
            funcs = get_available_functions()
            
            for tc in tool_calls:
                try:
                    fn, fn_args = get_function_and_args(tc, funcs)
                    resp = fn(**fn_args)
                    messages.append({
                        "tool_call_id": tc["id"],
                        "role": "tool",
                        "name": fn.__name__,
                        "content": json.dumps(resp)
                    })
                except ValueError as e:
                    messages.append({"role": "assistant", "content": f"[Error]: {str(e)}"})

            if not stop_event.is_set():
                follow_up = await client.chat.completions.create(
                    model=model,
                    messages=messages,
                    stream=True,
                    temperature=0.7,
                    top_p=1.0,
                )
                async for fu_chunk in follow_up:
                    if stop_event.is_set():
                        try:
                            await follow_up.close()
                        except Exception as e:
                            conditional_print(f"Error closing follow-up response: {e}", "default")
                        break

                    content = extract_content_from_openai_chunk(fu_chunk)
                    if content:
                        yield content
                    await chunk_queue.put(fu_chunk)

        await chunk_queue.put(None)
        await chunk_processor_task

    except Exception as e:
        await chunk_queue.put(None)
        raise HTTPException(status_code=500, detail=f"OpenAI API error: {e}")
