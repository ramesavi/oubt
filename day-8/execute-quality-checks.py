"""
Day 8: Execute Quality Checks (Simplified)

This script runs quality checks on enriched trip data using Great Expectations.
Results are written to S3 in Delta format for historical tracking.

Key Features:
- Uses Great Expectations with Spark in ephemeral mode
- Loads quality rules from YAML file
- Writes results to Delta format on S3
- Simple, beginner-friendly implementation (~100 lines)

Input: s3://day-6-datalake-nyc-data/silver/trips_enriched/ (Delta)
Rules: day-8/data-quality-rules-trips.yaml
Output: s3://day-6-datalake-nyc-data/quality_results/trips/ (Delta)

Usage:
    python execute-quality-checks.py              # Run against S3 data
    python execute-quality-checks.py --local      # Run against local sample data
"""

import os
import sys
from datetime import datetime, timezone

import yaml
from delta import configure_spark_with_delta_pip
from pyspark.sql import SparkSession
from pyspark.sql.types import (
    BooleanType,
    IntegerType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)

# ============================================
# CONFIGURATION
# ============================================
S3_BUCKET = "day-6-datalake-nyc-data"
INPUT_PATH = f"s3://{S3_BUCKET}/silver/trips_enriched/"
OUTPUT_PATH = f"s3://{S3_BUCKET}/quality_results/trips/"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
RULES_FILE = os.path.join(SCRIPT_DIR, "data-quality-rules-trips.yaml")


def create_spark_session() -> SparkSession:
    """Create Spark session with Delta Lake support."""
    builder = (
        SparkSession.builder.appName("QualityChecks")
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config(
            "spark.sql.catalog.spark_catalog",
            "org.apache.spark.sql.delta.catalog.DeltaCatalog",
        )
    )
    spark = configure_spark_with_delta_pip(builder).getOrCreate()
    spark.sparkContext.setLogLevel("WARN")
    return spark


def load_rules(rules_file: str) -> dict:
    """Load quality rules from YAML file."""
    print("\n=== Loading Quality Rules ===")
    print(f"File: {rules_file}")

    with open(rules_file) as f:
        rules = yaml.safe_load(f)

    print(f"Suite: {rules['expectation_suite_name']}")
    print(f"Rules: {len(rules['expectations'])}")
    return rules


def run_quality_checks(spark: SparkSession, df, rules: dict) -> list:
    """
    Run quality checks using Great Expectations with Spark.

    This function uses GE's ephemeral mode for simplicity - no persistent
    data context or checkpoints needed.
    """
    import great_expectations as gx
    from great_expectations.core import ExpectationConfiguration, ExpectationSuite

    print("\n=== Running Quality Checks ===")

    # Create ephemeral GE context (no persistent storage needed)
    context = gx.get_context(mode="ephemeral")

    # Build expectation suite from YAML rules
    suite = ExpectationSuite(expectation_suite_name=rules["expectation_suite_name"])

    for exp in rules["expectations"]:
        config = ExpectationConfiguration(
            expectation_type=exp["expectation_type"],
            kwargs=exp["kwargs"],
            meta=exp.get("meta", {}),
        )
        suite.add_expectation(config)

    context.suites.add(suite)

    # Create Spark datasource and run validation
    datasource = context.data_sources.add_or_update_spark(name="trips_ds")
    data_asset = datasource.add_dataframe_asset(name="trips_asset")
    batch_def = data_asset.add_batch_definition_whole_dataframe(name="trips_batch")

    validation_def = gx.ValidationDefinition(
        name="trips_validation",
        data=batch_def,
        suite=suite,
    )
    context.validation_definitions.add(validation_def)

    # Run validation
    result = validation_def.run(batch_parameters={"dataframe": df})

    # Extract results
    results = []
    record_count = df.count()

    for exp_result in result.to_json_dict()["results"]:
        exp_config = exp_result["expectation_config"]
        result_data = exp_result.get("result", {})
        meta = exp_config.get("meta", {})

        element_count = result_data.get("element_count", record_count)
        unexpected_count = result_data.get("unexpected_count", 0)

        results.append(
            {
                "check_time": datetime.now(timezone.utc),
                "expectation_type": exp_config["expectation_type"],
                "column": exp_config["kwargs"].get("column"),
                "success": exp_result["success"],
                "element_count": element_count,
                "unexpected_count": unexpected_count,
                "pass_rate": round(
                    (element_count - unexpected_count) / element_count * 100, 2
                )
                if element_count > 0
                else 0.0,
                "dimension": meta.get("dimension", "unknown"),
                "severity": meta.get("severity", "medium"),
                "business_rule": meta.get("business_rule", ""),
            }
        )

    return results


def results_to_dataframe(spark: SparkSession, results: list):
    """Convert results list to Spark DataFrame."""
    schema = StructType(
        [
            StructField("check_time", TimestampType(), False),
            StructField("expectation_type", StringType(), False),
            StructField("column", StringType(), True),
            StructField("success", BooleanType(), False),
            StructField("element_count", IntegerType(), False),
            StructField("unexpected_count", IntegerType(), False),
            StructField("pass_rate", StringType(), False),  # Store as string for Delta
            StructField("dimension", StringType(), True),
            StructField("severity", StringType(), True),
            StructField("business_rule", StringType(), True),
        ]
    )

    # Convert pass_rate to string for consistent Delta storage
    rows = []
    for r in results:
        rows.append(
            (
                r["check_time"],
                r["expectation_type"],
                r["column"],
                r["success"],
                r["element_count"],
                r["unexpected_count"],
                str(r["pass_rate"]),
                r["dimension"],
                r["severity"],
                r["business_rule"],
            )
        )

    return spark.createDataFrame(rows, schema)


def print_summary(results: list) -> None:
    """Print quality check summary to console."""
    print("\n" + "=" * 60)
    print("QUALITY CHECK SUMMARY")
    print("=" * 60)

    passed = sum(1 for r in results if r["success"])
    failed = len(results) - passed

    print(f"\nTotal Checks: {len(results)}")
    print(f"Passed: {passed} ✅")
    print(f"Failed: {failed} ❌")

    print("\n--- Check Details ---")
    for r in results:
        status = "✅" if r["success"] else "❌"
        print(f"{status} [{r['dimension']}] {r['column']}: {r['pass_rate']}% pass rate")
        if not r["success"]:
            print(f"   → {r['unexpected_count']:,} failing records")

    print("=" * 60)


def main():
    """Main execution function."""
    local_mode = "--local" in sys.argv

    print("\n" + "=" * 60)
    print("Day 8: Execute Quality Checks (Simplified)")
    print("=" * 60)
    print(f"Mode: {'Local' if local_mode else 'S3'}")
    print(f"Time: {datetime.now(timezone.utc).isoformat()}")

    # Initialize Spark
    spark = create_spark_session()

    try:
        # Load quality rules
        rules = load_rules(RULES_FILE)

        # Load enriched trip data
        print("\n=== Loading Trip Data ===")
        if local_mode:
            # For local testing, create sample data
            print("Creating sample data for local testing...")
            sample_data = [
                (
                    datetime(2025, 8, 15, 10, 0),
                    datetime(2025, 8, 15, 10, 30),
                    25.50,
                    30.0,
                    "Upper East Side",
                    "Midtown",
                ),
                (
                    datetime(2025, 8, 15, 11, 0),
                    datetime(2025, 8, 15, 11, 45),
                    35.00,
                    45.0,
                    "JFK Airport",
                    None,
                ),  # Orphan dropoff
                (
                    datetime(2025, 8, 15, 12, 0),
                    None,
                    15.00,
                    None,
                    "Times Square",
                    "Chelsea",
                ),  # Missing dropoff time
                (
                    datetime(2025, 8, 15, 13, 0),
                    datetime(2025, 8, 15, 13, 20),
                    -5.00,
                    20.0,
                    None,
                    "SoHo",
                ),  # Negative fare, orphan pickup
            ]
            df = spark.createDataFrame(
                sample_data,
                [
                    "tpep_pickup_datetime",
                    "tpep_dropoff_datetime",
                    "fare_amount",
                    "trip_duration_minutes",
                    "pickup_zone_name",
                    "dropoff_zone_name",
                ],
            )
        else:
            print(f"Path: {INPUT_PATH}")
            df = spark.read.format("delta").load(INPUT_PATH)

        record_count = df.count()
        print(f"Records: {record_count:,}")

        # Run quality checks
        results = run_quality_checks(spark, df, rules)

        # Print summary
        print_summary(results)

        # Write results to Delta
        if not local_mode:
            print("\n=== Writing Results to Delta ===")
            print(f"Path: {OUTPUT_PATH}")
            results_df = results_to_dataframe(spark, results)
            results_df.write.format("delta").mode("append").save(OUTPUT_PATH)
            print("Results written successfully!")
        else:
            print("\n[Local mode: Skipping S3 write]")

        print("\nQuality checks completed!")

    except Exception as e:
        print(f"\nError: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
