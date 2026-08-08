# SPU Portal Frontend

Frontend for the University Project Management system. The application uses React and Vite.

## Package manager

This project uses **npm**. All runtime and test dependencies are declared in `package.json`.
Do not install Vitest or Testing Library manually from setup scripts.

## Install

```bash
npm install
```

## Development

```bash
npm run dev
```

Vite will print the local development URL in the terminal (normally `http://localhost:5173`).

## Production build

```bash
npm run build
npm run preview
```

The production build is written to `dist/`.

## Lint

```bash
npm run lint
npm run lint:fix
```

## Tests

Watch mode:

```bash
npm test
```

Run once:

```bash
npm run test:run
```

Coverage:

```bash
npm run test:coverage
```

API-focused suite:

```bash
npm run test:api
```

Role/UI suite:

```bash
npm run test:role-ui
```

## Full frontend release checks (PowerShell)

From the `frontend` directory:

```powershell
.\tests\run_frontend_release_checks.ps1
```

The release script runs the frontend regression tests, ESLint, and the production build.

## Fresh setup

For a clean installation, remove `node_modules` and run:

```bash
npm install
```

The setup scripts no longer add packages individually; `package.json` is the declared dependency source.
