# Noēsis Docs (Mintlify)

This is the Mintlify site for the Noēsis documentation. We run source-first; PyPI will follow.

## Local preview

Install the Mintlify CLI:

```bash
npm i -g mintlify
```

Start the dev server from `docs/`:

```bash
cd docs
mintlify dev
```

Preview at `http://localhost:3000`.

## Link checks

```bash
cd docs
mintlify broken-links
```

## Notes

- The site configuration lives in `docs/docs.json`.
- Content is MDX under `docs/`.
- Schema JSONs are generated under `docs/schema/` from `internal_docs/schema/*.yaml` via `python scripts/gen_schema.py`.

For CLI help: `mintlify --help` or see the [Mintlify docs](https://mintlify.com/docs).
