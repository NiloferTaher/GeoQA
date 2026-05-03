from __future__ import annotations

import geoqa


def main() -> None:
    dataset = "data/public_samples/edge_cases/duplicate_vertex_line.geojson"

    report = geoqa.validate(dataset, profile="generic_quick")

    print("Summary")
    print(report.summary)
    print()

    print("Score")
    print(report.score(method="ml_ready"))
    print()

    print("ML rows")
    print(report.to_ml())
    print()

    if report.score() < 0.8:
        fixed = report.fix()
        print(fixed)


if __name__ == "__main__":
    main()
