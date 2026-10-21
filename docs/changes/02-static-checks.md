# 02: Static checks: ruff, strict mypy, ESLint and Prettier

## Issue

### Problem

Neither half of the codebase had a linter, a formatter or (on the backend) a type checker. Formatting
depended on whoever wrote the line, mistakes that tools catch in seconds (naive dates, untyped `any` data,
promises nobody awaits, click handlers that keyboard users cannot reach) were left to review, and CI
(task group 1) had nothing to enforce beyond the tests.

### Plan

- Backend: ruff for linting and formatting, mypy in strict mode with the pydantic plugin, configured in a
  new `backend/pyproject.toml`. Fix every finding in code; keep exceptions narrow and justified.
- Frontend: ESLint 9 flat config (typescript-eslint type-aware rules, react-hooks, jsx-a11y,
  react-refresh, eslint-config-prettier) and Prettier matching the existing style. Fix every finding.
- Formatting changes in their own `style:` commits; behaviour changes in separate, explained commits.
- Run all of it in CI.

## Pull request

### What changed

**Configuration**

- `backend/pyproject.toml` (new). Ruff: line length 120 (the existing code was written to 120; 11 lines
  were longer), target py312, rule sets E, W, F, I, B, UP, SIM, ASYNC, S (bandit), DTZ, PT, PLE, PLW, PLC,
  PLR, RUF. mypy: `strict = true`, `warn_unreachable = true`, pydantic plugin with `init_forbid_extra`,
  `init_typed`, `warn_required_dynamic_aliases`; checks `app`, `tests` and `alembic`. The pytest settings
  moved here from `pytest.ini` (deleted), so there is one tool configuration file.
- `frontend/eslint.config.js`, `frontend/.prettierrc.json`, `frontend/.prettierignore` (new);
  `frontend/package.json` gains the scripts `lint`, `format`, `format:check`, `typecheck`.
- `.github/workflows/ci.yml`: the backend job runs `ruff check .`, `ruff format --check .` and `mypy`
  before the migrations and tests; the frontend job runs `npm run format:check`, `npm run lint` and
  `npm run typecheck` before the unit tests and the build.
- `README.md`: a short "Static checks" section under Testing.

**Formatting** (two `style:` commits, no behaviour change): `ruff format` reformatted 44 backend files;
Prettier reformatted 26 frontend files. At `printWidth` 100 Prettier would have changed 52 files, at 110
40, at 120 26, so 120 is closest to the existing style.

**Backend fixes**

- `date.today()` (host time zone) replaced by `app/core/clock.utc_today()` for the delivery `actual_date`,
  the upcoming-deliveries count and the monthly-trend cutoff (ruff DTZ011). Production runs in UTC, so its
  behaviour is unchanged; on a machine in another zone the dates no longer disagree with the UTC
  timestamps Postgres stores and groups by. The spend-metrics test, which compared the server's local
  month with Postgres' UTC month, could fail around local midnight for that reason.
- Relationship target types imported under `TYPE_CHECKING` in every model (21 undefined-name findings).
- The three domain enums are `StrEnum` (ruff UP042). Values, database labels (SQLAlchemy stores member
  names), JSON and CSV output are unchanged; the code already used `.value` wherever it formatted a status.
  The OpenAPI schema was compared before and after and is byte-for-byte identical.
- `paginate()` now takes the read schema and returns `PaginatedResponse[S]` instead of an untyped tuple
  that every list endpoint repacked (7 routers, one line each now). This matches the convention in the
  project brief ("paginate returning PaginatedResponse"). The rows are validated with the same schema the
  response model used implicitly, so responses are unchanged.
- `require_permission()` was annotated as returning a plain function; it returns an async dependency.
- `TrustedProxyMiddleware` uses Starlette's ASGI types instead of `Any`.
- Audit payloads, report rows and the two small JSON endpoints are typed (`dict[str, Any]`,
  `dict[str, float]`, `dict[str, str]`). The only OpenAPI difference in the whole change: the responses of
  `/api/v1/reports/on-time-delivery-rate` and `/health` now declare their value types
  (`additionalProperties: number` / `string`). The bodies are unchanged.
- The inventory value multiplies `cost * current_stock` instead of `current_stock * cost`: SQLAlchemy
  types a product by its left operand, so the expression is now `Decimal` as the schema says. Same SQL
  result.
- `Settings` exposes its `Environment` literal type; tests reuse it.
- `HTTP_422_UNPROCESSABLE_ENTITY` (deprecated by Starlette, warned on every rejected opening balance)
  replaced by `HTTP_422_UNPROCESSABLE_CONTENT`. The test suite now finishes with no warnings.
- Bandit "hardcoded password" hits that are not secrets (the OAuth2 token type `"bearer"`, the JWT token
  kinds `"access"`/`"refresh"`, the secret-generation hint, the `"changed"` marker written to the audit log
  for a password change, and the admin-password placeholder that the seed already refuses outside
  development/test) carry a per-line `noqa` with the reason. The rules stay on everywhere else.
- The PO list status filter uses `Annotated[..., Query()]` (FastAPI's recommended form) instead of a call
  in the default value (bugbear B008). `PaginatedResponse` uses PEP 695 type parameters.
- isort is told that `alembic` is the installed package (the migrations folder has the same name).

**Backend tests**

- Every test, fixture and helper is annotated and the suite is type-checked strictly like the application.
  The factory fixtures get Protocol types in `tests/fixture_types.py` (`MakeUser`, `AuthHeaders`,
  `StockMatchesLedger`) so tests see their real call signatures.
- Optional results are narrowed with explicit asserts; count queries use `scalar_one()` so a missing row
  fails loudly instead of comparing `None`.
- Parametrize names are tuples, compound asserts are split so a failure names the broken condition, and
  `subprocess.run` calls state `check=False` because the next line asserts on the return code with the
  captured output. No test was removed, loosened or skipped.

**Frontend fixes**

- `api/client.ts`: the refresh and login responses are typed (`AccessTokenResponse`), the interceptor
  narrows its error with `axios.isAxiosError` before reading it, and rejections are rethrown from the async
  handler instead of wrapped in `Promise.reject` (same behaviour).
- `AuthProvider` and `ToastProvider` moved to their own modules (`lib/AuthProvider.tsx`,
  `components/ui/ToastProvider.tsx`) because Fast Refresh can only hot-swap modules that export nothing but
  components. The hooks and contexts stay at their old paths, so no consumer imports or test mocks changed.
- `AuthProvider` derives its initial `isLoading` from the session hint instead of setting it inside the
  mount effect (react-hooks `set-state-in-effect`).
- Accessibility (jsx-a11y): the modal's and the drawer's click-to-close backdrops are separate
  `aria-hidden` layers instead of click handlers on wrapper elements; keyboard users close with Escape or the
  close button as before. Both are now announced as modal dialogs named by their title (`role="dialog"`,
  `aria-modal`, `aria-labelledby`; the drawer had no dialog role before). The toast stack is a polite live
  region, the toast dismiss button has a label, and the close buttons are `type="button"`.
- Promise handling (typescript-eslint `no-floating-promises`, `no-misused-promises`): mutations return
  their cache invalidations from `onSuccess`, as the other mutations already did, so `mutateAsync` settles
  after the lists are refreshed. Async form and button handlers (which all catch and show their own errors)
  and router navigations are called with an explicit `void`.
- The receive-stock modal no longer pre-fills its quantities by setting state in an effect; its form mounts
  fresh each time the modal opens and computes them in its initial state. A side effect: a background
  refetch of the order while the modal is open no longer wipes the quantities being typed.
- `useBackendReadiness` resets its status in `retry()` instead of at the start of its effect.
- Tests: mocks return `Promise.resolve()` instead of being `async` functions with no `await`; the dashboard
  test keeps the spy from `vi.spyOn` instead of reading the method back (`unbound-method`).

### Why

- **Ruff** replaces flake8, isort, pyupgrade and bandit with one fast tool and one configuration, and its
  formatter is Black-compatible. **mypy strict** because the code was already written with SQLAlchemy 2's
  typed `Mapped[...]` API and pydantic models, so strictness was reachable, and it found two real
  annotation mistakes (`require_permission`, `paginate`) and the untyped data paths.
- **Bandit in tests**: `S101` (assert), `S105`/`S106`/`S107` (fixed test passwords) and `PLR2004` (inline
  expected values) are ignored for `tests/**` only. Tests assert by design, and their passwords are fixed
  fixtures for throwaway accounts, never real credentials. `S603`/`S607` are ignored only in the two test
  files that run alembic and the container start script with fixed arguments, and `S608` only in
  `alembic/versions/**`, where SQL is composed from module constants.
- **Pylint argument limits**: `max-args = 8` for services, which take the session plus keyword-only domain
  values; `PLR0913`/`PLR0917` are off in `app/routers/**` because FastAPI declares each query parameter as an
  endpoint argument (`list_products` takes 10).
- **ESLint type-aware rules** (`recommendedTypeChecked`) because the frontend's risk is untyped API data and
  forgotten promises, which the non-type-aware set cannot see. `eslint-plugin-react-hooks` 7 brings the
  React Compiler checks (`set-state-in-effect` and others) that the redesign (task group 9) will rely on.
  The configuration is generic (no file-specific exceptions), so it carries over to React 19, Tailwind 4
  and shadcn/ui unchanged, and generated shadcn components will be linted like everything else.
- **Prettier `endOfLine: "auto"`**: git converts text files to CRLF on Windows checkouts
  (`core.autocrlf`), so with the default `lf` a fresh Windows clone would fail `prettier --check` on every
  file. The repository stores LF and CI runs on Linux. Ruff's formatter already detects line endings per
  file.

### What remains relaxed in mypy

Nothing at module level: there are no `[[tool.mypy.overrides]]`. The application, the tests and the
Alembic migrations all pass `strict = true`. There is exactly one `# type: ignore`, with its error code:
`alembic/versions/1046460b0276_initial_schema.py:121`, `postgresql.JSONB(astext_type=sa.Text())`
(`no-untyped-call`), because SQLAlchemy's `JSONB.__init__` has no annotations upstream and the migration
is historical code that should not be rewritten.

### Alternatives considered

- **Relaxing mypy for tests** (`disallow_untyped_defs = false` under `tests.*`): the usual compromise and
  the fallback the task allowed. Annotating the tests turned out to be mostly mechanical (Protocol types for
  the three factory fixtures, `-> None` on tests) and it caught real looseness (comparisons against values
  that could be `None`), so no override was needed.
- **Moving the hooks instead of the providers** to satisfy react-refresh: would have changed the import
  path of `useAuth` / `useToast` in about 15 files and every `vi.mock("@/lib/auth-context")`.
- **Disabling `react-refresh/only-export-components` or `allowExportNames: ["useAuth", "useToast"]`**:
  rejected; the split is small and is the fix the rule asks for.
- **`checksVoidReturn: { attributes: false }`** for `no-misused-promises` (common in React projects):
  rejected; an explicit `void` at each call site shows that the promise is intentionally not awaited, and
  every such handler catches its own errors.
- **Keeping `str, Enum`** with a per-line ignore: `StrEnum` is the standard-library form and changes nothing
  observable here (verified by diffing the OpenAPI schema).
- **Excluding old migrations from formatting**: they were reformatted like everything else; formatting
  does not change what a migration does, and the round-trip migration test still passes.
- **Setting pytest-asyncio's `asyncio_default_fixture_loop_scope`** to silence its start-up notice: setting
  it to `function` breaks the session-scoped database fixture (ScopeMismatch), and `session` changes which
  event loop the tests run in. Left unset; task group 4 upgrades pytest and pytest-asyncio and settles the
  loop scope there.

### New dependencies (name, exact version, why)

Backend (`requirements-dev.txt`, development only):

- `ruff` 0.17.1: linter and formatter.
- `mypy` 2.4.0: static type checker.
- `types-passlib` 1.7.7.20260211: type stubs for passlib, which ships none (task group 3 replaces passlib;
  the stubs go with it).

Frontend (`devDependencies`, all exact versions):

- `eslint` 9.39.5 and `@eslint/js` 9.39.5: the linter and its core recommended rules (ESLint 9, as
  requested; ESLint 10 exists, but eslint-plugin-jsx-a11y 6.10.2 declares support only up to 9).
- `typescript-eslint` 8.71.1: TypeScript parser and type-aware rules (8.72.0 was 3 days old; 8.71.1 has
  been out for two weeks).
- `eslint-plugin-react-hooks` 7.1.1: rules of hooks and the React Compiler checks.
- `eslint-plugin-jsx-a11y` 6.10.2: accessibility rules for JSX.
- `eslint-plugin-react-refresh` 0.5.7: keeps modules hot-reloadable under Vite.
- `eslint-config-prettier` 10.1.8: turns off ESLint rules that conflict with Prettier.
- `globals` 17.13.0: browser and Node global variable sets for the flat config.
- `prettier` 3.9.9: formatter (3.9.10 was under two weeks old).

### Tests added or changed

No tests added or removed. Backend tests: annotations, `None` narrowing asserts, tuple parametrize names,
split compound asserts, `check=False` on `subprocess.run`, `utc_today()` in two tests. Frontend tests: the
provider test imports `AuthProvider` from its new module and awaits `act()` with an explicit promise;
`readiness.test.ts` and `DashboardPage.test.tsx` mocks return promises explicitly.

### How to verify (exact commands)

```bash
cd backend
.venv/Scripts/python -m pip install -r requirements-dev.txt
.venv/Scripts/ruff check .
.venv/Scripts/ruff format --check .
.venv/Scripts/python -m mypy
TEST_DATABASE_URL=postgresql+asyncpg://procuraflow:procuraflow@127.0.0.1:55432/procuraflow_test \
  DATABASE_URL=postgresql+asyncpg://procuraflow:procuraflow@127.0.0.1:55432/procuraflow \
  .venv/Scripts/python -m pytest -q
```

```bash
cd frontend
npm install
npm run format:check
npm run lint
npm run typecheck
npm test
npm run build
npm audit --omit=dev
```

```bash
docker run --rm -v "$PWD:/repo" -w /repo rhysd/actionlint:1.7.7 -color=false
```

### Results (measured)

Measured on the development machine on 2026-10-22.

| Check | Before | After |
|---|---|---|
| ruff check (final rule set) | 124 findings, 44 files not formatted | 0 findings, 103 files formatted |
| mypy strict (app, tests, alembic) | 373 errors in 33 files | 0 errors in 103 files (12.7 s warm) |
| ESLint | 54 errors | 0 problems (about 70 s, type-aware) |
| Prettier | 26 files not formatted | all files formatted (8.6 s) |
| Backend suite | 242 passed, 2 warnings | 242 passed, 0 warnings, 1110.30 s |
| Frontend suite | 58 passed in 12 files | 58 passed in 12 files |
| `tsc -b` | clean | clean (20.7 s) |
| Production bundle | JS 828.40 kB (243.54 kB gzip), CSS 19.31 kB | JS 828.85 kB (243.85 kB gzip), CSS 19.34 kB |
| `npm audit --omit=dev` | 0 | 0 |
| actionlint 1.7.7 | | no findings |
| OpenAPI schema | | identical except the two value-type declarations noted above |

The bundle grows by 0.45 kB for the new ARIA attributes, the split modules and the receive form component.
The backend suite ran slower than in task group 1 (934.99 s) on the same machine; nothing in this change
touches the hot paths (most of the time is password hashing), so this is machine load. Not yet measured: the
CI job durations on GitHub-hosted runners (visible in the Actions tab after the owner pushes).
