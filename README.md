# BESPOKE — The Self Developing CRM

A file-native CRM where the LLM is the interface and the Conductor is the deterministic mutation router. CRM records are Markdown files with YAML-compatible JSON frontmatter. No database is required.

## Start

```bash
python3 main.py
```

Open `http://127.0.0.1:8765`. This starts the quadrant renderer and the configured 5-minute heartbeat.

Useful commands:

```bash
python3 main.py audit
python3 main.py heartbeat
python3 main.py layout
python3 main.py nightly
python3 main.py action create_contact '{"name":"Jamie Lee","email":"jamie@example.com"}'
```

For a high-risk action that returns `hitl_required: true`, repeat the same action with `"approved": true` after user confirmation.

## Integration runtime

`.system/cogs/workers/integration_worker.py` accepts an injected executor. In ChatGPT/Codex deployments, bind that executor to Zapier MCP. The seed integration catalog reflects the apps already enabled for this project; credentials are not stored in the CRM.

## Self-improvement roles

Nightly work is split into OrchestraAgent (selects an improvement), CodingAgent (builds the dormant bundle), and VerifyAgent (checks it). `python3 main.py nightly` creates a proposal under `.system/orchestrator/proposals/`. Activation is a normal Conductor intent.
