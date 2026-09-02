# Second-Machine Reproducibility Checklist — Clean Environment Verification

**Branch:** `wuc-2027` | **Current status:** Local/self verification only; second-machine verification **PENDING**
**Current local verification (2026-09-02):** `python -m unittest discover -s tests -p test_*.py` → `Ran 175 tests in 40.665s OK` and `python scripts/wuc-2027/run_all.py` → `All 5 cases PASS — MATCH` and `python scripts/wuc-2027/validate_csv_evidence.py` → `All headline numbers MATCH` — all on same workstation `RTX 3060, Core Temp 14 sensors`. This does **NOT** establish second-machine reproducibility per task §8.

## Clean Environment Definition

A clean environment is **any** of:
- GitHub Actions `ubuntu-latest` runner (preferred, log is public)
- Second workstation / VM with fresh `git clone` and fresh `venv` (no `.geoqa_cache` reuse)
- `I:\My Drive\Projects` clean clone on same host but new venv (acceptable interim, but GitHub Actions is stronger)

## Exact Commands to Run (copy-paste)

```powershell
# 1. Clone and checkout
git clone https://github.com/NiloferTaher/GeoQA.git
cd GeoQA
git checkout wuc-2027

# 2. Create clean env
python -m venv .venv-clean
.venv-clean\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -e .[dev]  # if dev extras needed for validation

# 3. Run tests
python -m unittest discover -s tests -p "test_*.py"

# 4. Run WUC smoke repro
python scripts/wuc-2027/run_all.py

# 5. Validate headline numbers (read-only, no GeoQA import for headline)
python scripts/wuc-2027/validate_csv_evidence.py
```

## Acceptance Criteria

| Step | Expected | Actual (to be filled on clean run) | Verdict |
|---|---|---|---|
| `unittest discover` | `Ran 175 tests OK` (or 169 if spectral not yet merged to main, but 175 on wuc-2027) | _pending_ | _pending_ |
| `run_all.py` | `All 5 cases PASS — MATCH` with `wuc_run_log.csv` written | _pending_ | _pending_ |
| `validate_csv_evidence.py` | `All headline numbers MATCH` — ds1 2 issues full, ds5 spectral 3 issues, 5 catalog entries | _pending_ | _pending_ |
| `wuc_run_log.csv` | Byte-identical against committed baseline **excluding** explicitly documented machine-dependent timing fields (wall-clock `duration` may differ; `issue_count`, `execution_status`, `feature_count`, `SHA` must match) | _pending_ | _pending_ |

**Important:** Timing fields (`duration ~122s` vs ~15s) are machine-dependent and must be compared as *ranges*, not byte-identical. Issue counts, execution_status, feature counts, and SHA must be byte-identical.

## What NOT to Claim Until Actually Reproduced

- Do NOT claim `second-machine verified` until the table above shows PASS on a clean environment log (attach log file).
- Do NOT claim `same result` until `wuc_run_log.csv` has been compared excluding timing fields.
- Current tag `v0.3.1-wuc-2027-verified` is **self-verified on development workstation** — see `Git/tag status` section in final report.

## How to Capture Outcome

On clean machine, redirect:
```
python -m unittest discover -s tests -p "test_*.py" > second_machine_tests.log 2>&1
python scripts/wuc-2027/run_all.py > second_machine_run_all.log 2>&1
python scripts/wuc-2027/validate_csv_evidence.py > second_machine_validate.log 2>&1
```
Commit logs to `reports/wuc-2027/second_machine/` or attach to GitHub Actions run.

