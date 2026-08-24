# Flight Agent

An AI agent that searches live flight data via natural language. Built with Claude, Flask, and SerpAPI.

This is a beginner exercise in building LLM-powered agents — not a production tool. A general-purpose assistant like Claude will give better flight advice than this agent. The goal here is to understand how tool use and agent loops work by building something real and runnable. There is significant room to improve it.

## How it works

The project demonstrates LLM tool use. The language model decides when to invoke the flight search tool based on the conversation, the backend executes the search, and the model formats the results.

```
User message
  -> Claude decides to call search_flights
  -> Flask executes the search via SerpAPI
  -> Claude formats the results
  -> User sees the response
```

## Tech stack

| Layer       | Technology                      |
|-------------|---------------------------------|
| AI Agent    | Anthropic Claude                |
| Backend     | Flask                           |
| Flight Data | SerpAPI (Google Flights)        |
| Frontend    | Vanilla JavaScript and CSS      |

## Setup

```bash
git clone https://github.com/yourusername/flight-agent
cd flight-agent

python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt

Before running the app, create a `.env` file in the project root.

Add your API keys:

```env
ANTHROPIC_API_KEY=your_anthropic_api_key
SERPAPI_KEY=your_serpapi_key

python app.py
```

Open http://localhost:5000.

API keys:
- Anthropic: https://console.anthropic.com
- SerpAPI: https://serpapi.com (free tier, 100 searches/month)

## Example queries

- Find me flights from Berlin to New York next Friday
- Cheapest one-way from Frankfurt to Tokyo in August
- Round trip Stuttgart to London, leaving June 20th, returning June 27th

## Project structure

```
flight-agent/
├── app.py                # Flask routes
├── agent.py              # Agent loop and tool dispatch
├── flights.py            # SerpAPI flight search
├── config/
│   ├── __init__.py
│   └── settings.py       # Settings and resource loading
├── prompts/
│   ├── system.txt        # System prompt
│   └── tools.json        # Tool schema
├── templates/
│   └── index.html
├── static/
│   ├── style.css
│   └── app.js
├── requirements.txt
└── .env.example
```
