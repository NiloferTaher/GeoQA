from __future__ import annotations

import geoqa


def main() -> None:
    sample = "data/public_samples/edge_cases/duplicate_vertex_line.geojson"

    report = geoqa.validate(sample)
    print(report.summary)
    print(report.score())
    print(report.to_ml())

    quality_score = geoqa.score(sample)
    print(quality_score)

    crs_issues = geoqa.expect.valid_crs(sample, expected_crs="EPSG:3857")
    print(crs_issues)

    print(geoqa.expect.geometry.valid(sample))


if __name__ == "__main__":
    main()
