# Evaluation Notes

These lightweight evals are meant for portfolio-quality manual checks. They avoid automatic
live API calls because research runs consume OpenRouter and search-provider credits.

## How to Use

1. Start the app with Docker.
2. Open `http://localhost:8000/`.
3. Run the questions from `golden_questions.json`.
4. Check each response against the expected behavior.

## Pass Criteria

- The agent returns a non-empty `summary` for answerable questions.
- `key_findings` contains concise numbered findings.
- `sources` contains structured objects with `title`, `url`, `source_type`, and `insight`.
- General biography/product questions do not include irrelevant arXiv papers.
- Academic or technical questions may use arXiv when useful.
- `search_queries` are clean, readable search phrases.
- `core_entities` contains stable entity names, not question words like "who" or "what".
- If retrieval fails, the agent reports that no relevant sources were found instead of using
  model memory.
