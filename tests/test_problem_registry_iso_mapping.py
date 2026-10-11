from geoqa.problem_registry import _EXPLICIT_ISO_CATEGORIES, problem_definitions


def test_explicit_iso_category_names_are_registered() -> None:
    definitions = problem_definitions()
    unknown_names = set(_EXPLICIT_ISO_CATEGORIES) - set(definitions)
    assert not unknown_names, f"Unregistered names in ISO mapping: {sorted(unknown_names)}"


def test_accuracy_and_crs_problems_have_explicit_iso_categories() -> None:
    definitions = problem_definitions()
    missing_names = sorted(
        name
        for name, definition in definitions.items()
        if definition.category in {"accuracy", "crs"}
        and name not in _EXPLICIT_ISO_CATEGORIES
    )
    assert not missing_names, f"Accuracy/CRS problems missing explicit ISO mapping: {missing_names}"
