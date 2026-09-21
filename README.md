# Flight Agent

An AI agent that searches live flight data. Built with Claude, LangGraph, Flask, and SerpAPI.

This is an exercise in building LLM-powered agents. The goal here is to understand how tool use and agent loops work by building something real and runnable. There is significant room to improve it.

## How it works

The project demonstrates LLM tool use with a human-in-the-loop step built on LangGraph. The language model decides when to invoke a flight search tool based on the conversation, the backend executes the search, and the model formats the results.

```
User message
  -> Claude decides to call search_flights
  -> User picks Google Flights (live prices) or a Skyscanner deep-link search
     (better for budget carriers Google Flights often misses)
  -> Flask executes the search via SerpAPI or builds the deep-link
  -> Claude formats the results
  -> User confirms before a real booking-link lookup runs
  -> User sees the response
```

All search and booking inputs (airport codes, dates, cabin class, etc.) are validated with Pydantic before any external API call is made, so malformed input fails fast instead of wasting an API call.

## Tech stack

| Layer            | Technology                      |
|-------------------|---------------------------------|
| AI Agent          | Anthropic Claude                |
| Agent Orchestration | LangGraph (human-in-the-loop)  |
| Backend           | Flask                           |
| Request Validation | Pydantic                       |
| Flight Data       | SerpAPI (Google Flights) + Skyscanner deep-links |
| Frontend          | Vanilla JavaScript and CSS      |
| Containerization  | Docker + Docker Compose         |

## Setup

```bash
git clone https://github.com/yourusername/flight-agent
cd flight-agent
```

Before running the app (either way below), create a `.env` file in the project root with your API keys:

```env
ANTHROPIC_API_KEY=your_anthropic_api_key
SERPAPI_KEY=your_serpapi_key
```

### Option A: Docker (recommended)

```bash
docker compose up --build
```

Open http://localhost:5000.

### Option B: Local Python

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt
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
├── agent.py              # LangGraph agent loop, tool dispatch, human-in-the-loop gates
├── flights.py             # SerpAPI flight search and booking lookup
├── budget_search.py       # Skyscanner deep-link builder for budget carriers
├── booking_links.py       # Short-lived redirect links for booking form submissions
├── schemas.py              # Pydantic request/response models and validation
├── config/
│   ├── __init__.py
│   └── settings.py       # Settings and resource loading
├── prompts/
│   ├── system.txt        # System prompt
│   └── tools.json        # Tool schema
├── templates/
│   ├── index.html
│   └── booking_redirect.html
├── static/
│   ├── style.css
│   └── app.js
├── Dockerfile
├── docker-compose.yml
├── .dockerignore
├── requirements.txt
└── .env.example
```