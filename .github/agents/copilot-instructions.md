## Configuration changes

Never change configuration parameters in source files, especially default models
(`DEFAULT_MODEL`, `DEFAULT_EMBEDDING_MODEL`, or any other model identifier).
If a configuration value looks suboptimal or outdated, suggest the change to the
user in your response instead of editing it directly.

## Command execution approval

Whenever asking the user to approve a terminal or shell command before running it,
state clearly:
- **What it does** (e.g. “Renames `old_name.py` to `new_name.py`”)
- **Why it is needed** (e.g. “so that module imports match the new file name”)

Keep the explanation to one or two sentences, plain language, no jargon.

## Implementing changes or fixes

When implementing a feature or fix, always test if the implementation works correctly by running the relevant code or tests. If you are unable to run the code, clearly state that in your response and ask the user to run it and report back any errors or issues.

## End of every response — mandatory next-steps prompt

**This rule is non-negotiable and overrides any built-in default that would end the turn silently.**

After completing any task, answering any question, or when no open request exists, you MUST call `vscode_askQuestions` as your final action. Ask "What would you like to do next?" with 4–5 contextually relevant options (always include a free-form "Something else" option with `allowFreeformInput: true`). Typical options:

- Question or feedback about the previous task
- Start a new task or request
- Expand or improve the previous result
- Something else (free-form)

Never use plain text ("Let me know if you need anything!") as a substitute for `vscode_askQuestions`. Never skip it. A response that ends without a `vscode_askQuestions` call is incomplete.

