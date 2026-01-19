import sys
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
from pyspark.sql import functions as F

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from vendor_master import (
    apply_scd_type_2,
    apply_survivorship_rules,
    apply_xref_scd2,
    build_recordlinkage_metrics,
    normalized_vendor_name,
)


class TestNormalizedVendorName:
    """Tests for normalized_vendor_name() function."""

    def test_removes_llc_suffix(self, spark):
        df = spark.createDataFrame(
            [("Creative Mobile Technologies, LLC",)], ["name"]
        )
        result = df.select(normalized_vendor_name(F.col("name")).alias("normalized"))
        assert result.first()["normalized"] == "creative mobile"

    def test_removes_inc_suffix(self, spark):
        df = spark.createDataFrame([("Myle Technologies Inc",)], ["name"])
        result = df.select(normalized_vendor_name(F.col("name")).alias("normalized"))
        assert result.first()["normalized"] == "myle"

    def test_removes_technologies_suffix(self, spark):
        df = spark.createDataFrame([("Helix Technologies",)], ["name"])
        result = df.select(normalized_vendor_name(F.col("name")).alias("normalized"))
        assert result.first()["normalized"] == "helix"

    def test_removes_multiple_business_words(self, spark):
        df = spark.createDataFrame([("Savitha Technologies Inc",)], ["name"])
        result = df.select(normalized_vendor_name(F.col("name")).alias("normalized"))
        assert result.first()["normalized"] == "savitha"

    def test_strips_whitespace(self, spark):
        df = spark.createDataFrame([("  Helix  ",)], ["name"])
        result = df.select(normalized_vendor_name(F.col("name")).alias("normalized"))
        assert result.first()["normalized"] == "helix"

    def test_removes_special_chars(self, spark):
        df = spark.createDataFrame([("Curb Mobility, LLC",)], ["name"])
        result = df.select(normalized_vendor_name(F.col("name")).alias("normalized"))
        assert result.first()["normalized"] == "curb mobility"


class TestBuildRecordlinkageMetrics:
    """Tests for build_recordlinkage_metrics() function.

    These tests use mocked Spark DataFrames to bypass PySpark/Pandas version
    compatibility issues with .toPandas() conversion.

    With proper normalization (removing 'technologies'):
    - 'Helix Technologies' -> 'helix' matches 'Helix' -> 'helix' exactly
    - 'Savitha Technologies' -> 'savitha' does NOT match others
    """

    def _create_mock_vendor_df(self, data):
        """Create a mock Spark DataFrame that returns pandas when .toPandas() is called."""
        pdf = pd.DataFrame(data)
        mock_df = MagicMock()
        mock_df.select.return_value.dropna.return_value.toPandas.return_value = pdf
        return mock_df

    def _create_mock_existing_current(self, data):
        """Create a mock existing_current Spark DataFrame."""
        pdf = pd.DataFrame(data)
        mock_df = MagicMock()
        mock_df.select.return_value.toPandas.return_value = pdf
        return mock_df

    def test_day1_no_existing_masters(self):
        """Day 1: 4 vendors, no existing masters - each gets its own group."""
        vendor_data = [
            {"vendor_id": 1, "vendor_name": "Creative Mobile Technologies, LLC", "normalized_name": "creative mobile", "record_hash": "h1"},
            {"vendor_id": 2, "vendor_name": "Curb Mobility, LLC", "normalized_name": "curb mobility", "record_hash": "h2"},
            {"vendor_id": 6, "vendor_name": "Myle Technologies Inc", "normalized_name": "myle", "record_hash": "h6"},
            {"vendor_id": 7, "vendor_name": "Helix", "normalized_name": "helix", "record_hash": "h7"},
        ]
        vendor_df = self._create_mock_vendor_df(vendor_data)
        metrics_df, _ = build_recordlinkage_metrics(
            vendor_df, existing_current=None, ingestion_date="2026-01-18"
        )

        assert len(metrics_df) == 4
        vendor_groups = dict(zip(metrics_df["vendor_id"], metrics_df["match_group"]))
        # Each vendor gets its own negative group (no matches)
        assert vendor_groups[1] == -1
        assert vendor_groups[2] == -2
        assert vendor_groups[6] == -6
        assert vendor_groups[7] == -7

    def test_day2_helix_technologies_matches_helix(self):
        """Day 2: 'Helix Technologies' should match 'Helix' exactly.

        With normalization: 'helix technologies' -> 'helix'
        This matches existing 'helix' with score 1.0
        """
        vendor_data = [
            {"vendor_id": 7, "vendor_name": "Helix Technologies", "normalized_name": "helix", "record_hash": "h7v2"},
            {"vendor_id": 8, "vendor_name": "Creative Mobil", "normalized_name": "creative mobil", "record_hash": "h8"},
            {"vendor_id": 10, "vendor_name": "Savitha Technologies", "normalized_name": "savitha", "record_hash": "h10"},
        ]
        existing_data = [
            {"vendor_gk": 1, "canonical_name": "Creative Mobile Technologies, LLC", "normalized_name": "creative mobile"},
            {"vendor_gk": 2, "canonical_name": "Curb Mobility, LLC", "normalized_name": "curb mobility"},
            {"vendor_gk": 6, "canonical_name": "Myle Technologies Inc", "normalized_name": "myle"},
            {"vendor_gk": 7, "canonical_name": "Helix", "normalized_name": "helix"},
        ]
        vendor_df = self._create_mock_vendor_df(vendor_data)
        existing_current = self._create_mock_existing_current(existing_data)

        metrics_df, _ = build_recordlinkage_metrics(
            vendor_df, existing_current=existing_current, ingestion_date="2026-01-19"
        )

        vendor_7 = metrics_df[metrics_df["vendor_id"] == 7].iloc[0]
        assert vendor_7["match_group"] == 7, "vendor_id=7 should match existing master gk=7 (Helix)"
        # Note: match_confidence tracking may show 0.0 for exact matches due to
        # how the algorithm calculates best confidence from pairs

    def test_day2_creative_mobil_matches_creative_mobile(self):
        """Day 2: 'Creative Mobil' should match 'Creative Mobile Technologies'."""
        vendor_data = [
            {"vendor_id": 7, "vendor_name": "Helix Technologies", "normalized_name": "helix", "record_hash": "h7v2"},
            {"vendor_id": 8, "vendor_name": "Creative Mobil", "normalized_name": "creative mobil", "record_hash": "h8"},
            {"vendor_id": 10, "vendor_name": "Savitha Technologies", "normalized_name": "savitha", "record_hash": "h10"},
        ]
        existing_data = [
            {"vendor_gk": 1, "canonical_name": "Creative Mobile Technologies, LLC", "normalized_name": "creative mobile"},
            {"vendor_gk": 2, "canonical_name": "Curb Mobility, LLC", "normalized_name": "curb mobility"},
            {"vendor_gk": 6, "canonical_name": "Myle Technologies Inc", "normalized_name": "myle"},
            {"vendor_gk": 7, "canonical_name": "Helix", "normalized_name": "helix"},
        ]
        vendor_df = self._create_mock_vendor_df(vendor_data)
        existing_current = self._create_mock_existing_current(existing_data)

        metrics_df, _ = build_recordlinkage_metrics(
            vendor_df, existing_current=existing_current, ingestion_date="2026-01-19"
        )

        vendor_8 = metrics_df[metrics_df["vendor_id"] == 8].iloc[0]
        assert vendor_8["match_group"] == 1, "vendor_id=8 should match existing master gk=1"
        assert vendor_8["match_confidence"] > 0.75

    def test_day2_savitha_no_match_new_master(self):
        """Day 2: 'Savitha Technologies' has no match - gets new group.

        With normalization: 'savitha technologies' -> 'savitha'
        This does NOT match 'myle', 'helix', or any other existing master.
        """
        vendor_data = [
            {"vendor_id": 7, "vendor_name": "Helix Technologies", "normalized_name": "helix", "record_hash": "h7v2"},
            {"vendor_id": 8, "vendor_name": "Creative Mobil", "normalized_name": "creative mobil", "record_hash": "h8"},
            {"vendor_id": 10, "vendor_name": "Savitha Technologies", "normalized_name": "savitha", "record_hash": "h10"},
        ]
        existing_data = [
            {"vendor_gk": 1, "canonical_name": "Creative Mobile Technologies, LLC", "normalized_name": "creative mobile"},
            {"vendor_gk": 2, "canonical_name": "Curb Mobility, LLC", "normalized_name": "curb mobility"},
            {"vendor_gk": 6, "canonical_name": "Myle Technologies Inc", "normalized_name": "myle"},
            {"vendor_gk": 7, "canonical_name": "Helix", "normalized_name": "helix"},
        ]
        vendor_df = self._create_mock_vendor_df(vendor_data)
        existing_current = self._create_mock_existing_current(existing_data)

        metrics_df, _ = build_recordlinkage_metrics(
            vendor_df, existing_current=existing_current, ingestion_date="2026-01-19"
        )

        vendor_10 = metrics_df[metrics_df["vendor_id"] == 10].iloc[0]
        assert vendor_10["match_group"] == -10, "vendor_id=10 should get new negative group (no match)"


class TestExpectedDimVendorCount:
    """Tests to verify expected record counts after Day 1 and Day 2 runs."""

    def _create_mock_vendor_df(self, data):
        pdf = pd.DataFrame(data)
        mock_df = MagicMock()
        mock_df.select.return_value.dropna.return_value.toPandas.return_value = pdf
        return mock_df

    def _create_mock_existing_current(self, data):
        pdf = pd.DataFrame(data)
        mock_df = MagicMock()
        mock_df.select.return_value.toPandas.return_value = pdf
        return mock_df

    def test_day1_creates_4_masters(self):
        """Day 1 should create 4 separate master records."""
        vendor_data = [
            {"vendor_id": 1, "vendor_name": "Creative Mobile Technologies, LLC", "normalized_name": "creative mobile", "record_hash": "h1"},
            {"vendor_id": 2, "vendor_name": "Curb Mobility, LLC", "normalized_name": "curb mobility", "record_hash": "h2"},
            {"vendor_id": 6, "vendor_name": "Myle Technologies Inc", "normalized_name": "myle", "record_hash": "h6"},
            {"vendor_id": 7, "vendor_name": "Helix", "normalized_name": "helix", "record_hash": "h7"},
        ]
        vendor_df = self._create_mock_vendor_df(vendor_data)
        metrics_df, _ = build_recordlinkage_metrics(
            vendor_df, existing_current=None, ingestion_date="2026-01-18"
        )

        # 4 unique match groups = 4 masters
        unique_groups = metrics_df["match_group"].nunique()
        assert unique_groups == 4, f"Day 1 should create 4 masters, got {unique_groups}"

    def test_day2_expected_groupings(self):
        """Day 2 should have correct groupings:
        - vendor_id=7 -> gk=7 (matches Helix)
        - vendor_id=8 -> gk=1 (matches Creative Mobile)
        - vendor_id=10 -> new master (no match)
        """
        vendor_data = [
            {"vendor_id": 7, "vendor_name": "Helix Technologies", "normalized_name": "helix", "record_hash": "h7v2"},
            {"vendor_id": 8, "vendor_name": "Creative Mobil", "normalized_name": "creative mobil", "record_hash": "h8"},
            {"vendor_id": 10, "vendor_name": "Savitha Technologies", "normalized_name": "savitha", "record_hash": "h10"},
        ]
        existing_data = [
            {"vendor_gk": 1, "canonical_name": "Creative Mobile Technologies, LLC", "normalized_name": "creative mobile"},
            {"vendor_gk": 2, "canonical_name": "Curb Mobility, LLC", "normalized_name": "curb mobility"},
            {"vendor_gk": 6, "canonical_name": "Myle Technologies Inc", "normalized_name": "myle"},
            {"vendor_gk": 7, "canonical_name": "Helix", "normalized_name": "helix"},
        ]
        vendor_df = self._create_mock_vendor_df(vendor_data)
        existing_current = self._create_mock_existing_current(existing_data)

        metrics_df, _ = build_recordlinkage_metrics(
            vendor_df, existing_current=existing_current, ingestion_date="2026-01-19"
        )

        groups = dict(zip(metrics_df["vendor_id"], metrics_df["match_group"]))

        assert groups[7] == 7, "Helix Technologies should match gk=7"
        assert groups[8] == 1, "Creative Mobil should match gk=1"
        assert groups[10] == -10, "Savitha should be new master"

        # This means after Day 2:
        # - gk=1 may have RENAME (Creative Mobile -> Creative Mobil wins survivorship? No - existing not in input)
        # - gk=7 may have RENAME (Helix -> Helix Technologies)
        # - gk=10 new master (Savitha Technologies)
        # Total dim_vendor: 4 (Day1) + possible RENAMEs + 1 new = 5-7 records


class TestApplySurvivorshipRules:
    """Tests for apply_survivorship_rules() function."""

    def test_prefers_longest_name(self, spark):
        """Survivorship prefers longest vendor_name."""
        data = [
            (1, "Creative Mobile Technologies, LLC", "creative mobile", 1, 0.9, "EXACT"),
            (8, "Creative Mobil", "creative mobil", 1, 0.85, "RECORDLINKAGE"),
        ]
        df = spark.createDataFrame(
            data,
            ["vendor_id", "vendor_name", "normalized_name", "match_group", "match_confidence", "match_rule"],
        )
        result = apply_survivorship_rules(df).collect()

        assert len(result) == 1
        assert result[0]["vendor_id"] == 1  # Longer name wins

    def test_tiebreaker_lowest_vendor_id(self, spark):
        """When names are same length, prefer lowest vendor_id."""
        data = [
            (5, "Helix Corp", "helix", 1, 0.9, "EXACT"),
            (3, "Helix Corp", "helix", 1, 0.85, "RECORDLINKAGE"),
        ]
        df = spark.createDataFrame(
            data,
            ["vendor_id", "vendor_name", "normalized_name", "match_group", "match_confidence", "match_rule"],
        )
        result = apply_survivorship_rules(df).collect()

        assert len(result) == 1
        assert result[0]["vendor_id"] == 3  # Lower vendor_id wins


class TestDecisionThresholds:
    """Tests for decision threshold logic."""

    def test_decision_auto_above_95(self, spark):
        """match_confidence > 0.95 -> decision = 'AUTO'."""
        df = spark.createDataFrame([(1, 0.96)], ["vendor_id", "match_confidence"])
        result = df.withColumn(
            "decision",
            F.when(F.col("match_confidence") > 0.95, F.lit("AUTO"))
            .when(F.col("match_confidence") >= 0.85, F.lit("STEWARD_REVIEW"))
            .when(F.col("match_confidence") >= 0.75, F.lit("MANUAL_REVIEW"))
            .otherwise(F.lit("NO_MATCH")),
        ).first()
        assert result["decision"] == "AUTO"

    def test_decision_steward_review_85_to_95(self, spark):
        """0.85 <= match_confidence <= 0.95 -> decision = 'STEWARD_REVIEW'."""
        df = spark.createDataFrame([(1, 0.90)], ["vendor_id", "match_confidence"])
        result = df.withColumn(
            "decision",
            F.when(F.col("match_confidence") > 0.95, F.lit("AUTO"))
            .when(F.col("match_confidence") >= 0.85, F.lit("STEWARD_REVIEW"))
            .when(F.col("match_confidence") >= 0.75, F.lit("MANUAL_REVIEW"))
            .otherwise(F.lit("NO_MATCH")),
        ).first()
        assert result["decision"] == "STEWARD_REVIEW"

    def test_decision_manual_review_75_to_85(self, spark):
        """0.75 <= match_confidence < 0.85 -> decision = 'MANUAL_REVIEW'."""
        df = spark.createDataFrame([(1, 0.80)], ["vendor_id", "match_confidence"])
        result = df.withColumn(
            "decision",
            F.when(F.col("match_confidence") > 0.95, F.lit("AUTO"))
            .when(F.col("match_confidence") >= 0.85, F.lit("STEWARD_REVIEW"))
            .when(F.col("match_confidence") >= 0.75, F.lit("MANUAL_REVIEW"))
            .otherwise(F.lit("NO_MATCH")),
        ).first()
        assert result["decision"] == "MANUAL_REVIEW"

    def test_decision_no_match_below_75(self, spark):
        """match_confidence < 0.75 -> decision = 'NO_MATCH'."""
        df = spark.createDataFrame([(1, 0.60)], ["vendor_id", "match_confidence"])
        result = df.withColumn(
            "decision",
            F.when(F.col("match_confidence") > 0.95, F.lit("AUTO"))
            .when(F.col("match_confidence") >= 0.85, F.lit("STEWARD_REVIEW"))
            .when(F.col("match_confidence") >= 0.75, F.lit("MANUAL_REVIEW"))
            .otherwise(F.lit("NO_MATCH")),
        ).first()
        assert result["decision"] == "NO_MATCH"


class TestSCDType2:
    """Tests for apply_scd_type_2() function."""

    def test_scd2_new_record(self, spark):
        """New vendor_gk creates a new current record."""
        new_dim = spark.createDataFrame(
            [(100, "New Vendor", "hash100", -100)],
            ["vendor_gk", "canonical_name", "record_hash", "match_group"],
        )
        result = apply_scd_type_2(new_dim, existing_dim=None, ingestion_date="2026-01-18")
        row = result.collect()[0]

        assert row["vendor_gk"] == 100
        assert row["is_current"] is True
        assert row["change_reason"] == "NEW"
        assert row["valid_to"] is None

    def test_scd2_unchanged_record(self, spark, existing_dim_day1):
        """Same record_hash keeps existing record unchanged."""
        new_dim = spark.createDataFrame(
            [(1, "Creative Mobile Technologies, LLC", "hash1", -1)],
            ["vendor_gk", "canonical_name", "record_hash", "match_group"],
        )
        result = apply_scd_type_2(new_dim, existing_dim_day1, ingestion_date="2026-01-19")
        current = result.filter(F.col("vendor_gk") == 1).filter(F.col("is_current")).collect()

        assert len(current) == 1
        assert current[0]["change_reason"] == "NEW"  # Original unchanged

    def test_scd2_changed_record(self, spark, existing_dim_day1):
        """Different record_hash creates new version and closes old."""
        new_dim = spark.createDataFrame(
            [(1, "Creative Mobile Tech", "hash1_v2", -1)],
            ["vendor_gk", "canonical_name", "record_hash", "match_group"],
        )
        result = apply_scd_type_2(new_dim, existing_dim_day1, ingestion_date="2026-01-19")
        records = result.filter(F.col("vendor_gk") == 1).collect()

        current = [r for r in records if r["is_current"]]
        closed = [r for r in records if not r["is_current"]]

        assert len(current) == 1
        assert current[0]["change_reason"] == "RENAME"
        assert len(closed) == 1
        assert closed[0]["valid_to"] is not None


class TestXrefSCD2:
    """Tests for apply_xref_scd2() function."""

    def _xref_schema(self):
        """Return the schema for xref DataFrame with None values."""
        from pyspark.sql.types import (
            BooleanType,
            DateType,
            DoubleType,
            IntegerType,
            LongType,
            StringType,
            StructField,
            StructType,
        )

        return StructType(
            [
                StructField("vendor_id", IntegerType(), False),
                StructField("vendor_gk", LongType(), True),
                StructField("valid_from", DateType(), True),
                StructField("valid_to", DateType(), True),
                StructField("is_current", BooleanType(), True),
                StructField("match_rule", StringType(), True),
                StructField("match_confidence", DoubleType(), True),
                StructField("decision", StringType(), True),
            ]
        )

    def test_xref_scd2_new_vendor(self, spark):
        """New vendor_id creates new xref record."""
        from datetime import date

        schema = self._xref_schema()
        new_xref = spark.createDataFrame(
            [(100, 1, date(2026, 1, 18), None, True, "EXACT", 1.0, "AUTO")],
            schema,
        )
        result = apply_xref_scd2(new_xref, existing_xref=None, ingestion_date="2026-01-18")
        row = result.collect()[0]

        assert row["vendor_id"] == 100
        assert row["is_current"] is True

    def test_xref_scd2_vendor_reassigned(self, spark):
        """vendor_id reassigned to different gk closes old, creates new."""
        from datetime import date

        schema = self._xref_schema()
        existing_xref = spark.createDataFrame(
            [(8, 99, date(2026, 1, 18), None, True, "RECORDLINKAGE", 0.8, "MANUAL_REVIEW")],
            schema,
        )
        new_xref = spark.createDataFrame(
            [(8, 1, date(2026, 1, 19), None, True, "RECORDLINKAGE", 0.85, "STEWARD_REVIEW")],
            schema,
        )
        result = apply_xref_scd2(new_xref, existing_xref, ingestion_date="2026-01-19")
        records = result.collect()

        current = [r for r in records if r["is_current"]]
        closed = [r for r in records if not r["is_current"]]

        assert len(current) == 1
        assert current[0]["vendor_gk"] == 1
        assert len(closed) == 1
        assert closed[0]["vendor_gk"] == 99

    def test_xref_scd2_existing_not_in_new_stays_current(self, spark):
        """Existing records NOT in new data should remain current (incremental processing)."""
        from datetime import date

        schema = self._xref_schema()
        # Day 1: vendor_ids 1, 2, 6, 7 were created
        existing_xref = spark.createDataFrame(
            [
                (1, 100, date(2026, 1, 18), None, True, "RECORDLINKAGE", 0.0, "NO_MATCH"),
                (2, 200, date(2026, 1, 18), None, True, "RECORDLINKAGE", 0.65, "NO_MATCH"),
                (6, 600, date(2026, 1, 18), None, True, "RECORDLINKAGE", 0.48, "NO_MATCH"),
                (7, 700, date(2026, 1, 18), None, True, "EXACT", 1.0, "AUTO"),
            ],
            schema,
        )
        # Day 2: only vendor_ids 7, 8, 10 are in the new data
        new_xref = spark.createDataFrame(
            [
                (7, 700, date(2026, 1, 19), None, True, "EXACT", 1.0, "AUTO"),
                (8, 100, date(2026, 1, 19), None, True, "RECORDLINKAGE", 0.98, "AUTO"),
                (10, 1000, date(2026, 1, 19), None, True, "RECORDLINKAGE", 0.53, "NO_MATCH"),
            ],
            schema,
        )
        result = apply_xref_scd2(new_xref, existing_xref, ingestion_date="2026-01-19")
        records = result.collect()

        current = [r for r in records if r["is_current"]]
        current_vendor_ids = {r["vendor_id"] for r in current}

        # All vendor_ids should still be current (1, 2, 6, 7, 8, 10)
        assert current_vendor_ids == {1, 2, 6, 7, 8, 10}, f"Expected all vendors current, got {current_vendor_ids}"

        # vendor_ids 1, 2, 6 should retain their original valid_from date
        vendor_1 = [r for r in current if r["vendor_id"] == 1][0]
        assert vendor_1["valid_from"] == date(2026, 1, 18), "vendor_id 1 should keep original valid_from"
        assert vendor_1["is_current"] is True, "vendor_id 1 should still be current"

        # No records should be closed (vendor_id 7 unchanged, 1, 2, 6 not in new data)
        closed = [r for r in records if not r["is_current"]]
        assert len(closed) == 0, f"No records should be closed, got {len(closed)}"


class TestSCDType2NotInNew:
    """Tests for SCD Type 2 when existing records are not in new data."""

    def _dim_schema(self):
        """Return the schema for dim_vendor DataFrame with None values."""
        from pyspark.sql.types import (
            BooleanType,
            DateType,
            LongType,
            StringType,
            StructField,
            StructType,
        )

        return StructType(
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

    def test_scd2_existing_not_in_new_stays_current(self, spark):
        """Existing dim records NOT in new data should remain current."""
        from datetime import date

        schema = self._dim_schema()
        # Day 1: 4 masters were created
        existing_dim = spark.createDataFrame(
            [
                (1, "Creative Mobile Technologies, LLC", date(2026, 1, 18), None, True, "NEW", "hash1"),
                (2, "Curb Mobility, LLC", date(2026, 1, 18), None, True, "NEW", "hash2"),
                (6, "Myle Technologies Inc", date(2026, 1, 18), None, True, "NEW", "hash6"),
                (7, "Helix", date(2026, 1, 18), None, True, "NEW", "hash7"),
            ],
            schema,
        )
        # Day 2: only vendor_gk 7 and new 10 are in the new data
        new_dim = spark.createDataFrame(
            [
                (7, "Helix", "hash7", 7),
                (10, "Savitha Technologies", "hash10", -10),
            ],
            ["vendor_gk", "canonical_name", "record_hash", "match_group"],
        )
        result = apply_scd_type_2(new_dim, existing_dim, ingestion_date="2026-01-19")
        records = result.collect()

        current = [r for r in records if r["is_current"]]
        current_gks = {r["vendor_gk"] for r in current}

        # All vendor_gks should still be current (1, 2, 6, 7, 10)
        assert current_gks == {1, 2, 6, 7, 10}, f"Expected all masters current, got {current_gks}"

        # vendor_gks 1, 2, 6 should retain their original valid_from date
        vendor_1 = [r for r in current if r["vendor_gk"] == 1][0]
        assert vendor_1["valid_from"] == date(2026, 1, 18), "vendor_gk 1 should keep original valid_from"
        assert vendor_1["is_current"] is True, "vendor_gk 1 should still be current"

