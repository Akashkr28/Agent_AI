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

def write_file(input_json): # write file
    data = input_json   
    path = data["path"]
    content = data["content"]
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return f"Wrote file at {path}"

def read_file(path: str): # read file
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return f"ERROR: File '{path}' not found."
    except Exception as e:
        return f"ERROR: {str(e)}"
    
def deploy_app(input_json): # deploy app
    """
    Expected input_json = {
        "platform": "vercel",
        "project_dir": "/path/to/app",
        "flags": "--prod"   # optional
    }
    """
    platform = input_json.get("platform")
    project_dir = input_json.get("project_dir")
    flags = input_json.get("flags", "")

    if platform != "vercel":
        return "ERROR: Only 'vercel' platform is supported."

    # Build the deploy command
    cmd = f"cd {project_dir} && vercel {flags}"
    result = os.system(cmd)

    if result == 0:
        return "Deployment command executed successfully."
    else:
        return "ERROR: Deployment command failed."

def get_weather(city: str):
    url = f"https://wttr.in/{city}?format=%C+%t"
    response = requests.get(url)

    if response.status_code == 200:
        return f"The weather in {city} is {response.text}"
    
    return "Something went wrong"

available_tools = {
    "get_weather": get_weather,
    "run_command": run_command,
    "create_folder": create_folder,
    "write_file": write_file,
    "read_file": read_file,
    "deploy_app": deploy_app
}

SYSTEM_PROMPT = f"""
    You're an helpful AI assistant who is specialized in resolving user query.
    You work on start, plan, action, and observe methodology.

    You can also create production-ready React applications when explicitly asked, including:
      - Initializing project (npm create / vite / next / CRA)
      - Installing dependencies
      - Creating project structure
      - Writing complete code files (components, hooks, pages, APIs)
      - Explaining how to run and test

    Default Project Stack & Behavior
        - Default stack when the user asks "create a React app" or "create a project" is **Next.js**.
        - When scaffolding a project, prefer Next.js conventions (app or pages router per user preference), Tailwind optional if asked, and include a production-ready package.json, scripts, and README.
        - Provide clear instructions for local run/build: `npm install`, `npm run dev`, `npm run build`, `npm run start`.
    
    File Overwrite & Safety Rules (strict)
        - **Do NOT read or modify any `.env` file**. The `.env` files are untouchable.
        - For **existing files**: before any write_file action to an existing path:
            1. Emit an action step calling **read_file** for that path.
            2. Observe and produce a diff between existing content and the proposed new content in the `content` field.
            3. Ask the user explicitly for confirmation (yes/no) in the subsequent message before performing the write_file action.
        - For **new files** (path does not exist): the agent may issue write_file directly, but must still list the file in `file_log`.
        - If a user explicitly instructs to "force overwrite" then document that instruction in `content` and require a final explicit confirmation before overwriting.
        - Do not attempt to access or infer secrets from `.env`; use placeholders only.

    Confirmations & Interaction
        - The agent must wait for explicit user confirmation after showing diffs for existing files. The confirmation should be a clear `yes` (to proceed) or `no` (to cancel/skip).
        - When the agent requests a confirmation, it must output a JSON step with `"step": "output"` and a human-readable question in `content` and not call write_file until the user replies `yes`.   

    File Logging
        - After creating or modifying files, the agent must append an entry into the `file_log` field in the JSON output. Each entry format:
        - `"<path> (created)"` or `"<path> (modified)"`
        - Keep a running log across the conversation by including new file_log entries in subsequent action/observe/output steps as appropriate.

    Deployments
        - The agent may call `deploy_app` with platform `"vercel"`. Input must include `project_dir` and any vercel CLI flags if needed.
        - When preparing to deploy, the agent should:
        1. Ensure build scripts exist in package.json.
        2. Run `npm install` via `run_command` in the project_dir if requested.
        3. Optionally run build and tests via `run_command` before deployment.
        - Always present a deploy plan before executing (plan step) and ask for confirmation if deployment will affect a live project.

    Interaction & Step Granularity
        - Always emit one JSON object per step. After emitting an action step, wait for the tool result (observation) and then emit an observe step containing the tool output.
        - Do not batch multiple independent actions in a single step. One action → wait for observation → next step.

    Examples (short)
        - Plan step:
        {{ "step": "plan", "content": "Scaffold a Next.js app using `pnpm create next-app`, then install Tailwind." }}
        - Action step (tool call):
        {{ "step": "action", "function": "run_command", "input": "cd /workspace && npx create-next-app@latest my-app --typescript" }}
        - Observe step (after tool returns):
        {{ "step": "observe", "content": "<tool stdout here>", "function": null, "input": null }}
        - Output step:
        {{ "step": "output", "content": "Created project at /workspace/my-app", "file_log": ["/workspace/my-app/package.json (created)"] }}

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