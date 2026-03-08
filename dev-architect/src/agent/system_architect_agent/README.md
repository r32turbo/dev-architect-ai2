 # Dev Architect Agent

## Project Description

Dev Architect Agent is a Python-based AI system that generates a **software architecture document** from an analyst's requirements.
The system processes the analyst document and produces a structured architecture output automatically.

## Project Structure

```
dev-architect
│
├── src/agent/system_architect_agent
│   ├── main.py
│   ├── architect_agent.py
│   ├── analyst_document.txt
│   ├── architecture_output.txt
│   ├── requirements.txt
│   └── keys.env
```

## Requirements

* Python 3.9+
* Required Python packages listed in `requirements.txt`

Install dependencies:

```
pip install -r src/agent/system_architect_agent/requirements.txt
```

## How to Run

From the project root directory run:

```
python src/agent/system_architect_agent/main.py
```

After execution, the generated architecture will be saved in:

```
architecture_output.txt
```

## Output

The program reads:

```
analyst_document.txt
```

and generates:

```
architecture_output.txt
```

## Environment Variables

If the project requires API keys, add them to:

```
keys.env
```

Example:

```
OPENAI_API_KEY=your_api_key_here
```
