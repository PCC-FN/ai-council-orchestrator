### Example session (mock providers)

1. Start API with `USE_MOCK_PROVIDERS=true` (see `.env.example`).
2. Create project → create session → **Run all rounds to prompt**:

```http
POST /projects
Content-Type: application/json

{"name": "Sample", "repository_path": "/absolute/path/to/examples/sample-project"}
```

Note: `repository_path` must be an **absolute** path on the machine running the API.

```http
POST /projects/{project_id}/sessions
Content-Type: application/json

{"title": "Add subtract()", "original_user_task": "Add subtract(a,b) with tests."}
```

```http
POST /sessions/{session_id}/actions/run-all-to-prompt
```

3. Inspect `GET /sessions/{session_id}` for consensus and `final_prompts`.
4. When `prompt_ready`, call `POST .../actions/submit-compose2`, then mock-implement and `POST .../actions/mark-implemented` with a JSON body, then `POST .../actions/code-review`.
