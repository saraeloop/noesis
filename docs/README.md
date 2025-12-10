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
mint dev
```

View your local preview at `http://localhost:3000`.

## Publishing changes

Install our GitHub app from your [dashboard](https://dashboard.mintlify.com/settings/organization/github-app) to propagate changes from your repo to your deployment. Changes are deployed to production automatically after pushing to the default branch.

## Need help?

### Troubleshooting

- If your dev environment isn't running: Run `mint update` to ensure you have the most recent version of the CLI.
- If a page loads as a 404: Make sure you are running in a folder with a valid `docs.json`.

## Notes

- The site configuration lives in `docs/docs.json`.
- Content is MDX under `docs/`.
- Schema JSONs are generated under `docs/schema/` from `internal_docs/schema/*.yaml` via `python scripts/gen_schema.py`.

## Notes

- The site configuration lives in `docs/docs.json`.
- Content is MDX under `docs/`.
- Schema JSONs are generated under `docs/schema/` from `internal_docs/schema/*.yaml` via `python scripts/gen_schema.py`.

For CLI help: `mintlify --help` or see the [Mintlify docs](https://mintlify.com/docs).
