# Conversation memory demo

This demo compares the same chatbot with and without saved conversation state.
Conversation state is the message history that the program keeps for one conversation.
LangGraph runs a graph, which is a set of connected functions.
This graph contains one chatbot function.
An application programming interface (API) accepts program requests and returns results.
`langchain-openai` supplies `ChatOpenAI`, a connector for model API requests.
The connector sends requests directly to OpenAI.

## Message flow

```text
User message -> LangGraph state -> chatbot -> ChatOpenAI -> OpenAI API -> model
                                      ^
                  Saved messages -----|
                  Same thread, with memory only
```

A system instruction tells the model how to respond.
Both versions use the same prompts, system instruction, model, and graph.
A checkpointer saves and restores graph state.
The checkpointer is the only difference between the two graphs.

## Required items

- Python 3.11 or later.
- An internet connection for package installation.
- An OpenAI API key for the live demo.
- Access to the selected model through the OpenAI API.

An API key is a secret value that identifies your account to the service.

Each user message makes two model requests.
The live demo uses credits from your OpenAI API account.

## Install the packages

Use Windows PowerShell for these commands.

1. Open the demo folder.

   ```powershell
   Set-Location -LiteralPath 'C:\Users\Be Flith Rich\My Project Folder\Paytm Hackathon\memory-checkpoint-demo'
   ```

2. Create a separate Python environment for the demo.

   ```powershell
   py -V:Astral/CPython3.12.13 -m venv .venv
   ```

   This command selects Python 3.12.13 on this computer.
   On another computer, use the available Python 3.11 or later installation.

3. Install the required packages.

   ```powershell
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   ```

The environment contains a Python executable and the demo packages.
The commands use that Python executable directly.

## Configure the live demo

1. If `.env` does not exist, create the local settings file.

   ```powershell
   Copy-Item -LiteralPath .env.example -Destination .env
   ```

2. Open the settings file.

   ```powershell
   notepad .env
   ```

3. Set `OPENAI_API_KEY` to your OpenAI API key.

4. Keep `OPENAI_MODEL=gpt-5.4-nano` for the supplied model.

5. Save the file.

6. Close the editor.

The settings file stays on your computer.
The `.gitignore` file tells Git to ignore `.env`.
The program reads `.env` from the demo folder.
An environment variable is a named setting that a program receives from its operating system.
If an environment variable already has a value, the program uses that value instead of `.env`.

## Run the live demo

1. Run the program.

   ```powershell
   .\.venv\Scripts\python.exe demo.py
   ```

2. Wait for the `You:` prompt.

3. Type a message.

4. Press Enter.

   Both versions receive the same new message.
   The program prints the conversation messages that each version sends to OpenAI.
   Each `AI:` answer comes from the model response.
   The program also prints the OpenAI response ID and token counts.
   A response ID identifies one API response.
   A token is a unit that the model uses to process text.

5. Type the next message at `You:`.

6. Type `/quit` to stop.

The system instruction is fixed.
The program does not contain fixed user examples or fixed AI answers.
Live model wording can change.

## Demonstrate the result to an examiner

1. Ask the examiner to choose an unusual fact or a new project code.

2. Type that information as the first message.

3. Read both answers.

4. Type a question that needs the earlier information.

   Do not repeat that information in the question.

5. Compare the two answers.

   Without memory, the second request contains only the new question.
   With memory, the second request also contains the earlier message and answer.

6. Examine the conversation message counts.

   | Version | First request | Second request |
   |---|---:|---:|
   | Without memory | 1 | 1 |
   | With memory | 1 | 3 |

   The counts do not include the shared system instruction.
   Each request also contains that instruction.

7. Type `/reset` to start an empty conversation.

8. Repeat the question without the earlier information.

   Both versions now receive only that question.
   The program uses a new thread ID for the memory version.
   It does not delete the earlier thread from the running process.

## Run in VS Code

1. Open the demo folder as a VS Code workspace.

   ```powershell
   code --new-window .
   ```

2. Open `demo.py`.

3. Press Ctrl+Shift+P.

4. Select `Python: Select Interpreter`.

5. Select `.venv\Scripts\python.exe` from this demo folder.

   If the list does not contain that path, select `Enter interpreter path`.
   The complete path is below.

   ```text
   C:\Users\Be Flith Rich\My Project Folder\Paytm Hackathon\memory-checkpoint-demo\.venv\Scripts\python.exe
   ```

6. Press F5.

7. If VS Code requests a debug configuration, select `Memory checkpoint demo`.

8. Type messages in the integrated terminal at `You:`.

The `.vscode/settings.json` file selects the local Python environment by default.
An earlier interpreter selection can require the manual selection above.
The `.vscode/launch.json` file specifies the local Python executable for F5.

## Identify the current prompt

| Prompt | Meaning | Input |
|---|---|---|
| `PS ...>` | PowerShell is ready. | Type the complete program command. |
| `>>>` | Python is in interactive mode. | Type `exit()` to return to PowerShell. |
| `You:` | The demo is ready. | Type a chat message, `/reset`, or `/quit`. |

## Explain the result

`operator.add` adds new messages to the end of the message list.
`InMemorySaver` saves graph state in the running Python process.
The `thread_id` value identifies the conversation.
All memory requests in one conversation use the same generated thread ID.
LangGraph restores the saved state before it adds the next user message.

The model receives the earlier messages again through the API.
This demo does not train the model.
The connector does not supply conversation memory.
LangGraph supplies the saved state.

## Memory limits

The graph without a checkpointer can receive earlier messages if your application supplies them.
This demo supplies only one new user message for each call.

`InMemorySaver` keeps state only while the same saver remains available in the running process.
A different `thread_id` starts a separate conversation.
A Python restart or Colab runtime restart removes this memory.
A checkpoint is a saved copy of graph state.
This demo does not save checkpoints to a database or disk.

## Change the model

1. Select an OpenAI model that your API account can access.

2. Set `OPENAI_MODEL` to that model ID in `.env`.

   The command below overrides that setting for one run.

   ```powershell
   .\.venv\Scripts\python.exe demo.py --model gpt-5.4-nano
   ```

## Common problems

| Problem | Action |
|---|---|
| `Missing OPENAI_API_KEY` | Set the API key in `.env`. |
| HTTP 401 | Examine the OpenAI API key. |
| Model access error | Examine the model ID and account access. |
| HTTP 429 | Examine your API account credits and request limits. |
| Import error | Install the packages with the demo environment's Python executable. |
| VS Code import warnings | Select this demo's Python interpreter. |
| VS Code still shows built-in name warnings | Use `Developer: Reload Window` after interpreter selection. |

## Technical terms

| Term | Meaning |
|---|---|
| API | An interface that accepts program requests and returns results. |
| API key | A secret value that identifies an account to a service. |
| Checkpointer | A component that saves and restores graph state. |
| Checkpoint | A saved copy of graph state. |
| Connector | A package that adapts model requests to another interface. |
| Environment | A separate Python installation with its required packages. |
| Graph | A set of functions with defined execution paths. |
| Model | A language model that produces a response from supplied messages. |
| Node | A function in the graph. |
| State | The data that the graph uses during a run. |
| System instruction | A message that gives response instructions to the model. |
| Thread | One conversation with an assigned identifier. |

## Check the demo

A regression check examines behavior after a code change.
This check covers typed messages, separate histories, empty input, reset, quit, and response details.
The check uses local test responses.
The demo uses live OpenAI responses.

1. Run the check from the demo folder.

   ```powershell
   .\.venv\Scripts\python.exe -B -m unittest discover -s tests -v
   ```

2. Make sure that the result is `OK`.

An earlier live check on 2026-10-30 made four OpenAI requests with a new project code.
The version without memory could not supply that code on the second turn.
The version with memory supplied that code.

The README uses ASD-STE100 rules and selected dictionary checks.
A full independent dictionary audit is not complete.

## Files

| Path | Purpose |
|---|---|
| `demo.py` | Live chatbot and memory comparison. |
| `README.md` | Setup, demonstration, and check instructions. |
| `requirements.txt` | Required package versions. |
| `.env` | Your local API key and model settings. |
| `.env.example` | Empty settings template. |
| `.gitignore` | Rules that keep local files out of Git. |
| `.vscode/` | Python selection and F5 settings. |
| `tests/test_demo.py` | One regression check. |
| `.venv/` | Installed Python environment. |

## References

- [LangGraph memory](https://docs.langchain.com/oss/python/langgraph/add-memory)
- [LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence)
- [OpenAI GPT-5.4 nano](https://developers.openai.com/api/docs/models/gpt-5.4-nano)
- [OpenAI Chat Completions](https://developers.openai.com/api/reference/python/resources/chat/subresources/completions/methods/create)
- [VS Code Python environments](https://code.visualstudio.com/docs/python/environments)
- [ASD-STE100 official reference](https://www.asd-ste100.org/)
