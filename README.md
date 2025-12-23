# Tessera-2600

CLI-only OSINT tool that generates phone-number variations and checks them across services with rich terminal output.

- Runtime: Python 3.8+
- Distribution: PyPI package `tessera-2600` (console scripts installed)
- Primary CLI commands: `tessera`, `tessera-2600`, or `tessera2600`

## Installation

From PyPI (recommended):

```bash
pip install tessera-2600
```

From source (editable dev install):

```bash
git clone https://github.com/Seraphim-Solutions/tessera.git
cd tessera
pip install -e .
```

## Quick start

After installing from PyPI, use the console script:

```bash
# Basic run (auto threads/timeouts per services)
tessera -n "+420 731x4x748"

# Choose specific services
tessera -n "+420 731x4x748" --services seznamcz <another_service>

# Use country-specific mobile prefixes when first digit is unknown (x)
tessera -n "+420 xxxxxxxx" --use-country-prefixes

# Show services and rate limit guidance
tessera --show-services
tessera --show-rate-limits

# Save aggregated results (format inferred by extension)
tessera -n "+420 731x4x748" -o results.json

# Stream durable JSONL of all checks (append-only)
tessera -n "+420 731x4x748" --jsonl-out runs/checks.jsonl

# Save per-service outputs and then auto cross-reference
tessera -n "+420 731x4x748" \
  --per-service-out-dir out/ \
  --per-service-format json \
  --cross-ref-after-scan --cross-ref-output out/crossref.json

# Standalone cross-reference mode (no scanning): pass files/dirs
tessera --cross-ref out/ facebook.json instagram.json \
        --cross-ref-output out/crossref.csv
```

Aliases installed by the package: `tessera`, `tessera-2600`, and `tessera2600` (all equivalent).

Note: `--number/-n` is required for scanning runs. It is not required when using informational or analysis modes such as `--show-services`, `--show-rate-limits`, or `--cross-ref`.

The tool automatically detects country codes and suggests using country-specific mobile prefixes:

- 🇨🇿 Czech Republic (+420): Prefixes 6, 7
- 🇸🇰 Slovakia (+421): Prefix 9
- 🇺🇸 USA/Canada (+1): Prefixes 2-9
- 🇬🇧 United Kingdom (+44): Prefix 7
- 🇩🇪 Germany (+49): Prefix 1

## Project Structure

```
tessera/
├── pyproject.toml                     # Build and metadata (setuptools)
├── README.md                          # This file
├── LICENSE
├── src/
│   └── tessera_2600/
│       ├── __init__.py
│       ├── tessera_cli.py             # CLI implementation (Rich-powered)
│       ├── config.py                  # Configuration settings and UX strings
│       ├── utils.py                   # Utilities (validation, logging, proxies)
│       ├── generator.py               # Phone number generation/expansion
│       ├── checker.py                 # Service checker orchestration
│       ├── core/
│       │   ├── __init__.py
│       │   ├── models.py              # CheckResult, RunSummary schemas
│       │   ├── adapters.py            # Legacy-to-structured adapters
│       │   ├── plugin_api.py          # External plugin entry point API
│       │   ├── declarative_service.py # Runner for JSON/YAML-described services
│       │   ├── proxy_manager.py       # Proxy rotation and management
│       │   ├── threading_manager.py   # Thread coordination
│       │   └── work_distributor.py    # Work queue management
│       ├── services/
│       │   ├── __init__.py            # Descriptor loader and registry
│       │   ├── utils.py
│       │   └── descriptors/           # Built-in service descriptors
│       │       ├── *.json             # Preferred descriptor format
│       │       └── *.yaml|*.yml       # Optional if PyYAML is installed
│       └── operations/
│           ├── __init__.py
│           ├── variation_generator.py
│           └── results_handler.py
└── tests/
    ├── test_*.py                      # `unittest` test modules
```

## Development

### Running Tests

By default, tests work with the standard library `unittest`:

```bash
python -m unittest discover -s tests -p 'test_*.py' -v
```

Optionally, you can use pytest (uncomment in `requirements.txt` and install):

```bash
pytest -q
```

### Code Formatting

```bash
black .
flake8 .
```

### Type Checking

```bash
mypy .
```

### Packaging and Publishing (PyPI)

The project uses a `src/` layout and `pyproject.toml` with setuptools. Console scripts are declared under `[project.scripts]` and install `tessera`, `tessera-2600`, and `tessera2600`.

Build artifacts:

```bash
python -m pip install --upgrade build twine
python -m build                      # produces dist/*.whl and dist/*.tar.gz
twine check dist/*                   # optional validation
pip install dist/*.whl               # install locally
```

## Outputs and exports

The CLI supports multiple export paths to suit different workflows:

- Aggregated results: `--output/-o <path>`
  - Format is inferred by file extension: `.json`, `.csv`, or `.txt`.
  - JSON schema: `{ timestamp, total_found, accounts: [ { number, platform, url, ... } ] }`.

- Per-service outputs: `--per-service-out-dir <dir>` with `--per-service-format {json,csv,txt}`
  - Writes one file per platform (e.g., `facebook.json`, `instagram.csv`) into the given directory.
  - JSON per-service files include a header `{ timestamp, service, total_found, accounts: [...] }`.

- Durable stream (append-only): `--jsonl-out <path>`
  - Appends every individual check as one JSON object per line for resilience against interruptions.

- Cross-reference numbers across files: `--cross-ref <files/dirs...>`
  - Analyzes two or more inputs (you may pass directories; known result patterns are auto-discovered).
  - Saves to `--cross-ref-output <path>`; format is inferred by extension (`.json`, `.csv`, `.txt`).
  - By default, reports numbers present in at least two inputs; use `--cross-ref-all` to require presence in all inputs.
  - You can also enable `--cross-ref-after-scan` to automatically cross-reference the per-service files just written.

## Contributing

We welcome contributions of new services. You can:

- Add a declarative descriptor under `src/tessera_2600/services/descriptors/` (JSON preferred; YAML optional if `PyYAML` is available). See the sections below for schema and examples.
- Or provide an external plugin package exposing an entry point under the `tessera.services` group (see `src/tessera_2600/core/plugin_api.py`).

Then open a Pull Request to the official repository. General workflow:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/new-service-<key>`)
3. Commit your changes (`git commit -m 'Add <service_key> descriptor'`)
4. Push to the branch (`git push origin feature/new-service-<key>`)
5. Open a Pull Request

## Legal Notice

This tool is for educational and legitimate OSINT purposes only. Users are responsible for complying with all applicable laws and regulations in their jurisdiction. The developers assume no liability for misuse.

## Credits

- Pattern detection inspired by [social-media-detector-api](https://github.com/yazeed44/social-media-detector-api) by yazeed44

## License

GNU General Public License v3.0 or later (GPLv3+) — see `LICENSE` for full text

<!-- Changelog removed; see Git history for changes. -->
## Service model

Tessera uses a descriptor‑only model for services. Each service is defined by a JSON (or optional YAML) file under `src/tessera_2600/services/descriptors/`. No Python service classes are required for built‑in behavior.

## Threading and Performance

The CLI runs sequentially by default for stability. You can enable conservative concurrency with the `--threads` (or `-t`) option:

Examples
- Auto (recommended based on selected services): omit the flag → `tessera -n "+420 731x4x748"`
- Explicit threads: `tessera -n "+420 731x4x748" --threads 4`

Notes
- Respect per‑service delays and consider proxies to improve reliability.
- If `--timeout` is not set, Tessera picks a recommended delay based on the selected services.
- If `--threads` is not provided, Tessera picks a conservative maximum based on the selected services.

## Troubleshooting

- Timeouts or connection errors: Increase `--timeout` or use proxies via `--proxy-file`.
- Rate limits or CAPTCHA: Slow down, use proxies, and respect platform ToS. The tool will surface `[RATE LIMITED]` or `[BLOCKED]` statuses when detected.
- Invalid number pattern: Ensure it starts with a `+<countrycode>` and uses `x` wildcards. Example: `+420 731x4x748`.

## Declarative services only (JSON/YAML descriptors)

Tessera uses a descriptor‑only model for service integrations:

- Author a JSON descriptor in `src/tessera_2600/services/descriptors/` and Tessera will load it at runtime.

Key points
- No new runtime deps: JSON is used for descriptors by default to avoid adding YAML libraries.
- Optional YAML: You can also author `.yaml`/`.yml` descriptors if `PyYAML` is installed (dev optional). If the library is not present, YAML files are ignored.
- Uniform UX: Descriptors show up the same way for `--show-services` and rate-limit summaries.

Minimal schema (JSON; YAML uses the same fields)

```
{
  "schema_version": 1,
  "service_key": "myservice",
  "display_name": "My Service",
  "description": "Example declarative service",
  "requires_proxy": false,
  "recommended_delay": 2,
  "timeouts": { "request": 10 },
  "rate_limits": { "rpm": 30 },
  "endpoints": [
    {
      "name": "check",
      "method": "POST",
      "url": "https://example.com/api/check",
      "headers": { "Content-Type": "application/x-www-form-urlencoded" },
      "body": { "phone": "${phone}" },
      "success_signals": [
        { "type": "status", "equals": 200, "weight": 1.0 }
      ],
      "failure_signals": [
        { "type": "status", "equals": 404, "weight": 1.0 }
      ],
      "retry": { "max_retries": 1, "backoff_ms": 500 }
    }
  ]
}
```

How it works
- Descriptors are parsed into dataclasses (see `src/tessera_2600/core/descriptor_models.py`).
- `src/tessera_2600/core/declarative_service.py` executes the endpoints, evaluates success/failure signals, and produces the same legacy status strings (`[FOUND]`, `[NOT FOUND]`, `[ERROR]`, etc.).
- Confidence weights are scaled to 0..100 and compared against `config.CONFIRMATION_THRESHOLD` to decide a positive match.

Add a new descriptor
1. Create `src/tessera_2600/services/descriptors/<service_key>.json` or `.yaml` using the schema above.
2. Ensure `service_key` is unique and not already implemented in Python.
3. Run the CLI normally; the new service will be available by its `service_key`.

Testing descriptors
- Unit tests should mock HTTP (`requests.Session.request`) to avoid network usage.
- See `tests/test_declarative_service.py` for a minimal example.

Example YAML descriptor

- This repository ships both JSON (`src/tessera_2600/services/descriptors/seznamcz.json`) and YAML (`src/tessera_2600/services/descriptors/seznamcz.yaml`) examples for Seznam.cz. JSON is loaded by default (no extra dependencies). YAML is illustrative and will be used only if `PyYAML` is installed.

## Implementing a new service (step-by-step)

Add a service via descriptors (recommended for simple, single-request checks)

- Create a file under `src/tessera_2600/services/descriptors/<service_key>.json` (or `.yaml`).
- Use the minimal schema shown above. Important fields:
  - `service_key`: unique identifier (lowercase, no spaces), e.g., `myservice` or `acmeus`.
  - `display_name`: human-friendly name shown in CLI (aliases are derived automatically).
  - `requires_proxy` and `recommended_delay`: influence CLI guidance and scheduling.
  - `endpoints`: at least one HTTP request with `method`, `url`, optional `headers`, and signal rules:
    - `success_signals`: e.g., `{ "type": "status", "equals": 200, "weight": 1.0 }`
    - `failure_signals`: same shape, used to cancel positives.
- Place `${phone}` anywhere you want the current phone string substituted (query, headers, or body).
- Run the CLI and verify the service is discovered:
  - `tessera --show-services`
  - Run with an explicit service list: `tessera -n "+420 731x4x748" --services <service_key>`

Notes on naming and resolution
- Users can refer to a service by `service_key`, by `display_name` (case-insensitive), or by a simplified variant (punctuation removed). For keys like `seznamcz`, the tool also maps `seznam` as a convenience.
- Choose a clear `display_name` and concise `service_key` to improve discoverability.

Descriptor file precedence and duplicates
- If both `<name>.json` and `<name>.yaml`/`<name>.yml` exist, Tessera prefers the JSON descriptor.
- YAML descriptors are only considered if `PyYAML` is installed; otherwise they are ignored.
- When duplicates are present, Tessera logs a warning and surfaces the selected file in CLI output.
- The `--show-services` table includes a “Descriptor” column that shows the exact filename (including extension) that was loaded for each service. The same table is printed after the banner at startup.

Descriptor search paths
- Built-in descriptors are loaded from the package directory `src/tessera_2600/services/descriptors`.
- You can add extra directories via environment variable `TESSERA_EXTRA_DESCRIPTOR_DIRS` (or `TESSERA_DESCRIPTOR_DIRS`).
  - Use your OS path separator to provide multiple directories (e.g., `export TESSERA_EXTRA_DESCRIPTOR_DIRS="/abs/path/one:/abs/path/two"`).
  - Files from all search paths are grouped by base name; selection rules above (JSON preferred) still apply.

Testing a descriptor
- Unit tests should mock HTTP I/O. See `tests/test_declarative_service.py` for an example using `@patch("requests.Session.request")`.

Practical tips
- Set realistic `recommended_delay` and `requires_proxy` to avoid bans; descriptors expose these directly.
- Keep HTTP headers conservative and rotate proxies where appropriate (see `core/proxy_manager.py`).
- For internationalization or multiple regional variants, encode regions in `service_key` (e.g., `acmeus`, `acmeuk`) and rely on the built-in alias normalization.
