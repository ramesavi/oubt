import sys

import pandas as pd
import recordlinkage as rl
from awsglue.utils import getResolvedOptions
from glue_utils import init_glue_job
from pyspark.sql import functions as F
from pyspark.sql.window import Window


def get_glue_args(argv):
    return getResolvedOptions(
        argv,
        [
            "JOB_NAME",
            "bronze_db",
            "master_db",
            "debug_db",
            "ingestion_date",
            "output_path",
            "debug_output_path",
        ],
    )


def parse_args(argv):
    args = get_glue_args(argv)
    bronze_table = f"{args['bronze_db']}.vendor"
    master_dim_table = f"{args['master_db']}.dim_vendor"
    master_xref_table = f"{args['master_db']}.xref_vendor"
    debug_vendor_match_pairs_table = f"{args['debug_db']}.debug_vendor_match_pairs"
    ingestion_date = args["ingestion_date"]
    output_path = args["output_path"]
    debug_output_path = args["debug_output_path"]
    dim_vendor_path = f"{output_path}/dim_vendor"
    xref_vendor_path = f"{output_path}/xref_vendor"
    debug_vendor_match_pairs_path = f"{debug_output_path}/debug_vendor_match_pairs"
    return (
        args,
        bronze_table,
        master_dim_table,
        master_xref_table,
        debug_vendor_match_pairs_table,
        ingestion_date,
        dim_vendor_path,
        xref_vendor_path,
        debug_vendor_match_pairs_path,
    )


def init_spark(args):
    spark, glue_context, job = init_glue_job(args["JOB_NAME"], args)
    spark.conf.set("spark.sql.sources.partitionOverwriteMode", "dynamic")
    spark.conf.set("spark.databricks.delta.schema.autoMerge.enabled", "true")
    return spark, glue_context, job


def read_bronze(glue_context, bronze_table, ingestion_date):
    """
    Read from Glue Data Catalog, filtering by ingestion_date.
    """
    if "." not in bronze_table:
        raise ValueError(f"Expected database.table format, got: {bronze_table}")
    bronze_db, bronze_name = bronze_table.split(".", 1)

    df = (
        glue_context.create_dynamic_frame.from_catalog(
            database=bronze_db, table_name=bronze_name
        )
        .toDF()
    )
    return df.filter(F.col("ingestion_date") == F.lit(ingestion_date))


def normalized_vendor_name(col: F.Column) -> F.Column:
    """
    Normalize vendor name:
      - lowercase, trim
      - replace punctuation with spaces
      - collapse whitespace
      - remove legal suffixes (LLC, Inc, Ltd, Corp, etc.)
      - remove common business words that cause false matches
    """
    x = F.lower(F.trim(col))
    x = F.regexp_replace(x, r"[^a-z0-9]+", " ")
    x = F.regexp_replace(x, r"\s+", " ")
    x = F.trim(x)
    # Remove legal suffixes
    x = F.regexp_replace(
        x,
        r"\b(llc|l\.l\.c|inc|incorporated|ltd|limited|corp|corporation|co|company)\b",
        "",
    )
    # Remove common business words that cause false matches
    x = F.regexp_replace(
        x,
        r"\b(technologies|technology|tech|solutions|services|systems|group|holdings|enterprises)\b",
        "",
    )
    x = F.regexp_replace(x, r"\s+", " ")
    x = F.trim(x)
    return x


def transform_bronze(df):
    """
    Transform bronze data: type casting, null handling, normalization, deduplication.
    """
    df = df.select(
        F.col("vendor_id").cast("int").alias("vendor_id"),
        F.when(F.trim(F.col("vendor_name")) == "", F.lit(None))
        .otherwise(F.trim(F.col("vendor_name")))
        .alias("vendor_name"),
        F.col("ingestion_date").cast("date").alias("ingestion_date"),
    )
    df = df.withColumn("normalized_name", normalized_vendor_name(F.col("vendor_name")))
    return df.dropDuplicates(["vendor_id"])


def generate_record_hash(df):
    return df.withColumn(
        "record_hash", F.sha2(F.concat_ws("|", F.col("normalized_name")), 256)
    )


def build_recordlinkage_metrics(vendor_df, existing_current, ingestion_date=None):
    pdf_all = (
        vendor_df.select("vendor_id", "vendor_name", "normalized_name", "record_hash")
        .dropna(subset=["vendor_id"])
        .toPandas()
    )

    empty_debug = pd.DataFrame(
        columns=[
            "ingestion_date",
            "source_id_1",
            "source_id_2",
            "entity_type_1",
            "entity_type_2",
            "normalized_name_1",
            "normalized_name_2",
            "match_confidence",
            "match_group_1",
            "match_group_2",
            "same_group",
            "above_threshold",
        ]
    )

    if pdf_all.empty and existing_current is None:
        return (
            pd.DataFrame(
                columns=["vendor_id", "match_group", "match_confidence", "match_rule"]
            ),
            empty_debug,
        )

    pdf_all["vendor_id"] = pdf_all["vendor_id"].astype("Int64")  # nullable int64
    pdf_all["entity_id"] = "S:" + pdf_all["vendor_id"].astype(str)
    pdf_all["entity_type"] = "S"

    existing_pdf_all = pd.DataFrame(
        columns=[
            "vendor_gk",
            "canonical_name",
            "normalized_name",
            "entity_id",
            "entity_type",
        ]
    )
    if existing_current is not None:
        existing_pdf_all = existing_current.select(
            "vendor_gk", "canonical_name", "normalized_name"
        ).toPandas()
        if not existing_pdf_all.empty:
            existing_pdf_all["vendor_gk"] = existing_pdf_all["vendor_gk"].astype("Int64")  # nullable int64
            existing_pdf_all["entity_id"] = "G:" + existing_pdf_all["vendor_gk"].astype(
                str
            )
            existing_pdf_all["entity_type"] = "G"

    combined = pd.concat(
        [
            pdf_all[["entity_id", "entity_type", "vendor_id", "normalized_name"]],
            existing_pdf_all[
                ["entity_id", "entity_type", "vendor_gk", "normalized_name"]
            ],
        ],
        ignore_index=True,
    )

    all_ids = pdf_all["vendor_id"].tolist()  # Already Int64, convert to Python ints
    all_ids = [int(x) for x in all_ids]
    vendor_entities = pdf_all[["vendor_id", "entity_id"]].copy()

    matchable = combined.dropna(subset=["normalized_name"]).set_index("entity_id")
    if matchable.empty:
        metrics_df = pd.DataFrame({"vendor_id": all_ids})
        metrics_df["match_group"] = metrics_df["vendor_id"].map(lambda v: -int(v))
        metrics_df["match_confidence"] = 0.0
        metrics_df["match_rule"] = "RECORDLINKAGE"
        return metrics_df, empty_debug

    pairs_df = pd.DataFrame(columns=["vendor_id_1", "vendor_id_2", "match_confidence"])
    indexer = rl.Index()
    indexer.full()
    pairs = indexer.index(matchable)

    compare = rl.Compare()
    compare.string(
        "normalized_name",
        "normalized_name",
        method="jarowinkler",
        label="match_confidence",
    )
    features = compare.compute(pairs, matchable)
    pairs_df = (
        features.reset_index()
        .rename(columns={"level_0": "entity_id_1", "level_1": "entity_id_2"})
        .sort_values(
            ["match_confidence", "entity_id_1", "entity_id_2"],
            ascending=[False, True, True],
        )
    )

    parent = {eid: eid for eid in matchable.index.tolist()}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    edges = pairs_df[
        (pairs_df["match_confidence"] >= 0.75)
        & (
            pairs_df["entity_id_1"].str.startswith("S:")
            | pairs_df["entity_id_2"].str.startswith("S:")
        )
    ][["entity_id_1", "entity_id_2"]]
    for a, b in edges.itertuples(index=False):
        union(a, b)

    entity_to_root = {eid: find(eid) for eid in parent}

    root_to_gk = {}
    root_to_min_vendor = {}
    matchable_reset = matchable.reset_index()
    for row in matchable_reset.itertuples(index=False):
        entity_id = row.entity_id
        root = entity_to_root.get(entity_id, entity_id)
        if row.entity_type == "G":
            gk = int(row.vendor_gk)
            root_to_gk[root] = min(gk, root_to_gk.get(root, gk))
        else:
            vid = int(row.vendor_id)
            root_to_min_vendor[root] = min(vid, root_to_min_vendor.get(root, vid))

    root_to_group = {}
    for root, min_vid in root_to_min_vendor.items():
        if root in root_to_gk:
            root_to_group[root] = root_to_gk[root]
        else:
            root_to_group[root] = -min_vid

    def group_id_for_entity(entity_id, vendor_id):
        if entity_id in entity_to_root:
            root = entity_to_root[entity_id]
            return root_to_group.get(root, -int(vendor_id))
        return -int(vendor_id)

    groups_df = vendor_entities.copy()
    groups_df["match_group"] = groups_df.apply(
        lambda row: group_id_for_entity(row["entity_id"], row["vendor_id"]), axis=1
    )

    best = pd.Series(0.0, index=vendor_entities["entity_id"].tolist())
    if not pairs_df.empty:
        pairs_for_best = pairs_df[
            pairs_df["entity_id_1"].str.startswith("S:")
            | pairs_df["entity_id_2"].str.startswith("S:")
        ]
        best_left = pairs_for_best.groupby("entity_id_1")["match_confidence"].max()
        best_right = pairs_for_best.groupby("entity_id_2")["match_confidence"].max()
        best = best_left.combine(best_right, max).reindex(
            vendor_entities["entity_id"].tolist(), fill_value=0.0
        )

    metrics_df = groups_df.assign(
        match_confidence=groups_df["entity_id"].map(best).fillna(0.0),
    )
    metrics_df["match_rule"] = metrics_df["match_confidence"].map(
        lambda c: "EXACT" if c == 1.0 else "RECORDLINKAGE"
    )
    # Ensure match_group is int64 to prevent precision loss when converting to Spark
    # (Spark may infer object dtype as DoubleType, losing precision for large integers)
    metrics_df["match_group"] = metrics_df["match_group"].astype("int64")

    debug_pairs_df = build_debug_vendor_match_pairs(
        pairs_df, matchable, entity_to_root, root_to_group, ingestion_date
    )

    return (
        metrics_df[["vendor_id", "match_group", "match_confidence", "match_rule"]],
        debug_pairs_df,
    )


def build_debug_vendor_match_pairs(
    pairs_df, matchable, entity_to_root, root_to_group, ingestion_date
):
    """Build debug pairs dataframe including unmatched entities."""
    matchable_reset = matchable.reset_index()

    entity_info = {}
    for row in matchable_reset.itertuples(index=False):
        entity_info[row.entity_id] = {
            "entity_type": row.entity_type,
            "normalized_name": row.normalized_name,
            "vendor_id": getattr(row, "vendor_id", None),
            "vendor_gk": getattr(row, "vendor_gk", None),
        }

    def get_source_id(info):
        if info is None:
            return None
        if info["entity_type"] == "S":
            vid = info.get("vendor_id")
            return int(vid) if vid is not None else None
        gk = info.get("vendor_gk")
        return int(gk) if gk is not None else None

    def get_match_group(entity_id):
        if entity_id in entity_to_root:
            root = entity_to_root[entity_id]
            return root_to_group.get(root)
        return None

    rows = []

    if not pairs_df.empty:
        for row in pairs_df.itertuples(index=False):
            e1, e2 = row.entity_id_1, row.entity_id_2
            info1 = entity_info.get(e1)
            info2 = entity_info.get(e2)
            mg1 = get_match_group(e1)
            mg2 = get_match_group(e2)

            rows.append(
                {
                    "ingestion_date": ingestion_date,
                    "source_id_1": get_source_id(info1),
                    "source_id_2": get_source_id(info2),
                    "entity_type_1": info1.get("entity_type") if info1 else None,
                    "entity_type_2": info2.get("entity_type") if info2 else None,
                    "normalized_name_1": info1.get("normalized_name") if info1 else None,
                    "normalized_name_2": info2.get("normalized_name") if info2 else None,
                    "match_confidence": row.match_confidence,
                    "match_group_1": mg1,
                    "match_group_2": mg2,
                    "same_group": mg1 == mg2
                    if (mg1 is not None and mg2 is not None)
                    else False,
                    "above_threshold": row.match_confidence >= 0.75,
                }
            )

    entities_in_pairs = set()
    if not pairs_df.empty:
        entities_in_pairs = set(pairs_df["entity_id_1"]).union(
            set(pairs_df["entity_id_2"])
        )

    all_entities = set(matchable.index.tolist())
    unmatched = all_entities - entities_in_pairs

    for entity_id in unmatched:
        info = entity_info.get(entity_id)
        mg = get_match_group(entity_id)
        rows.append(
            {
                "ingestion_date": ingestion_date,
                "source_id_1": get_source_id(info),
                "source_id_2": None,
                "entity_type_1": info.get("entity_type") if info else None,
                "entity_type_2": None,
                "normalized_name_1": info.get("normalized_name") if info else None,
                "normalized_name_2": None,
                "match_confidence": 0.0,
                "match_group_1": mg,
                "match_group_2": None,
                "same_group": False,
                "above_threshold": False,
            }
        )

    result_df = pd.DataFrame(rows)
    # Ensure match_group columns are int64 to prevent precision loss when converting to Spark
    if not result_df.empty:
        result_df["match_group_1"] = result_df["match_group_1"].astype("Int64")  # nullable int64
        result_df["match_group_2"] = result_df["match_group_2"].astype("Int64")  # nullable int64
        result_df["source_id_1"] = result_df["source_id_1"].astype("Int64")
        result_df["source_id_2"] = result_df["source_id_2"].astype("Int64")
    return result_df


def write_debug_vendor_match_pairs(df, spark, table, path):
    """
    Create debug_vendor_match_pairs table if missing and overwrite the data.
    Partitioned by ingestion_date.
    """
    spark.sql(
        f"""
        CREATE TABLE IF NOT EXISTS {table} (
            source_id_1 LONG,
            source_id_2 LONG,
            entity_type_1 STRING,
            entity_type_2 STRING,
            normalized_name_1 STRING,
            normalized_name_2 STRING,
            match_confidence DOUBLE,
            match_group_1 LONG,
            match_group_2 LONG,
            same_group BOOLEAN,
            above_threshold BOOLEAN,
            ingestion_date DATE
        )
        USING DELTA
        PARTITIONED BY (ingestion_date)
        LOCATION '{path}'
        """
    )
    (
        df.select(
            F.col("source_id_1").cast("long"),
            F.col("source_id_2").cast("long"),
            F.col("entity_type_1").cast("string"),
            F.col("entity_type_2").cast("string"),
            F.col("normalized_name_1").cast("string"),
            F.col("normalized_name_2").cast("string"),
            F.col("match_confidence").cast("double"),
            F.col("match_group_1").cast("long"),
            F.col("match_group_2").cast("long"),
            F.col("same_group").cast("boolean"),
            F.col("above_threshold").cast("boolean"),
            F.col("ingestion_date").cast("date"),
        )
        .write.format("delta")
        .mode("overwrite")
        .option("replaceWhere", f"ingestion_date = '{df.first()['ingestion_date']}'")
        .save(path)
    )


def apply_survivorship_rules(vendor_scored):
    window = Window.partitionBy("match_group").orderBy(
        F.desc(F.length("vendor_name")), F.asc("vendor_id")
    )
    return (
        vendor_scored.withColumn("rn", F.row_number().over(window))
        .filter(F.col("rn") == 1)
        .drop("rn")
    )


def build_master_records(vendor_scored, existing_current):
    canonical_name = F.coalesce(F.col("vendor_name"), F.col("normalized_name"))
    if existing_current is None:
        return vendor_scored.select(
            F.abs(
                F.xxhash64(
                    F.concat_ws(
                        "|", canonical_name, F.col("match_group").cast("string")
                    )
                )
            )
            .cast("long")
            .alias("vendor_gk"),
            canonical_name.alias("canonical_name"),
            F.col("record_hash"),
            F.col("match_group"),
        )

    existing_gk = existing_current.select(
        F.col("vendor_gk").alias("existing_vendor_gk")
    )
    joined = vendor_scored.join(
        existing_gk,
        vendor_scored["match_group"] == existing_gk["existing_vendor_gk"],
        "left",
    )
    return joined.select(
        F.when(F.col("existing_vendor_gk").isNotNull(), F.col("existing_vendor_gk"))
        .otherwise(
            F.abs(
                F.xxhash64(
                    F.concat_ws(
                        "|", canonical_name, F.col("match_group").cast("string")
                    )
                )
            )
        )
        .cast("long")
        .alias("vendor_gk"),
        canonical_name.alias("canonical_name"),
        F.col("record_hash"),
        F.col("match_group"),
    )


def apply_scd_type_2(new_dim, existing_dim, ingestion_date):
    new_dim_base = new_dim.select(
        "vendor_gk",
        "canonical_name",
        F.lit(ingestion_date).cast("date").alias("valid_from"),
        F.lit(None).cast("date").alias("valid_to"),
        F.lit(True).alias("is_current"),
        F.lit("NEW").alias("change_reason"),
        "record_hash",
    )

    if existing_dim is None:
        return new_dim_base

    existing_current = existing_dim.filter(F.col("is_current") == F.lit(True))
    existing_hist = existing_dim.filter(F.col("is_current") == F.lit(False))

    joined = new_dim_base.alias("n").join(
        existing_current.alias("e"), "vendor_gk", "left"
    )

    # Records that exist in both and haven't changed - keep existing
    unchanged = joined.filter(
        F.col("e.vendor_gk").isNotNull()
        & (F.col("n.record_hash") == F.col("e.record_hash"))
    ).select("e.*")

    # Records that exist in both but have changed
    changed = joined.filter(
        F.col("e.vendor_gk").isNotNull()
        & (F.col("n.record_hash") != F.col("e.record_hash"))
    )
    # Close old records
    closed = (
        changed.select("e.*")
        .withColumn("valid_to", F.date_sub(F.lit(ingestion_date).cast("date"), 1))
        .withColumn("is_current", F.lit(False))
        .withColumn("change_reason", F.lit("RENAME"))
    )
    changed_new = (
        changed.select("n.*")
        .withColumn("change_reason", F.lit("RENAME"))
        .withColumn("is_current", F.lit(True))
        .withColumn("valid_to", F.lit(None).cast("date"))
        .withColumn("valid_from", F.lit(ingestion_date).cast("date"))
    )

    # New vendor_gk not in existing
    new_only = joined.filter(F.col("e.vendor_gk").isNull()).select("n.*")

    # Existing current records NOT in new data - keep them as-is (still current)
    not_in_new = existing_current.join(
        new_dim.select("vendor_gk"), "vendor_gk", "left_anti"
    )

    return (
        existing_hist.unionByName(unchanged)
        .unionByName(closed)
        .unionByName(changed_new)
        .unionByName(new_only)
        .unionByName(not_in_new)
    )


def build_xref(vendor_scored, group_to_gk, ingestion_date):
    return vendor_scored.join(group_to_gk, on="match_group", how="left").select(
        F.col("vendor_id"),
        F.col("vendor_gk"),
        F.lit(ingestion_date).cast("date").alias("valid_from"),
        F.lit(None).cast("date").alias("valid_to"),
        F.lit(True).alias("is_current"),
        F.col("match_rule"),
        F.col("match_confidence"),
        F.col("decision"),
    )


def apply_xref_scd2(new_xref, existing_xref, ingestion_date):
    if existing_xref is None:
        return new_xref

    existing_current = existing_xref.filter(F.col("is_current") == F.lit(True))
    existing_hist = existing_xref.filter(F.col("is_current") == F.lit(False))

    joined = new_xref.alias("n").join(existing_current.alias("e"), "vendor_id", "left")

    # Records that exist in both and haven't changed - keep existing
    unchanged = joined.filter(
        F.col("e.vendor_id").isNotNull()
        & (F.col("e.vendor_gk") == F.col("n.vendor_gk"))
        & (F.col("e.match_rule") == F.col("n.match_rule"))
        & (F.col("e.match_confidence") == F.col("n.match_confidence"))
        & (F.col("e.decision") == F.col("n.decision"))
    ).select("e.*")

    # Records that exist in both but have changed
    changed = joined.filter(
        F.col("e.vendor_id").isNotNull()
        & ~(
            (F.col("e.vendor_gk") == F.col("n.vendor_gk"))
            & (F.col("e.match_rule") == F.col("n.match_rule"))
            & (F.col("e.match_confidence") == F.col("n.match_confidence"))
            & (F.col("e.decision") == F.col("n.decision"))
        )
    )
    # Close old records - valid_to is day before new record starts
    closed = (
        changed.select("e.*")
        .withColumn("valid_to", F.date_sub(F.lit(ingestion_date).cast("date"), 1))
        .withColumn("is_current", F.lit(False))
    )
    changed_new = changed.select("n.*")

    # New vendor_ids not in existing
    new_only = joined.filter(F.col("e.vendor_id").isNull()).select("n.*")

    # Existing current records NOT in new data - keep them as-is (still current)
    not_in_new = existing_current.join(
        new_xref.select("vendor_id"), "vendor_id", "left_anti"
    )

    return (
        existing_hist.unionByName(unchanged)
        .unionByName(closed)
        .unionByName(changed_new)
        .unionByName(new_only)
        .unionByName(not_in_new)
    )


def write_dim_vendor(df, spark, table, path):
    """
    Create dim_vendor table if missing and overwrite the data.
    """
    spark.sql(
        f"""
        CREATE TABLE IF NOT EXISTS {table} (
            vendor_gk LONG,
            canonical_name STRING,
            valid_from DATE,
            valid_to DATE,
            is_current BOOLEAN,
            change_reason STRING,
            record_hash STRING
        )
        USING DELTA
        LOCATION '{path}'
        """
    )
    (
        df.select(
            "vendor_gk",
            "canonical_name",
            "valid_from",
            "valid_to",
            "is_current",
            "change_reason",
            "record_hash",
        )
        .write.format("delta")
        .mode("overwrite")
        .insertInto(table)
    )


def write_xref_vendor(df, spark, table, path):
    """
    Create xref_vendor table if missing and overwrite the data.
    """
    spark.sql(
        f"""
        CREATE TABLE IF NOT EXISTS {table} (
            vendor_id INT,
            vendor_gk LONG,
            valid_from DATE,
            valid_to DATE,
            is_current BOOLEAN,
            match_rule STRING,
            match_confidence DOUBLE,
            decision STRING
        )
        USING DELTA
        LOCATION '{path}'
        """
    )
    (
        df.select(
            "vendor_id",
            "vendor_gk",
            "valid_from",
            "valid_to",
            "is_current",
            "match_rule",
            "match_confidence",
            "decision",
        )
        .write.format("delta")
        .mode("overwrite")
        .insertInto(table)
    )


def main():
    (
        args,
        bronze_table,
        master_dim_table,
        master_xref_table,
        debug_vendor_match_pairs_table,
        ingestion_date,
        dim_vendor_path,
        xref_vendor_path,
        debug_vendor_match_pairs_path,
    ) = parse_args(sys.argv)
    spark, glue_context, job = init_spark(args)

    # Read from bronze and transform
    bronze_df = read_bronze(glue_context, bronze_table, ingestion_date)
    vendor_df = transform_bronze(bronze_df)

    if vendor_df.limit(1).count() == 0:
        job.commit()
        return

    vendor_df = generate_record_hash(vendor_df)

    existing_dim = (
        spark.read.table(master_dim_table)
        if spark.catalog.tableExists(master_dim_table)
        else None
    )
    existing_current = None
    if existing_dim is not None:
        existing_current = (
            existing_dim.filter(F.col("is_current") == F.lit(True))
            .withColumn(
                "normalized_name", normalized_vendor_name(F.col("canonical_name"))
            )
            .select("vendor_gk", "canonical_name", "normalized_name")
        )

    metrics_df, debug_pairs_df = build_recordlinkage_metrics(
        vendor_df, existing_current, ingestion_date
    )
    metrics_sdf = spark.createDataFrame(metrics_df).select(
        F.col("vendor_id").cast("int"),
        F.col("match_group").cast("long"),
        F.col("match_confidence").cast("double"),
        F.col("match_rule").cast("string"),
    )

    vendor_scored = vendor_df.join(metrics_sdf, on="vendor_id", how="left")
    vendor_scored = vendor_scored.withColumn(
        "decision",
        F.when(F.col("match_confidence") > 0.95, F.lit("AUTO"))
        .when(F.col("match_confidence") >= 0.85, F.lit("STEWARD_REVIEW"))
        .when(F.col("match_confidence") >= 0.75, F.lit("MANUAL_REVIEW"))
        .otherwise(F.lit("NO_MATCH")),
    )

    master_candidates = apply_survivorship_rules(vendor_scored)
    master_records = build_master_records(master_candidates, existing_current)

    final_dim_vendor = apply_scd_type_2(master_records, existing_dim, ingestion_date)

    group_to_gk = master_records.select("match_group", "vendor_gk")
    new_xref = build_xref(vendor_scored, group_to_gk, ingestion_date)
    existing_xref = (
        spark.read.table(master_xref_table)
        if spark.catalog.tableExists(master_xref_table)
        else None
    )
    final_xref_vendor = apply_xref_scd2(new_xref, existing_xref, ingestion_date)

    write_dim_vendor(final_dim_vendor, spark, master_dim_table, dim_vendor_path)
    write_xref_vendor(final_xref_vendor, spark, master_xref_table, xref_vendor_path)

    if not debug_pairs_df.empty:
        debug_pairs_sdf = spark.createDataFrame(debug_pairs_df)
        write_debug_vendor_match_pairs(
            debug_pairs_sdf, spark, debug_vendor_match_pairs_table, debug_vendor_match_pairs_path
        )

    job.commit()


if __name__ == "__main__":
    main()
