import geoqa.validations.water_loss as water_loss
from geoqa.validations.reference_cases import run_reference_cases


def test_all_reference_cases_pass() -> None:
    results = run_reference_cases()
    failures = [result for result in results if not result.passed]
    assert not failures, [result.as_dict() for result in failures]


def test_aqua_uarl_reference_case_uses_library_computation(monkeypatch) -> None:
    original = water_loss.compute_uarl_l_per_day

    def doubled(*args, **kwargs):
        return 2 * original(*args, **kwargs)

    monkeypatch.setattr(water_loss, "compute_uarl_l_per_day", doubled)
    results = run_reference_cases()
    aqua_uarl = next(
        result for result in results if result.case.name == "aqua1999_uarl_example"
    )

    assert not aqua_uarl.passed


def test_aqua_ili_end_to_end_uses_library_index(monkeypatch) -> None:
    original = water_loss.infrastructure_leakage_index

    def doubled(**kwargs):
        return 2 * original(**kwargs)

    monkeypatch.setattr(water_loss, "infrastructure_leakage_index", doubled)
    results = run_reference_cases()
    aqua_ili = next(
        result for result in results if result.case.name == "aqua1999_ili_end_to_end"
    )

    assert not aqua_ili.passed
