---
name: testing-quality
description: >
  Define, write, review and enforce the test strategy and quality gates for the
  whole system health dashboard (Python backend, WebSocket protocol, React
  frontend, design system). Use this skill whenever the user mentions tests,
  pytest, Vitest, Playwright, coverage, mocks or fakes, flaky tests, fixtures,
  CI pipeline, quality gates, regression, load or soak testing, mutation
  testing, test data, TDD, "is this tested enough", or "set up CI", even if
  they only say "make sure it works" or "verify this". Also use it when
  adding a feature (to decide which tests are required), when a bug is fixed
  (regression test), and before declaring any work done.
---

# Testing & Quality Skill

The cross-cutting quality contract for the **Linux system health dashboard**.
Each other skill lists tests for its own area; this skill defines the shared
rules, tooling, CI gates and the final release checklist. When tooling choices
differ from older notes, this file and the frontend skill agree: **pytest for
Python, Vitest for TypeScript (not Jest), Playwright for end to end**.

## 1. Non-negotiable rules

| # | Rule | Why |
|---|------|-----|
| 1 | **Tests are deterministic.** No real sleeps, no real network, no dependence on host load, time of day, or random seeds that are not logged. Use fake clocks, injected RNGs, fake sockets. | A flaky test is worse than no test; people stop trusting the suite. |
| 2 | **Test behavior at boundaries, not implementation.** Assert outputs, state and observable effects. | Refactors must not break tests that are still correct. |
| 3 | **Fakes live at port boundaries and only in test code.** Production code never contains fabricated metrics, and test-only adapters are never reachable in a production build. | Same honesty rule as the monitor: never fake data in production paths. |
| 4 | **Every bug fix ships with a regression test** that fails before the fix. | Bugs recur where tests are absent. |
| 5 | **Coverage is a floor, not a goal.** Branch coverage with layer-specific thresholds, plus review of what the tests actually assert. | 100 % coverage with weak assertions proves little. |
| 6 | **The suite runs unprivileged and hermetically.** Privileged or host-dependent tests are explicitly marked and opt-in. | Matches the "no root by default" rule; keeps CI portable. |
| 7 | **Quality gates are automated and blocking.** No manual "remember to run it". | Gates that depend on memory get skipped. |
| 8 | **Never delete or weaken a test to make a build pass** without approval (section 15). Quarantine with an owner and expiry instead. | Silent test erosion is how regressions ship. |

## 2. Workflow

1. **Classify the change** (domain logic, adapter, API, protocol, UI, theme, deployment) and look up required test types in section 4.
2. **Write the test first when practical** (TDD for domain and application logic, protocol parsing, rate math, backoff). For exploratory UI work, write tests as soon as the shape settles, in the same change.
3. **Choose the cheapest layer that can catch the failure** (section 3).
4. **Make it deterministic** (section 5).
5. **Run locally** (fast tier), then let CI run the full gates (section 9).
6. **Review test quality** with the checklist in section 12 before merging.
7. **Record results** for performance and soak tests; compare against budgets.

## 3. Test pyramid for this project

| Tier | Share of tests | Speed target | Scope |
|------|----------------|--------------|-------|
| Unit | ~70 % | whole tier under 30 s | Pure functions, domain, use cases with fake ports, components in isolation |
| Contract / integration | ~20 % | under 2 min | Adapters against real psutil/`/proc` fixtures, API routes, WebSocket endpoint, socket client with fake `WebSocket`, schema-vs-fixture checks |
| End to end | ~5 % | under 5 min | Real backend (with test composition) + built frontend in a browser |
| Performance / soak / chaos | ~5 % | nightly or on demand | Load, 1-hour soak, network failure scenarios |

Prefer a lower tier when it can detect the same defect. E2E tests cover **journeys** (boots, streams, loses connection, recovers, switches theme), not every widget state.

## 4. Required tests by change type

Use this as the "what must exist" map. Details live in each skill.

| Change area | Must include |
|-------------|--------------|
| Metric collector (`linux-monitoring`) | Unit tests for rate/delta math and counter reset; adapter tests with monkeypatched psutil raising `AccessDenied`, missing API, `None` values; recorded `/proc` and cgroup fixtures; contract test shared by all adapters of the port; non-root run; edge cases (no swap, no sensors, 1 CPU, many cores, hung mount) |
| Use case / sampler | Failure isolation, interval floor, bounded history, fake clock; cancellation on shutdown |
| REST route (`python-backend`) | Status codes, schema, error envelope, validation 422, limits, `dependency_overrides` |
| WebSocket (`realtime-websocket`) | Contract fixtures (server and client), hello first, `seq` monotonic, bad message, oversize, rate limit, origin rejection, slow-client isolation, shutdown 1001, leak test |
| Frontend widget (`react-dashboard`) | All seven states (loading, ok, partial, unavailable, stale, disconnected, error), keyboard, labels and units, axe |
| Frontend socket client | Backoff and jitter, fatal codes, stale detection, gap handling, unmount cleanup, strict-mode double mount |
| Design tokens (`ui-design-system`) | Contrast matrix, light/dark parity, token-usage lint, visual baselines |
| Deployment config | Settings validation, default bind address, non-root start, health/ready endpoints |

## 5. Determinism and flakiness policy

- **Time**: inject a `Clock` port in Python; use `vi.useFakeTimers()` in Vitest. `asyncio.sleep` in tests is banned except inside fake-clock helpers. Use `anyio`/`asyncio.Event` and "wait until" helpers with a timeout instead of fixed delays.
- **Randomness**: inject RNGs (backoff jitter, sampling); property tests log their seed (Hypothesis does this by default).
- **Ordering**: run with random order (`pytest-randomly`) to expose hidden coupling; the seed is printed so failures reproduce.
- **Isolation**: no shared mutable module state; each test builds its own container via `composition.py` or fixtures; temp dirs via `tmp_path`; no writes outside them.
- **Network**: only localhost sockets on ephemeral ports (`port=0`), never fixed ports; block external network in unit tiers (`pytest-socket` or equivalent).
- **Timeouts**: every test has a timeout (`pytest-timeout`, Vitest `testTimeout`, Playwright timeouts) so hangs fail fast.
- **Flaky test handling**: a test that fails intermittently is **quarantined within one day** (marked `@pytest.mark.quarantine` or `test.skip` with a linked issue, owner and expiry date), fixed, and restored. Blind automatic retries are not a fix; a limited retry (max 1) is allowed only for E2E browser tests, and every retry is reported.
- **Host dependence**: assertions on live host values check **shape and range** (`0 <= pct <= 100`, types, units), never exact numbers.

## 6. Fakes, fixtures and test data

- **Fakes over mocks** for ports: write small in-memory implementations (`FakeCpuReader`, `FakeClock`, `FakeSocket`) in `tests/fakes/`, reused everywhere. Use `unittest.mock` / `vi.fn` for interaction checks sparingly.
- **Recorded real fixtures** for `/proc`, `/sys` and cgroup files and for WebSocket/REST payloads, stored under `tests/fixtures/` and `contracts/`. Record sources (kernel version, distro) in a README next to them.
- **Test-only composition**: end-to-end tests start the app through `tests/e2e/app_with_fakes.py` that wires fakes into the same composition root. The production entry point must **refuse to start** if a fake adapter is configured (guard test included), and fakes are never imported from `src/`.
- **Builders/factories** for entities (`make_cpu_snapshot(percent=...)`) with sensible defaults; one obvious override per test.
- **Frontend**: MSW for REST, a `FakeWebSocket` class for sockets, fixtures shared with the server contract tests.
- Never reuse production secrets or real hostnames; fixtures are scrubbed (no usernames, real command lines, tokens).

## 7. Python testing setup

```toml
# pyproject.toml (excerpt)
[tool.pytest.ini_options]
addopts = "-ra --strict-markers --strict-config --cov=src/monitor --cov-branch --cov-report=term-missing"
asyncio_mode = "auto"
timeout = 10
markers = [
  "unit: fast, pure, no I/O",
  "integration: real adapters/fixtures, localhost only",
  "e2e: full stack with browser",
  "perf: benchmarks and load (not in default run)",
  "soak: long-running (nightly)",
  "privileged: needs elevated permissions (opt-in)",
  "quarantine: known flaky, tracked by an issue",
]
testpaths = ["tests"]

[tool.coverage.report]
fail_under = 85
exclude_also = ["if TYPE_CHECKING:", "raise NotImplementedError"]
```

- Layer thresholds: after the main run, enforce stricter floors with `coverage report --include="src/monitor/domain/*,src/monitor/application/*" --fail-under=95`.
- Default CI run excludes `perf`, `soak`, `privileged`, `quarantine`: `-m "not perf and not soak and not privileged and not quarantine"`.
- Parameterize heavily (`pytest.mark.parametrize`) for edge-case matrices; use `hypothesis` for rate/delta math, parsers and protocol validation.
- Async: `pytest-asyncio` (or the `anyio` plugin), never `asyncio.run` inside tests; await cancellation in teardown; assert no leaked tasks with a fixture that compares `asyncio.all_tasks()` before and after.
- Permissions: simulate with monkeypatch (`PermissionError`, `psutil.AccessDenied`) and `chmod 000` temp files; run the suite as an unprivileged user in CI to prove the "no root" rule.
- Containers: cgroup behavior tested with recorded cgroup v1 and v2 file trees; one optional CI job runs inside a memory/CPU-limited container to validate real limits.

## 8. TypeScript testing setup

- **Vitest** + `@testing-library/react` + `user-event` + `jsdom`; **MSW** for REST; **Playwright** for E2E and visual baselines; `vitest-axe` / `@axe-core/playwright` for accessibility.
- Coverage via `@vitest/coverage-v8` with thresholds, global 85 % and **95 % for `domain/` and `infrastructure/ws`** (use per-glob thresholds; verify the syntax against the installed Vitest version).
- Query by role/label/text, never by CSS class or test-id unless there is no accessible handle; test what the user sees.
- Snapshot tests only for small, stable outputs (formatters, serialized schemas); never snapshot whole component trees.
- Strict mode: render components inside `<React.StrictMode>` in tests so double-mount and effect-cleanup bugs show up.
- Playwright: run chromium by default; add firefox/webkit in nightly. Use `page.clock` or the fake-sampler backend to control time; no `waitForTimeout`.

## 9. CI pipeline and quality gates

Stages (fail fast, cheap first). Gate = blocks merge.

| Stage | Checks | Gate |
|-------|--------|------|
| 1. Static | `ruff` (lint + format check), `mypy --strict`, `tsc --noEmit`, ESLint (`jsx-a11y`, `react-hooks`), Prettier check, Stylelint | Yes |
| 2. Architecture | `import-linter` (domain/application do not import infrastructure or psutil), `dependency-cruiser` or `eslint-plugin-boundaries`, token-usage lint | Yes |
| 3. Security | `bandit`, `pip-audit`, `npm audit --omit=dev`, secret scan (`gitleaks`) | Yes (high/critical) |
| 4. Unit | pytest unit tier, Vitest, random order, coverage floors | Yes |
| 5. Contract + integration | Schema generation unchanged, shared fixtures validated by Pydantic and Zod, adapter fixture tests, API/WebSocket endpoint tests, contrast/parity tests | Yes |
| 6. Build | Production frontend build, bundle-size budget (`size-limit`), backend package build, container image build | Yes |
| 7. E2E | Playwright against the test-composition backend and built frontend, axe, visual diffs | Yes |
| 8. Matrix (nightly or release) | Python versions supported; Debian-family and RHEL-family containers; kernel with/without PSI; cgroup v1/v2 | Yes for release |
| 9. Perf / soak / chaos (nightly) | 100-200 clients at 1 Hz for 1 hour; memory/task/socket growth; message-size budget; chaos scenarios | Yes for release; trend tracked |

Rules: pin tool versions; cache dependencies; upload coverage, Playwright traces and screenshots as artifacts; run stages 1 to 5 in parallel where possible; a red main branch is fixed or reverted before new work merges.

## 10. Performance, load and chaos testing

- **Python microbenchmarks**: `pytest-benchmark` for collectors, serialization, hub fan-out; compare against stored baselines and fail on regression beyond a tolerance (for example 20 %).
- **WebSocket load**: an asyncio script using the `websockets` **client** (dev dependency) or Locust. Apache Bench cannot test WebSockets; use it only for simple REST checks if at all.
- **Soak**: `tracemalloc` snapshots and process RSS sampled over an hour; assert flat memory, stable task/socket counts, no growth in drop counters under normal load.
- **Chaos**: drop the network mid-stream, silent half-open peer, server restart, proxy idle timeout; assert the UI shows stale then recovers without refresh.
- Budgets come from the other skills (message size, CPU overhead, bundle size, latency); this skill makes them **CI-enforced**.
- Run performance tests on a consistent runner; results on shared CI hardware are trends, not absolutes.
- Prometheus/Grafana are observability tools, not test frameworks; they can visualize soak results but are not required.

## 11. Security testing (scoped to this app)

- Static: `bandit` for Python; ESLint security rules; dependency audits.
- Dynamic/behavioral tests written by us: origin rejection, token handling (not logged), oversize and malformed frames, rate-limit enforcement, error envelope leaks nothing, CORS closed by default, default bind `127.0.0.1`, command lines redacted, no `dangerouslySetInnerHTML` (lint rule).
- Fuzzing: property-based tests with Hypothesis for parsers (`/proc` readers, protocol messages). Coverage-guided fuzzers for native code are out of scope.
- Optional with approval: OWASP ZAP baseline scan against the REST API (limited WebSocket support), Semgrep rules.
- There is no maintained `pytest-security` package; do not add one.
- Not applicable by default: authorization matrices, data-protection and compliance suites (no user data, read-only API). Add them if authentication is introduced (approval required).

## 12. Test quality review checklist

Before merging tests, confirm:

- [ ] The test fails if the behavior breaks (try deleting the fix or flipping a condition).
- [ ] Assertions check outcomes, not just "no exception".
- [ ] One reason to fail per test; name states the behavior: `test_unavailable_sensor_is_reported_not_zero`.
- [ ] Arrange-Act-Assert is visible; setup is not copy-pasted (use fixtures/builders).
- [ ] No sleeps, fixed ports, shared state, or order dependence.
- [ ] Edge cases covered: empty, zero, one, max, negative delta, missing field, unicode, very long strings.
- [ ] Error paths asserted (the right `Unavailable` kind, the right close code, the right error envelope).
- [ ] No fabricated values leak into production code; fixtures are scrubbed.
- [ ] Runs fast enough for its tier; heavy tests are marked.
- [ ] Optional but valuable on core logic: **mutation testing** (`mutmut` or `cosmic-ray` for Python; `StrykerJS` for TypeScript) on `domain/` and protocol code, run nightly; surviving mutants point to weak assertions. Needs approval as a new tool.

## 13. Common pitfalls

- Testing mocks instead of behavior; asserting that a mock was called with exactly the implementation's arguments.
- Using Jest in the Vite project (duplicate transforms); mixing Jest and Vitest APIs.
- Hard-coding live host values (`assert cpu == 12.3`); or fabricating metrics inside production code "for testing".
- `time.sleep` / `waitForTimeout` to "let things settle".
- Fixed ports and shared global state causing order-dependent failures.
- Treating coverage percentage as proof; testing getters to raise the number.
- Snapshot tests of large trees that everyone auto-updates.
- Skipping the unprivileged run, so tests silently depend on root.
- Slow, flaky E2E tests covering what a unit test could.
- Retrying flaky tests until green.
- No leak checks for tasks and sockets in async/WebSocket code.
- Server and client tests using different hand-written payloads instead of shared fixtures.
- Accessibility and contrast verified manually once, never in CI.
- Test-only adapters reachable from the production entry point.
- Letting the suite grow slow until developers stop running it.

## 14. Release checklist (aggregate Definition of Done)

All must be true. Each line points to the skill that owns the detail.

- [ ] CI stages 1 to 7 green on the release commit; stage 8 and 9 green on the latest nightly. (this skill)
- [ ] Coverage meets floors: 85 % overall, 95 % on domain/application, protocol, hub and client socket code; branch coverage on. (this skill)
- [ ] No quarantined tests past their expiry; no tests deleted or weakened without approval. (this skill)
- [ ] Collectors return typed results; unsupported, permission, partial and container cases tested; suite passes as non-root. (`linux-monitoring`)
- [ ] API and WebSocket contract fixtures validated by both server and client; schema unchanged or approved. (`realtime-websocket`, `python-backend`)
- [ ] Hub bounded; slow-client isolation, leak, shutdown and chaos tests pass; soak shows flat memory. (`realtime-websocket`)
- [ ] Every widget handles all seven data states; axe clean in both themes; contrast matrix and token parity pass. (`react-dashboard`, `ui-design-system`)
- [ ] Production entry point refuses fake adapters; default bind is localhost; error responses leak nothing. (`python-backend`)
- [ ] Performance budgets (message size, bundle size, CPU, latency) enforced in CI and met. (all)
- [ ] Documentation of limitations per metric and of test commands is current. (`linux-monitoring`, this skill)

## 15. Operations requiring user approval

Ask before:

- Adding a new test framework, runner or major plugin (including mutation, fuzzing, ZAP, Semgrep, Chromatic or Storybook-based testing).
- Changing the test architecture (tiers, markers, where fakes live, test-composition approach).
- Adding test dependencies not listed in section 16.
- Removing, skipping long-term, or weakening existing tests or coverage thresholds.
- Lowering a performance budget or an accessibility threshold.
- Running tests that need elevated privileges, touch the real network, or modify the host.

## 16. Dependencies

**Python:** `pytest`, `pytest-asyncio`, `pytest-cov`, `pytest-timeout`, `pytest-randomly`, `pytest-benchmark`, `pytest-socket`, `hypothesis`, `httpx`, `websockets` (client for integration/load only), `jsonschema`, `ruff`, `mypy`, `import-linter`, `bandit`, `pip-audit`; optional `pytest-xdist` for parallel runs, `locust`.

**TypeScript:** `vitest`, `@vitest/coverage-v8`, `@testing-library/react`, `@testing-library/user-event`, `@testing-library/jest-dom`, `jsdom`, `msw`, `@playwright/test`, `vitest-axe` or `@axe-core/playwright`, `eslint` with `typescript-eslint`, `jsx-a11y`, `react-hooks`, `prettier`, `stylelint`, `size-limit`, `dependency-cruiser`.

**CI and hygiene:** `gitleaks`, `npm audit`, container build tooling.

**Not used:** Jest, `pytest-security`, AFL++, Apache Bench for WebSockets, Prometheus/Grafana as test frameworks.