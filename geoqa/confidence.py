"""How much to believe a finding.

A validator that reports only "this is wrong" forces the operator to treat
every finding identically, which is the wrong response to a gap of three
metres and to a gap of three centimetres when the tolerance is a metre. The
second one is usually a false positive, and nobody can tell that from the
severity alone.

This module turns each finding into an explicit, inspectable claim about its
own reliability. The claim is probabilistic because the underlying truth is,
but it is computed rather than guessed: it is a posterior over "is this a
genuine defect", built from evidence the validator can actually see.

**Where the number comes from.** A prior, multiplied by likelihood ratios
for each piece of observed evidence, normalised:

    posterior odds = prior odds x product of likelihood ratios

The prior is the base rate of the defect class: of all findings this check
produces, what proportion are genuine. That number cannot be invented. It has
to come from labelled outcomes, and the library refuses to produce a
calibrated probability without one, because a plausible-looking number that
nobody has checked is worse than no number at all.

When no base rate is supplied the result is marked uncalibrated and the
prior is stated explicitly, so a reader can see exactly what assumption the
figure rests on.

**Why likelihood ratios and not multipliers.** A multiplier of 2 or 5 has no
meaning. A likelihood ratio is a ratio of two probabilities that can be
measured, and it is the same quantity whether it came from a study or from a
hundred labels the analyst collected themselves.

**What moves a finding.** The margin past the threshold is the strongest
signal available and the one most tools discard: a finding at one and a half
times tolerance is not the same claim as one at five times. Corroboration by
an independent check raises it. The issue class matters: a governance gap is
a fact about records rather than about geometry, and treating it as a
geometric defect inflates the apparent error rate.

Nothing here consults a model. The same input gives the same number, and the
number can be traced back to the specific evidence that produced it.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

from geoqa.validations.base import ValidationIssue

__all__ = [
    "Evidence",
    "ConfidenceResult",
    "assess_finding",
    "assess_findings",
    "confidence_band",
    "calibration_report",
    "DEFAULT_BASE_RATES",
    "UNPRIORED",
]


#: The prior is the proportion of findings of that class that are genuine.
#: These are placeholders derived from ordinary surveying and GIS practice,
#: not measurements of anyone's data. Supply measured values before treating
#: any output as calibrated.
DEFAULT_BASE_RATES: dict[str, float] = {
    "geometry_topology": 0.75,
    "attribute_schema": 0.80,
    "metadata": 0.70,
    "coverage_clipping": 0.60,
    "sentinel_value": 0.85,
    "spatial_statistics": 0.45,
    "governance": 0.90,
}

#: Marker for a finding whose class has no base rate at all. These are reported
#: with their prior stated and nothing else, because inventing a base rate is
#: how a confidence number becomes decoration.
UNPRIORED = None


@dataclass(frozen=True)
class Evidence:
    """One observation, and how much it moves the odds."""

    name: str
    description: str
    likelihood_ratio: float
    detail: Any = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "likelihood_ratio": self.likelihood_ratio,
            "detail": self.detail,
        }


@dataclass
class ConfidenceResult:
    """A finding's reliability, with the reasoning attached."""

    problem_name: str
    feature_id: Any
    prior: float | None
    posterior: float
    calibrated: bool
    band: str
    evidence: list[Evidence] = field(default_factory=list)
    caveats: list[str] = field(default_factory=list)
    would_change_it: list[str] = field(default_factory=list)

    @property
    def is_genuine_likely(self) -> bool:
        """False means not established, so check the calibrated field."""
        return self.calibrated and self.posterior >= 0.5

    def to_dict(self) -> dict[str, Any]:
        return {
            "problem_name": self.problem_name,
            "feature_id": self.feature_id,
            "prior": self.prior,
            "posterior": self.posterior,
            "calibrated": self.calibrated,
            "band": self.band,
            "is_genuine_likely": self.is_genuine_likely,
            "evidence": [e.to_dict() for e in self.evidence],
            "caveats": list(self.caveats),
            "would_change_it": list(self.would_change_it),
        }


def confidence_band(posterior: float, *, calibrated: bool) -> str:
    """Name the band, so a number is not left to be interpreted by eye."""
    if not calibrated:
        return "uncalibrated"
    if posterior >= 0.90:
        return "near_certain"
    if posterior >= 0.70:
        return "probable"
    if posterior >= 0.45:
        return "uncertain"
    if posterior >= 0.20:
        return "weak"
    return "likely_false_positive"


# --------------------------------------------------------------------------
# Evidence extraction
# --------------------------------------------------------------------------

#: Fields that carry the measured margin, and the ratio they imply. The
#: breakpoints encode the plain fact that a finding barely past a threshold
#: is usually noise, while one far past it is not in doubt.
_MARGIN_RULES: tuple[tuple[str, float, float, float], ...] = (
    # (field, ratio_at_1x, ratio_at_2x, floor)
    ("distance", 0.45, 4.0, 1.0),
    ("ratio", 0.35, 5.0, 1.0),
    ("severity_delta", 0.5, 3.0, 1.0),
    ("area_relative", 0.5, 3.0, 1.0),
)


def _margin_evidence(issue: ValidationIssue) -> list[Evidence]:
    extra = issue.extra or {}
    found: list[Evidence] = []

    distance = extra.get("distance")
    tolerance = extra.get("tolerance")
    if isinstance(distance, (int, float)) and isinstance(tolerance, (int, float)) and tolerance > 0:
        ratio = float(distance) / float(tolerance)
        if ratio >= 1.0:
            # Log-linear between 1x and 2x, flattening after 3x.
            if ratio < 2.0:
                lr = 0.45 * (4.0 / 0.45) ** ((ratio - 1.0) / 1.0)
            else:
                lr = min(4.0 * math.log2(ratio), 40.0)
            found.append(Evidence(
                name="margin_past_tolerance",
                description=(
                    f"The measured value is {ratio:.2f} times the declared tolerance. "
                    + (
                        "A finding this far past the threshold is unlikely to be noise."
                        if ratio >= 2.0
                        else "A finding barely past the threshold is often digitising noise."
                    )
                ),
                likelihood_ratio=float(max(lr, 0.05)),
                detail={"ratio": ratio, "distance": distance, "tolerance": tolerance},
            ))
        else:
            found.append(Evidence(
                name="below_declared_tolerance",
                description=(
                    f"The measured value is {ratio:.2f} times the tolerance, so it does not "
                    "meet the declared threshold at all and should not be reported as a defect."
                ),
                likelihood_ratio=0.1,
                detail={"ratio": ratio},
            ))

    ratio_field = extra.get("ratio")
    if isinstance(ratio_field, (int, float)) and "distance" not in extra:
        if ratio_field < 1.0:
            found.append(Evidence(
                name="below_declared_floor",
                description=(
                    f"The retained fraction is {ratio_field:.1%}, below the declared floor. "
                    "This is the shape of a boundary that does not match the feature, "
                    "rather than a data error."
                ),
                likelihood_ratio=0.3,
                detail={"ratio": ratio_field},
            ))
        elif ratio_field >= 1.0:
            found.append(Evidence(
                name="above_declared_floor",
                description=f"Retained fraction is {ratio_field:.1%}, meeting the declared floor.",
                likelihood_ratio=1.5,
                detail={"ratio": ratio_field},
            ))

    deviation = extra.get("deviation_ratio")
    if isinstance(deviation, (int, float)):
        lr = 1.0 / max(float(deviation), 1e-9)
        found.append(Evidence(
            name="deviation_from_reference",
            description=(
                f"This feature deviates from its reference by a factor of {deviation:.2f}."
            ),
            likelihood_ratio=float(min(max(lr, 0.1), 10.0)),
            detail={"deviation_ratio": deviation},
        ))
    return found


def _class_evidence(issue: ValidationIssue) -> list[Evidence]:
    issue_class = getattr(issue, "issue_class", None) or "data_issue"
    if issue_class == "data_issue":
        return []
    if issue_class == "evidence_condition":
        return [Evidence(
            name="observation_not_defect",
            description=(
                "This is recorded as an observation rather than a defect. It describes "
                "what was measured and leaves the judgement to a person, so treating it "
                "as an error overstates the finding rate."
            ),
            likelihood_ratio=0.5,
        )]
    return [Evidence(
        name="records_about_records",
        description=(
            "This concerns what was written down rather than the geometry. It is almost "
            "always genuine and almost never a spatial error, so it should not be counted "
            "with geometry defects."
        ),
        likelihood_ratio=2.0,
    )]


def _corroboration_evidence(issue: ValidationIssue) -> list[Evidence]:
    extra = issue.extra or {}
    corroborating = extra.get("corroborating_conditions") or extra.get("corroborated_by")
    if not corroborating:
        return []
    names = [corroborating] if isinstance(corroborating, str) else list(corroborating)
    if len(names) < 2:
        return []
    # Corroboration compounds: each additional independent check raises the odds,
    # at a diminishing rate, because independent checks are rarely truly
    # independent once they share a geometry engine.
    lr = 1.0 + 0.6 * (len(names) - 1)
    return [Evidence(
        name="corroborated",
        description=(
            "Independent checks agree: "
            + ", ".join(str(n) for n in names)
            + ". Agreement raises confidence but does not prove it, because checks "
            "sharing a geometry engine are not fully independent."
        ),
        likelihood_ratio=float(lr),
        detail={"conditions": names},
    )]


# --------------------------------------------------------------------------
# Assessment
# --------------------------------------------------------------------------

#: Registry category to base-rate key. The category is read from the registry
#: rather than guessed from the condition name, so a condition that is not
#: registered has no category and therefore no prior, which is the intended
#: outcome rather than a gap in the mapping.
_CATEGORY_PRIORS: dict[str, str] = {
    "geometry": "geometry_topology",
    "topology": "geometry_topology",
    "accuracy": "geometry_topology",
    "spatial_logic": "geometry_topology",
    "integrity": "geometry_topology",
    "boundary": "coverage_clipping",
    "attributes": "attribute_schema",
    "schema": "attribute_schema",
    "metadata": "metadata",
    "crs": "metadata",
    "vertical": "metadata",
    "anomalies": "spatial_statistics",
    "runtime": "governance",
    "governance": "governance",
}


def _prior_key(problem_name: str) -> str | None:
    """Base-rate group for a condition, or None when it cannot be determined.

    Reading the registry rather than matching on the name means an
    unregistered condition produces no probability at all, instead of quietly
    inheriting a plausible-looking one.
    """
    try:
        from geoqa.problem_registry import get_problem_definition

        definition = get_problem_definition(problem_name)
    except Exception:
        return None
    if definition is None:
        return None
    category = str(getattr(definition, "category", "") or "")
    return _CATEGORY_PRIORS.get(category)


def assess_finding(
    issue: ValidationIssue,
    *,
    base_rates: Mapping[str, float] | None = None,
    prior: float | None = None,
) -> ConfidenceResult:
    """Assess one finding, returning the reasoning alongside the number."""
    caveats: list[str] = []
    would_change: list[str] = []

    if prior is not None:
        resolved_prior = float(prior)
        calibrated = True
        rate_source = "supplied for this finding"
    else:
        key = _prior_key(issue.problem_name)
        if key is not None and base_rates is not None and key in base_rates:
            resolved_prior = base_rates[key]
            calibrated = True
            rate_source = f"supplied base rate for {key}"
        else:
            resolved_prior = DEFAULT_BASE_RATES.get(key) if key else None
            calibrated = False
            rate_source = (
                f"default base rate for {key}" if resolved_prior is not None else "no base rate"
            )

    if resolved_prior is None:
        return ConfidenceResult(
            problem_name=issue.problem_name,
            feature_id=issue.feature_id,
            prior=None,
            posterior=float("nan"),
            calibrated=False,
            band="uncalibrated",
            evidence=[],
            caveats=[
                "No base rate is registered for this condition, so no probability is "
                "produced. Supply one from labelled outcomes rather than accepting a guess."
            ],
            would_change_it=[
                "Collect outcomes for a sample of findings of this condition and register "
                "the observed proportion that were genuine."
            ],
        )

    if 0.0 <= resolved_prior < 0.5:
        caveats.append(
            "The base rate for this condition is below one half, so most findings of "
            "this kind are not genuine even before any evidence is weighed."
        )
    if not calibrated or rate_source.startswith("default"):
        would_change.append(
            "Replace the default base rate with one measured from labelled outcomes; "
            "the figure is a placeholder until then."
        )

    evidence = _margin_evidence(issue) + _class_evidence(issue) + _corroboration_evidence(issue)

    prior_odds = resolved_prior / (1.0 - resolved_prior) if resolved_prior < 1.0 else float("inf")
    odds = prior_odds
    for item in evidence:
        odds *= item.likelihood_ratio

    if odds == float("inf"):
        posterior = 1.0
    elif odds <= 0:
        posterior = 0.0
    else:
        posterior = odds / (1.0 + odds)

    # A finding carrying its own geometry can be looked at. One without cannot,
    # and that is worth saying rather than leaving implied.
    if getattr(issue, "geometry", None) is None:
        would_change.append(
            "The finding carries no geometry, so nobody can inspect it on a map to "
            "decide. Findings with geometry should be confirmed visually."
        )

    return ConfidenceResult(
        problem_name=issue.problem_name,
        feature_id=issue.feature_id,
        prior=resolved_prior,
        posterior=float(posterior),
        calibrated=calibrated,
        band=confidence_band(float(posterior), calibrated=calibrated),
        evidence=evidence,
        caveats=caveats,
        would_change_it=would_change,
    )


def assess_findings(
    issues: Sequence[ValidationIssue],
    *,
    base_rates: Mapping[str, float] | None = None,
    limit: int | None = None,
) -> list[ConfidenceResult]:
    """Assess a batch, most credible first."""
    results = [assess_finding(issue, base_rates=base_rates) for issue in issues]
    results.sort(
        key=lambda r: (r.calibrated, r.posterior if r.posterior == r.posterior else -1.0),
        reverse=True,
    )
    return results[:limit] if limit else results


def calibration_report(
    results: Sequence[ConfidenceResult],
    outcomes: Mapping[tuple[str, Any], bool],
    *,
    bins: int = 5,
) -> dict[str, Any]:
    """Compare predicted confidence against observed outcomes.

    ``outcomes`` maps ``(problem_name, feature_id)`` to whether the finding
    turned out to be genuine. A confidence figure that has never been checked
    against outcomes is a claim, and this is what turns it into a measurement.

    The bins below one show predicted confidence that did not materialise,
    which is the failure mode that matters: a number that reads 0.8 and is
    right 40 percent of the time is worse than no number.
    """
    matched: list[tuple[float, bool]] = []
    unlabelled = 0
    for result in results:
        outcome = outcomes.get((result.problem_name, result.feature_id))
        if outcome is None:
            unlabelled += 1
            continue
        if not result.calibrated:
            continue
        matched.append((result.posterior, bool(outcome)))

    if not matched:
        return {
            "checked": 0,
            "unlabelled": unlabelled,
            "note": "No labelled outcomes were supplied, so nothing can be checked.",
        }

    predicted = sum(p for p, _ in matched) / len(matched)
    observed = sum(1 for _, o in matched if o) / len(matched)
    mean_error = sum(abs(p - (1.0 if o else 0.0)) for p, o in matched) / len(matched)

    edges = [i / bins for i in range(bins + 1)]
    buckets = []
    for low, high in zip(edges[:-1], edges[1:]):
        inside = [(p, o) for p, o in matched if low <= p < high or (high == 1.0 and p == 1.0)]
        buckets.append({
            "range": [round(low, 3), round(high, 3)],
            "count": len(inside),
            "mean_predicted": (sum(p for p, _ in inside) / len(inside)) if inside else None,
            "observed_rate": (sum(1 for _, o in inside if o) / len(inside)) if inside else None,
        })

    return {
        "checked": len(matched),
        "unlabelled": unlabelled,
        "mean_predicted": predicted,
        "observed_rate": observed,
        "mean_absolute_error": mean_error,
        "over_confident_by": predicted - observed,
        "bins": buckets,
    }