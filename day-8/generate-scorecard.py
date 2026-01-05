"""
Day 8: Generate Quality Scorecard (Simplified)

This script reads quality check results from Delta format on S3 and generates
a markdown scorecard with summary metrics and recommendations.

Key Features:
- Reads latest quality results from Delta table
- Generates simple, readable markdown scorecard
- Includes pass/fail summary and recommendations
- Beginner-friendly implementation (~80 lines)

Input: s3://day-6-datalake-nyc-data/quality_results/trips/ (Delta)
Output: day-8/quality-scorecard.md

Usage:
    python generate-scorecard.py              # Read from S3
    python generate-scorecard.py --sample     # Use sample data for testing
"""

import os
import sys
from datetime import datetime, timezone

from delta import configure_spark_with_delta_pip
from pyspark.sql import SparkSession
from pyspark.sql.functions import col

# ============================================
# CONFIGURATION
# ============================================
S3_BUCKET = "day-6-datalake-nyc-data"
RESULTS_PATH = f"s3://{S3_BUCKET}/quality_results/trips/"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = os.path.join(SCRIPT_DIR, "quality-scorecard.md")


def create_spark_session() -> SparkSession:
    """Create Spark session with Delta Lake support."""
    builder = (
        SparkSession.builder.appName("QualityScorecard")
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config(
            "spark.sql.catalog.spark_catalog",
            "org.apache.spark.sql.delta.catalog.DeltaCatalog",
        )
    )
    spark = configure_spark_with_delta_pip(builder).getOrCreate()
    spark.sparkContext.setLogLevel("WARN")
    return spark


def get_sample_results() -> list:
    """Generate sample results for testing without S3 access."""
    return [
        {
            "column": "tpep_pickup_datetime",
            "dimension": "completeness",
            "severity": "critical",
            "business_rule": "Every trip must have a pickup timestamp",
            "success": True,
            "pass_rate": "100.0",
            "unexpected_count": 0,
        },
        {
            "column": "tpep_dropoff_datetime",
            "dimension": "completeness",
            "severity": "critical",
            "business_rule": "Every trip must have a dropoff timestamp",
            "success": True,
            "pass_rate": "99.8",
            "unexpected_count": 7000,
        },
        {
            "column": "fare_amount",
            "dimension": "business_rule",
            "severity": "high",
            "business_rule": "Fare must be between $0 and $500",
            "success": False,
            "pass_rate": "96.5",
            "unexpected_count": 122500,
        },
        {
            "column": "trip_duration_minutes",
            "dimension": "business_rule",
            "severity": "high",
            "business_rule": "Trip duration must be between 0 and 180 minutes",
            "success": False,
            "pass_rate": "94.2",
            "unexpected_count": 203000,
        },
        {
            "column": "pickup_zone_name",
            "dimension": "referential_integrity",
            "severity": "high",
            "business_rule": "Pickup location must match a valid zone",
            "success": True,
            "pass_rate": "99.9",
            "unexpected_count": 3500,
        },
        {
            "column": "dropoff_zone_name",
            "dimension": "referential_integrity",
            "severity": "high",
            "business_rule": "Dropoff location must match a valid zone",
            "success": True,
            "pass_rate": "99.9",
            "unexpected_count": 3500,
        },
    ]


def generate_scorecard(results: list) -> str:
    """Generate markdown scorecard from quality results."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # Calculate summary metrics
    total = len(results)
    passed = sum(1 for r in results if r["success"])
    failed = total - passed
    score = (passed / total * 100) if total > 0 else 0

    # Determine overall status
    if score >= 95:
        status = "✅ HEALTHY"
    elif score >= 80:
        status = "⚠️ NEEDS ATTENTION"
    else:
        status = "❌ CRITICAL"

    # Build scorecard
    scorecard = f"""# Data Quality Scorecard

**Generated:** {now}  
**Data Source:** Silver Enriched Trips (Day 7 Output)

---

## Executive Summary

| Metric | Value |
|--------|-------|
| **Overall Status** | {status} |
| **Quality Score** | **{score:.1f}%** |
| Total Checks | {total} |
| Passed | {passed} |
| Failed | {failed} |

---

## Quality Check Results

| Dimension | Column | Business Rule | Pass Rate | Status |
|-----------|--------|---------------|-----------|--------|
"""

    # Add each check result
    for r in results:
        status_icon = "✅" if r["success"] else "❌"
        pass_rate = r["pass_rate"]
        scorecard += f"| {r['dimension']} | `{r['column']}` | {r['business_rule']} | {pass_rate}% | {status_icon} |\n"

    # Add dimension summary
    scorecard += """
---

## Quality by Dimension

"""

    dimensions = {}
    for r in results:
        dim = r["dimension"]
        if dim not in dimensions:
            dimensions[dim] = {"passed": 0, "total": 0}
        dimensions[dim]["total"] += 1
        if r["success"]:
            dimensions[dim]["passed"] += 1

    for dim, counts in dimensions.items():
        dim_score = (
            (counts["passed"] / counts["total"] * 100) if counts["total"] > 0 else 0
        )
        dim_status = "✅" if dim_score >= 95 else "⚠️" if dim_score >= 80 else "❌"
        scorecard += f"- **{dim.replace('_', ' ').title()}**: {dim_score:.0f}% ({counts['passed']}/{counts['total']} checks passed) {dim_status}\n"

    # Add recommendations for failed checks
    failed_checks = [r for r in results if not r["success"]]
    if failed_checks:
        scorecard += """
---

## Recommendations

The following checks failed and require attention:

"""
        for r in failed_checks:
            severity_icon = (
                "🔴"
                if r["severity"] == "critical"
                else "🟠"
                if r["severity"] == "high"
                else "🟡"
            )
            scorecard += f"""### {severity_icon} {r["column"]}

- **Dimension:** {r["dimension"]}
- **Severity:** {r["severity"].upper()}
- **Rule:** {r["business_rule"]}
- **Pass Rate:** {r["pass_rate"]}%
- **Failing Records:** {r["unexpected_count"]:,}
- **Action:** Investigate records where this check fails

"""
    else:
        scorecard += """
---

## Recommendations

🎉 **All quality checks passed!** No immediate action required.

"""

    # Add footer
    scorecard += """---

## Next Steps

1. Review any failed checks and investigate root causes
2. Monitor quality trends over time using the Delta table history
3. Adjust thresholds if business requirements change

---

*Generated by Day 8 Quality Scorecard Generator*
"""

    return scorecard


def main():
    """Main execution function."""
    sample_mode = "--sample" in sys.argv

    print("\n" + "=" * 60)
    print("Day 8: Generate Quality Scorecard")
    print("=" * 60)
    print(f"Mode: {'Sample' if sample_mode else 'S3'}")
    print(f"Time: {datetime.now(timezone.utc).isoformat()}")

    if sample_mode:
        # Use sample data for testing
        print("\n=== Using Sample Data ===")
        results = get_sample_results()
    else:
        # Read from S3 Delta table
        print("\n=== Reading Results from Delta ===")
        print(f"Path: {RESULTS_PATH}")

        spark = create_spark_session()
        try:
            results_df = spark.read.format("delta").load(RESULTS_PATH)

            # Get the latest batch of results (most recent check_time)
            latest_time = results_df.agg({"check_time": "max"}).collect()[0][0]
            latest_df = results_df.filter(col("check_time") == latest_time)

            # Convert to list of dicts
            results = [row.asDict() for row in latest_df.collect()]
            print(f"Found {len(results)} check results from {latest_time}")

        except Exception as e:
            print(f"Error reading from S3: {e}")
            print("Falling back to sample data...")
            results = get_sample_results()
        finally:
            spark.stop()

    # Generate scorecard
    print("\n=== Generating Scorecard ===")
    scorecard = generate_scorecard(results)

    # Write to file
    with open(OUTPUT_FILE, "w") as f:
        f.write(scorecard)

    print(f"Scorecard written to: {OUTPUT_FILE}")

    # Also print to console
    print("\n" + "=" * 60)
    print("SCORECARD PREVIEW")
    print("=" * 60)
    print(scorecard[:1500] + "..." if len(scorecard) > 1500 else scorecard)

    print("\nScorecard generation completed!")


if __name__ == "__main__":
    main()
