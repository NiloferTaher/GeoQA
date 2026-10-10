from __future__ import annotations

import geoqa


def main() -> None:
    dataset = "data/public_samples/edge_cases/duplicate_vertex_line.geojson"

    report = geoqa.validate(dataset, profile="generic_quick")

    print("Before")
    print(report.summary)
    print(f"Score: {report.score(method='conservative')}")
    print()

    cleaned = report.clean()
    output_path = cleaned.export("data/integration_results/duplicate_vertex_line_cleaned.geojson")

    print("After")
    print(f"Cleaned dataset written to: {output_path}")
    print("This example shows the GeoQA workflow: validate -> inspect -> clean -> export.")


if __name__ == "__main__":
    main()
