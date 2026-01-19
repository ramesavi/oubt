import sys
from unittest.mock import MagicMock

import pytest
from pyspark.sql import SparkSession
from pyspark.sql.types import (
    BooleanType,
    DateType,
    LongType,
    StringType,
    StructField,
    StructType,
)

# Mock AWS Glue modules before importing vendor_silver_master
sys.modules["awsglue"] = MagicMock()
sys.modules["awsglue.utils"] = MagicMock()
sys.modules["glue_utils"] = MagicMock()


@pytest.fixture(scope="session")
def spark():
    """Create a local Spark session for testing."""
    return (
        SparkSession.builder.master("local[*]")
        .appName("test-vendor-master")
        .config("spark.sql.shuffle.partitions", "1")
        .config("spark.ui.enabled", "false")
        .config("spark.sql.execution.arrow.pyspark.enabled", "true")
        .getOrCreate()
    )


@pytest.fixture
def sample_silver_day1(spark):
    """Day 1 silver data (2026-01-18)."""
    data = [
        (1, "Creative Mobile Technologies, LLC", "creative mobile technologies", "2026-01-18"),
        (2, "Curb Mobility, LLC", "curb mobility", "2026-01-18"),
        (6, "Myle Technologies Inc", "myle technologies", "2026-01-18"),
        (7, "Helix", "helix", "2026-01-18"),
    ]
    return spark.createDataFrame(
        data, ["vendor_id", "vendor_name", "normalized_name", "ingestion_date"]
    )


@pytest.fixture
def sample_silver_day2(spark):
    """Day 2 silver data (2026-01-19)."""
    data = [
        (7, "Helix Technologies", "helix technologies", "2026-01-19"),
        (8, "Creative Mobil", "creative mobil", "2026-01-19"),
        (10, "Savitha Technologies", "savitha technologies", "2026-01-19"),
    ]
    return spark.createDataFrame(
        data, ["vendor_id", "vendor_name", "normalized_name", "ingestion_date"]
    )


@pytest.fixture
def existing_dim_day1(spark):
    """Simulated dim_vendor after Day 1 processing."""
    from datetime import date

    schema = StructType(
        [
            StructField("vendor_gk", LongType(), False),
            StructField("canonical_name", StringType(), True),
            StructField("valid_from", DateType(), True),
            StructField("valid_to", DateType(), True),
            StructField("is_current", BooleanType(), True),
            StructField("change_reason", StringType(), True),
            StructField("record_hash", StringType(), True),
        ]
    )
    data = [
        (1, "Creative Mobile Technologies, LLC", date(2026, 1, 18), None, True, "NEW", "hash1"),
        (2, "Curb Mobility, LLC", date(2026, 1, 18), None, True, "NEW", "hash2"),
        (6, "Myle Technologies Inc", date(2026, 1, 18), None, True, "NEW", "hash6"),
        (7, "Helix", date(2026, 1, 18), None, True, "NEW", "hash7"),
    ]
    return spark.createDataFrame(data, schema)


@pytest.fixture
def existing_current_day1(spark):
    """Existing current masters for Day 2 matching."""
    data = [
        (1, "Creative Mobile Technologies, LLC", "creative mobile technologies"),
        (2, "Curb Mobility, LLC", "curb mobility"),
        (6, "Myle Technologies Inc", "myle technologies"),
        (7, "Helix", "helix"),
    ]
    return spark.createDataFrame(
        data, ["vendor_gk", "canonical_name", "normalized_name"]
    )
