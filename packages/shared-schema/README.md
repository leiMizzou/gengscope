# Shared Schema Plan

This package will hold shared contracts between API, web app, worker and agent integrations.

Planned contents:

```text
openapi/
  gengscope.openapi.yaml
jsonschema/
  risk-card.schema.json
  integrity-event.schema.json
  evidence-pointer.schema.json
typescript/
  generated-types.ts
python/
  generated_models.py
```

Contract-first targets:

- Risk card shape.
- Integrity event shape.
- Evidence pointer shape.
- Agent API response shape.
