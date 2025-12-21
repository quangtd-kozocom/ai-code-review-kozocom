# 🤖 AI Code Reviewer

AI-powered code review system that automatically reviews pull requests using multiple specialized agents.

## Features

- **Multi-Agent Review**: Security, Style, and Logic analysis
- **GitHub Integration**: Webhook receiver with HMAC validation
- **Async Processing**: Celery-based background processing
- **Smart Aggregation**: Deduplication and prioritization of findings

## Quick Start

### Prerequisites

- Python 3.13+
- [uv](https://github.com/astral-sh/uv) (recommended) or pip
- Redis (or Upstash)
- GitHub App credentials

### Installation

```bash
# Clone the repo
git clone https://github.com/your-org/ai-code-reviewer.git
cd ai-code-reviewer

# Install dependencies
uv sync
# OR with pip
pip install -e .

# Copy environment file
cp .env.example .env
# Edit .env with your credentials
```

### Running Locally

```bash
# Start the API server
make dev

# In another terminal, start the Celery worker
make worker
```

### Testing with ngrok

```bash
# Expose local server
ngrok http 8000

# Use the ngrok URL for GitHub webhook
```

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   GitHub    │────>│   FastAPI   │────>│   Celery    │
│   Webhook   │     │   Handler   │     │   Worker    │
└─────────────┘     └─────────────┘     └─────────────┘
                                              │
                    ┌─────────────────────────┼─────────────────────────┐
                    │                         │                         │
              ┌─────▼─────┐           ┌───────▼───────┐           ┌─────▼─────┐
              │ Security  │           │    Style      │           │   Logic   │
              │   Agent   │           │    Agent      │           │   Agent   │
              └─────┬─────┘           └───────┬───────┘           └─────┬─────┘
                    │                         │                         │
                    └─────────────────────────┼─────────────────────────┘
                                              │
                                        ┌─────▼─────┐
                                        │Aggregator │
                                        └─────┬─────┘
                                              │
                                        ┌─────▼─────┐
                                        │ Publisher │
                                        └───────────┘
```

## Configuration

See `.env.example` for all configuration options.

## License

MIT
