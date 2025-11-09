# Documentation

This `docs/` folder houses the Next.js site plus supporting artifacts used in the README.

- `app/` – MDX-powered routes that surface guides, release notes, and cookbook content.
- `runs/` – sample episode outputs for screenshots (not bundled with the package).
- `artifacts/` – focused guides such as [`state.md`](artifacts/state.md) that explain JSON payloads referenced in the repository README.

## Developing locally

```bash
cd docs
pnpm install
pnpm dev
```

Visit `http://localhost:3000` to browse the docs with hot reload.
