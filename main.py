from dotenv import load_dotenv
from datetime import datetime
from openai import OpenAI
import json
import requests
import os

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def run_command(cmd: str): # run linux command
    result = os.system(cmd)
    return result

def create_folder(folder_name: str):
    try:
        os.makedirs(folder_name, exist_ok=True)
        return f"Folder '{folder_name}' created successfully."
    except Exception as e:
        return str(e)

def get_weather(city: str):
    url = f"https://wttr.in/{city}?format=%C+%t"
    response = requests.get(url)

    if response.status_code == 200:
        return f"The weather in {city} is {response.text}"
    
    return "Something went wrong"

available_tools = {
    "get_weather": get_weather,
    "run_command": run_command,
    "create_folder": create_folder
}

SYSTEM_PROMPT = f"""
    You're an helpful AI assistant who is specialized in resolving user query.
    You work on start, plan, action, and observe methodology.

    For the given user query and available tools, plan the step by step execution, based on the planning,
    select the relevant tool from the available tool. and based on the tool selection you perform an action to call the tool.

    Wait for the observation and based on the observation from the tool call resolve the user query.

    Rules:
    - Follow the Output JSON Format.
    - Always perform one step at a time and wait for next input
    - Carefully analyse the user query

    Output JSON Format:
    {{
        "step": "string",
        "content": "string",
        "function": "The name of function if the step is action",
        "input": "The input parameter for the function",
    }}

    Available Tools:
    - "get_weather": Takes a city name as an input and returns the current weather for the city
    - "run_command": Takes linux command as a string and executes the command and returns the output after executing it.
    - "create_folder": Takes folder name as input and creates a folder with the given name.

    Example:
    User Query: What is the weather of new york?
    Output: {{ "step": "plan", "content": "The user is interseted in weather data of new york" }}
    Output: {{ "step": "plan", "content": "From the available tools I should call get_weather" }}
    Output: {{ "step": "action", "function": "get_weather", "input": "new york" }}
    Output: {{ "step": "observe", "output": "12 Degree Cel" }}
    Output: {{ "step": "output", "content": "The weather for new york seems to be 12 degrees." }}
"""

messages = [
    {"role": "system", "content": SYSTEM_PROMPT}
]

while True:
    query = input("User Query: ")  # take input from user
    messages.append({"role": "user", "content": query})  # add user query to message

    while True:
        response = client.chat.completions.create(
            model="gpt-4.1",
            response_format={"type":"json_object"},
            messages=messages
        )

        messages.append({"role": "assistant", "content": response.choices[0].message.content})  # add assistant response to message
        parsed_response = json.loads(response.choices[0].message.content) # parse the response content

        if parsed_response.get("step") == "plan": # if step is plan
            print(f"🧠: {parsed_response.get("content")}") 
            continue

        if parsed_response.get("step") == "action": # if step is action
            tool_name = parsed_response.get("function")
            tool_input = parsed_response.get("input")

            print(f"🔧: Calling tool {tool_name} with input {tool_input}")

            if available_tools.get(tool_name) != False: # if tool is available
                output = available_tools[tool_name](tool_input) # call the tool
                messages.append({"role": "user", "content": json.dumps({"step": "observe", "output": output}) }) # add output to message
                continue

        if parsed_response.get("step") == "output":
            print(f"🤖: {parsed_response.get('content')}")
            break