"""
Day 8 Task 8.2: ETL Job - CSV to Delta with Quality Gates

This script implements a Glue ETL job that:
1. Reads taxi_zone_lookup.csv from the bronze zone
2. Applies quality checks (completeness, validity, uniqueness)
3. Routes data based on quality gate results:
   - Pass: Write to silver zone as Delta format
   - Fail: Send quality alert (no quarantine write)

Pipeline Flow:
    Read CSV from Bronze → Apply Quality Checks → Quality Score >= Threshold?
      → Yes: Write to Silver (Delta)
      → No: Send Alert

Input: s3://day-6-datalake-nyc-data/bronze/taxi_zones/
Silver Output: s3://day-6-datalake-nyc-data/silver/zones_validated/
"""

import sys
from dataclasses import dataclass
from datetime import datetime

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql.functions import col, current_timestamp, lit


# ============================================
# CONFIGURATION
# ============================================
@dataclass
class Config:
    """ETL job configuration."""

    S3_BUCKET: str = "day-6-datalake-nyc-data"
    BRONZE_PATH: str = "s3://day-6-datalake-nyc-data/bronze/taxi_zones/"
    SILVER_PATH: str = "s3://day-6-datalake-nyc-data/silver/zones_validated/"

    # Quality thresholds
    COMPLETENESS_THRESHOLD: float = 0.99
    VALIDITY_THRESHOLD: float = 0.99
    UNIQUENESS_THRESHOLD: float = 1.0

    # Valid values for validation
    VALID_BOROUGHS: tuple = (
        "Manhattan",
        "Brooklyn",
        "Queens",
        "Bronx",
        "Staten Island",
        "EWR",
    )
    VALID_SERVICE_ZONES: tuple = ("Yellow Zone", "Boro Zone", "Airports", "EWR", "N/A")
    MIN_LOCATION_ID: int = 1
    MAX_LOCATION_ID: int = 265

    # Required columns for completeness check
    REQUIRED_COLUMNS: tuple = ("LocationID", "Borough", "Zone")
    PRIMARY_KEY: str = "LocationID"


CONFIG = Config()


# ============================================
# SPARK SESSION
# ============================================
def create_spark_session() -> SparkSession:
    """Create Spark session with Delta Lake support."""
    return (
        SparkSession.builder.appName("GlueETL-CSVtoDelta-QualityGates")
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config(
            "spark.sql.catalog.spark_catalog",
            "org.apache.spark.sql.delta.catalog.DeltaCatalog",
        )
        .config("spark.sql.adaptive.enabled", "true")
        .getOrCreate()
    )


# ============================================
# DATA READING
# ============================================
def read_csv(spark: SparkSession, path: str) -> DataFrame:
    """Read CSV data from bronze zone."""
    print(f"\n=== Reading CSV from: {path} ===")
    df = spark.read.option("header", "true").option("inferSchema", "true").csv(path)
    print(f"Records: {df.count():,} | Columns: {df.columns}")
    return df


# ============================================
# QUALITY CHECKS
# ============================================
@dataclass
class QualityResult:
    """Quality check result."""

    score: float
    passed: bool
    details: dict


def check_completeness(df: DataFrame, columns: tuple) -> QualityResult:
    """Check completeness (non-null ratio) for specified columns."""
    print("\n=== Completeness Check ===")
    total = df.count()
    scores = {}

    for col_name in columns:
        non_null = df.filter(col(col_name).isNotNull()).count()
        scores[col_name] = non_null / total if total > 0 else 0
        print(f"  {col_name}: {scores[col_name]:.2%}")

    overall = sum(scores.values()) / len(scores) if scores else 0
    passed = overall >= CONFIG.COMPLETENESS_THRESHOLD
    print(f"  Overall: {overall:.2%} {'✅' if passed else '❌'}")

    return QualityResult(score=overall, passed=passed, details=scores)


def check_validity(df: DataFrame) -> QualityResult:
    """Check validity based on business rules."""
    print("\n=== Validity Check ===")
    total = df.count()
    scores = {}

    # LocationID range check
    valid_loc = df.filter(
        (col("LocationID") >= CONFIG.MIN_LOCATION_ID)
        & (col("LocationID") <= CONFIG.MAX_LOCATION_ID)
    ).count()
    scores["LocationID_range"] = valid_loc / total if total > 0 else 0
    print(f"  LocationID (1-265): {scores['LocationID_range']:.2%}")

    # Borough validity check
    valid_borough = df.filter(col("Borough").isin(CONFIG.VALID_BOROUGHS)).count()
    scores["Borough_valid"] = valid_borough / total if total > 0 else 0
    print(f"  Borough valid: {scores['Borough_valid']:.2%}")

    # Service zone check (if column exists)
    if "service_zone" in df.columns:
        valid_zone = df.filter(
            col("service_zone").isin(CONFIG.VALID_SERVICE_ZONES)
        ).count()
        scores["service_zone_valid"] = valid_zone / total if total > 0 else 0
        print(f"  service_zone valid: {scores['service_zone_valid']:.2%}")

    overall = sum(scores.values()) / len(scores) if scores else 0
    passed = overall >= CONFIG.VALIDITY_THRESHOLD
    print(f"  Overall: {overall:.2%} {'✅' if passed else '❌'}")

    return QualityResult(score=overall, passed=passed, details=scores)


def check_uniqueness(df: DataFrame, key_column: str) -> QualityResult:
    """Check uniqueness of primary key column."""
    print("\n=== Uniqueness Check ===")
    total = df.count()
    distinct = df.select(key_column).distinct().count()
    score = distinct / total if total > 0 else 0
    duplicates = total - distinct

    passed = score >= CONFIG.UNIQUENESS_THRESHOLD
    print(
        f"  {key_column}: {score:.2%} (duplicates: {duplicates}) {'✅' if passed else '❌'}"
    )

    return QualityResult(
        score=score,
        passed=passed,
        details={"distinct": distinct, "total": total, "duplicates": duplicates},
    )


def run_quality_checks(df: DataFrame) -> tuple[bool, dict]:
    """Run all quality checks and return overall result."""
    completeness = check_completeness(df, CONFIG.REQUIRED_COLUMNS)
    validity = check_validity(df)
    uniqueness = check_uniqueness(df, CONFIG.PRIMARY_KEY)

    overall_passed = completeness.passed and validity.passed and uniqueness.passed

    report = {
        "execution_time": datetime.utcnow().isoformat(),
        "record_count": df.count(),
        "scores": {
            "completeness": completeness.score,
            "validity": validity.score,
            "uniqueness": uniqueness.score,
        },
        "thresholds": {
            "completeness": CONFIG.COMPLETENESS_THRESHOLD,
            "validity": CONFIG.VALIDITY_THRESHOLD,
            "uniqueness": CONFIG.UNIQUENESS_THRESHOLD,
        },
        "passed": {
            "completeness": completeness.passed,
            "validity": validity.passed,
            "uniqueness": uniqueness.passed,
        },
        "overall_passed": overall_passed,
        "details": {
            "completeness": completeness.details,
            "validity": validity.details,
            "uniqueness": uniqueness.details,
        },
    }

    print(f"\n=== Quality Gate: {'✅ PASSED' if overall_passed else '❌ FAILED'} ===")
    return overall_passed, report


# ============================================
# DATA WRITING
# ============================================
def write_to_delta(df: DataFrame, path: str) -> int:
    """Write data to silver zone as Delta format."""
    print(f"\n=== Writing Delta to: {path} ===")

    df_with_metadata = df.withColumn(
        "quality_validated_at", current_timestamp()
    ).withColumn("quality_status", lit("PASSED"))

    df_with_metadata.write.format("delta").mode("overwrite").save(path)
    count = df_with_metadata.count()
    print(f"Records written: {count:,}")
    return count


# ============================================
# ALERTING
# ============================================
def send_quality_alert(report: dict) -> None:
    """Send quality failure alert (logs to console, would send SNS in production)."""
    print("\n" + "=" * 60)
    print("🚨 QUALITY GATE ALERT 🚨")
    print("=" * 60)
    print(f"Time: {report['execution_time']}")
    print(f"Records: {report['record_count']:,}")
    print("\nScores vs Thresholds:")
    for dim in ["completeness", "validity", "uniqueness"]:
        score = report["scores"][dim]
        threshold = report["thresholds"][dim]
        status = "✅" if report["passed"][dim] else "❌"
        print(
            f"  {dim.capitalize():12}: {score:.2%} (threshold: {threshold:.0%}) {status}"
        )

    print("\nFailed Checks:")
    for dim in ["completeness", "validity", "uniqueness"]:
        if not report["passed"][dim]:
            print(f"  - {dim.capitalize()}: {report['details'][dim]}")

    print("\nAction Required:")
    print("  - Review source data quality issues")
    print("  - Data NOT written to silver zone")
    print("=" * 60)

    # In production: boto3.client('sns').publish(...)


# ============================================
# SUMMARY
# ============================================
def print_summary(
    report: dict, output_path: str | None = None, output_count: int = 0
) -> None:
    """Print ETL job summary."""
    print("\n" + "=" * 60)
    print("ETL JOB SUMMARY")
    print("=" * 60)
    print(f"Source: {CONFIG.BRONZE_PATH}")
    print(f"Records Read: {report['record_count']:,}")
    print(f"\nQuality Gate: {'✅ PASSED' if report['overall_passed'] else '❌ FAILED'}")
    for dim in ["completeness", "validity", "uniqueness"]:
        print(f"  {dim.capitalize():12}: {report['scores'][dim]:.2%}")

    if output_path:
        print(f"\nOutput: {output_path}")
        print(f"Records Written: {output_count:,}")
        print("Format: Delta")
    else:
        print("\nOutput: None (quality gate failed)")
    print("=" * 60)


# ============================================
# MAIN
# ============================================
def main():
    """Main ETL execution."""
    print("\n" + "=" * 60)
    print("ETL Job: CSV to Delta with Quality Gates")
    print("=" * 60)

    spark = create_spark_session()

    try:
        # Read source data
        df = read_csv(spark, CONFIG.BRONZE_PATH)

        # Run quality checks
        quality_passed, report = run_quality_checks(df)

        # Route based on quality gate
        if quality_passed:
            output_count = write_to_delta(df, CONFIG.SILVER_PATH)
            print_summary(report, CONFIG.SILVER_PATH, output_count)
            print("\n✅ ETL completed successfully!")
        else:
            send_quality_alert(report)
            print_summary(report)
            print("\n❌ ETL completed with quality issues - no data written")
            # Optionally fail the job: sys.exit(1)

    except Exception as e:
        print(f"\n❌ ETL failed: {e}")
        sys.exit(1)
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
