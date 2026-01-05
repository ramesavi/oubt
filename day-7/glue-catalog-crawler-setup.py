"""
Day 7 Task 7.5: AWS Glue Catalog & Crawler Setup with Lineage

This script sets up AWS Glue Data Catalog infrastructure for the NYC Taxi data lake:
1. Creates a Glue database for the NYC Taxi data
2. Creates crawlers for each data zone (Bronze, Silver, Gold)
3. Runs crawlers to auto-discover schemas and create tables
4. Adds governance and lineage metadata to all tables

Lineage Tracking:
- source_tables: Upstream tables this table depends on
- derived_from: Source system or file
- transformation_job: Glue/Spark job that creates this table
- downstream_tables: Tables that depend on this table
- lineage_updated: Timestamp of last lineage update

Important: This script uses boto3 for all AWS Glue operations.

Prerequisites:
- AWS credentials configured with Glue permissions
- S3 bucket with data in bronze/silver/gold zones
- IAM role for Glue service (GlueServiceRole)
"""

import sys
import time
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError

# ============================================
# CONFIGURATION
# ============================================
S3_BUCKET = "day-7-spark-glue"
DATABASE_NAME = "nyc_taxi_db"
GLUE_ROLE = "GlueServiceRole"  # IAM role for Glue
AWS_REGION = "us-east-1"  # Default AWS region

# Crawler configurations
CRAWLERS = [
    {
        "name": "bronze_crawler",
        "path": f"s3://{S3_BUCKET}/bronze/",
        "prefix": "bronze_",
        "schedule": "cron(0 6 * * ? *)",  # Daily at 6 AM UTC
        "description": "Crawls Bronze zone for raw data tables",
    },
    {
        "name": "silver_crawler",
        "path": f"s3://{S3_BUCKET}/silver/",
        "prefix": "silver_",
        "schedule": "cron(0 7 * * ? *)",  # Daily at 7 AM UTC
        "description": "Crawls Silver zone for cleaned data tables",
    },
    {
        "name": "gold_crawler",
        "path": f"s3://{S3_BUCKET}/gold/",
        "prefix": "gold_",
        "schedule": "cron(0 8 * * ? *)",  # Daily at 8 AM UTC
        "description": "Crawls Gold zone for aggregated and master data tables",
    },
]

# Table metadata with governance and lineage information
TABLE_METADATA = {
    "bronze_yellow_tripdata": {
        # Governance metadata
        "data_owner": "NYC TLC",
        "domain": "Transportation",
        "classification": "Internal",
        "pii_flag": "false",
        "retention_days": "365",
        "data_zone": "bronze",
        "source_system": "NYC TLC Website",
        # Lineage metadata
        "derived_from": "https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page",
        "source_tables": "",
        "transformation_job": "",
        "downstream_tables": "silver_trips_cleaned",
        "lineage_updated": "",
    },
    "bronze_taxi_zones": {
        # Governance metadata
        "data_owner": "NYC TLC",
        "domain": "Transportation",
        "classification": "Reference Data",
        "pii_flag": "false",
        "retention_days": "indefinite",
        "data_zone": "bronze",
        "source_system": "NYC TLC Website",
        # Lineage metadata
        "derived_from": "https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page",
        "source_tables": "",
        "transformation_job": "",
        "downstream_tables": "silver_zones_cleaned,gold_taxi_zones_master",
        "lineage_updated": "",
    },
    "silver_trips_cleaned": {
        # Governance metadata
        "data_owner": "Data Engineering",
        "domain": "Transportation",
        "classification": "Internal",
        "pii_flag": "false",
        "retention_days": "365",
        "data_zone": "silver",
        # Lineage metadata
        "derived_from": "",
        "source_tables": "bronze_yellow_tripdata",
        "transformation_job": "pyspark-trip-transformations",
        "downstream_tables": "silver_trips_enriched,gold_trip_metrics",
        "lineage_updated": "",
    },
    "silver_zones_cleaned": {
        # Governance metadata
        "data_owner": "Data Engineering",
        "domain": "Transportation",
        "classification": "Reference Data",
        "pii_flag": "false",
        "retention_days": "indefinite",
        "data_zone": "silver",
        # Lineage metadata
        "derived_from": "",
        "source_tables": "bronze_taxi_zones",
        "transformation_job": "pyspark-taxi-transformations",
        "downstream_tables": "gold_taxi_zones_master",
        "lineage_updated": "",
    },
    "silver_trips_enriched": {
        # Governance metadata
        "data_owner": "Data Engineering",
        "domain": "Transportation",
        "classification": "Internal",
        "pii_flag": "false",
        "retention_days": "365",
        "data_zone": "silver",
        # Lineage metadata
        "derived_from": "",
        "source_tables": "silver_trips_cleaned,gold_taxi_zones_master",
        "transformation_job": "master-data-enrichment",
        "downstream_tables": "",
        "lineage_updated": "",
    },
    "gold_taxi_zones_master": {
        # Governance metadata
        "data_owner": "MDM Team",
        "domain": "Transportation",
        "classification": "Master Data",
        "pii_flag": "false",
        "retention_days": "indefinite",
        "data_zone": "gold",
        "is_golden_record": "true",
        "data_steward": "MDM Team",
        # Lineage metadata
        "derived_from": "",
        "source_tables": "silver_zones_cleaned",
        "transformation_job": "pyspark-taxi-transformations",
        "downstream_tables": "silver_trips_enriched",
        "lineage_updated": "",
    },
    "gold_trip_metrics": {
        # Governance metadata
        "data_owner": "Analytics Team",
        "domain": "Transportation",
        "classification": "Analytics",
        "pii_flag": "false",
        "retention_days": "365",
        "data_zone": "gold",
        "is_fact_table": "true",
        "partition_key": "trip_date",
        # Lineage metadata
        "derived_from": "",
        "source_tables": "silver_trips_cleaned",
        "transformation_job": "pyspark-aggregations",
        "downstream_tables": "",
        "lineage_updated": "",
    },
}


# ============================================
# GLUE CLIENT INITIALIZATION
# ============================================
def create_glue_client():
    """Create and return a boto3 Glue client."""
    return boto3.client("glue", region_name=AWS_REGION)


def create_iam_client():
    """Create and return a boto3 IAM client."""
    return boto3.client("iam", region_name=AWS_REGION)


# ============================================
# IAM ROLE CREATION
# ============================================
def create_glue_service_role(iam_client):
    """
    Create the IAM role required for AWS Glue crawlers.

    This role allows Glue to:
    - Access S3 buckets for crawling data
    - Write to CloudWatch Logs
    - Perform Glue operations

    Returns:
        bool: True if role was created or already exists, False on error
    """
    print("\n" + "=" * 60)
    print("Creating IAM Role for Glue Service")
    print("=" * 60)

    # Trust policy allowing Glue to assume this role
    trust_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": "glue.amazonaws.com"},
                "Action": "sts:AssumeRole",
            }
        ],
    }

    try:
        # Check if role already exists
        try:
            iam_client.get_role(RoleName=GLUE_ROLE)
            print(f"  IAM Role '{GLUE_ROLE}' already exists")
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] != "NoSuchEntity":
                raise

        # Create the role
        print(f"  Creating IAM role: {GLUE_ROLE}")
        iam_client.create_role(
            RoleName=GLUE_ROLE,
            AssumeRolePolicyDocument=str(trust_policy).replace("'", '"'),
            Description="IAM role for AWS Glue crawlers to access S3 and Glue resources",
            Tags=[
                {"Key": "Project", "Value": "MDM Training"},
                {"Key": "CreatedBy", "Value": "glue-catalog-crawler-setup.py"},
            ],
        )
        print(f"  Role created: {GLUE_ROLE}")

        # Attach AWS managed policies
        policies_to_attach = [
            {
                "arn": "arn:aws:iam::aws:policy/service-role/AWSGlueServiceRole",
                "name": "AWSGlueServiceRole",
            },
            {
                "arn": "arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess",
                "name": "AmazonS3ReadOnlyAccess",
            },
        ]

        for policy in policies_to_attach:
            print(f"  Attaching policy: {policy['name']}")
            iam_client.attach_role_policy(
                RoleName=GLUE_ROLE,
                PolicyArn=policy["arn"],
            )

        print(f"\n  IAM Role '{GLUE_ROLE}' created successfully!")
        print("  Waiting 10 seconds for IAM role propagation...")
        time.sleep(10)  # IAM roles need time to propagate
        return True

    except ClientError as e:
        print(f"  Error creating IAM role: {e}")
        return False


# ============================================
# STEP 1: CREATE DATABASE
# ============================================
def create_database(glue_client):
    """
    Create the Glue database for NYC Taxi data.

    Database: nyc_taxi_db
    Location: s3://day-6-datalake-nyc-data/
    """
    print("\n" + "=" * 60)
    print("Step 1: Database Creation")
    print("=" * 60)

    try:
        glue_client.create_database(
            DatabaseInput={
                "Name": DATABASE_NAME,
                "Description": "NYC Taxi Trip Data for MDM Training",
                "LocationUri": f"s3://{S3_BUCKET}/",
                "Parameters": {
                    "created_by": "glue-catalog-crawler-setup.py",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "project": "MDM Training",
                    "data_domain": "Transportation",
                },
            }
        )
        print(f"  Database: {DATABASE_NAME}")
        print(f"  Location: s3://{S3_BUCKET}/")
        print("  Status: Created")
        return True

    except ClientError as e:
        if e.response["Error"]["Code"] == "AlreadyExistsException":
            print(f"  Database: {DATABASE_NAME}")
            print(f"  Location: s3://{S3_BUCKET}/")
            print("  Status: Already exists (skipping creation)")
            return True
        else:
            print(f"  Error creating database: {e}")
            raise


# ============================================
# STEP 2: CREATE CRAWLERS
# ============================================
def create_crawlers(glue_client):
    """
    Create Glue crawlers for each data zone.

    Crawlers:
    - bronze_crawler: s3://day-6-datalake-nyc-data/bronze/
    - silver_crawler: s3://day-6-datalake-nyc-data/silver/
    - gold_crawler: s3://day-6-datalake-nyc-data/gold/

    Schema change policy:
    - UpdateBehavior: UPDATE_IN_DATABASE (update schema when changes detected)
    - DeleteBehavior: LOG (log deletions but don't remove from catalog)
    """
    print("\n" + "=" * 60)
    print("Step 2: Crawler Creation")
    print("=" * 60)

    created_crawlers = []

    # Verify the IAM role exists (should have been created in Step 0)
    iam_client = boto3.client("iam", region_name=AWS_REGION)
    try:
        iam_client.get_role(RoleName=GLUE_ROLE)
        print(f"  IAM Role '{GLUE_ROLE}' verified")
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchEntity":
            print(f"\n  ERROR: IAM Role '{GLUE_ROLE}' does not exist!")
            print(
                "  This should have been created in Step 0. Please check for errors above."
            )
            return created_crawlers
        else:
            print(f"  Error checking IAM role: {e}")
            raise

    # Delta Lake crawler configuration
    # This tells Glue to recognize Delta Lake table format
    delta_config = {
        "Version": 1.0,
        "CrawlerOutput": {
            "Partitions": {"AddOrUpdateBehavior": "InheritFromTable"},
            "Tables": {"AddOrUpdateBehavior": "MergeNewColumns"},
        },
        "Grouping": {"TableGroupingPolicy": "CombineCompatibleSchemas"},
    }

    for crawler in CRAWLERS:
        try:
            glue_client.create_crawler(
                Name=crawler["name"],
                Role=GLUE_ROLE,
                DatabaseName=DATABASE_NAME,
                Description=crawler["description"],
                Targets={
                    "DeltaTargets": [
                        {
                            "DeltaTables": [crawler["path"]],
                            "WriteManifest": True,
                        }
                    ]
                },
                TablePrefix=crawler["prefix"],
                SchemaChangePolicy={
                    "UpdateBehavior": "UPDATE_IN_DATABASE",
                    "DeleteBehavior": "LOG",
                },
                Schedule=crawler["schedule"],
                Configuration=str(delta_config).replace("'", '"'),
            )
            print(f"  - {crawler['name']} → {crawler['path']}")
            print(f"    Prefix: {crawler['prefix']}")
            print(f"    Schedule: {crawler['schedule']}")
            created_crawlers.append(crawler["name"])

        except ClientError as e:
            if e.response["Error"]["Code"] == "AlreadyExistsException":
                # Check if the crawler needs to be updated with new S3 path
                existing_crawler = glue_client.get_crawler(Name=crawler["name"])
                existing_targets = existing_crawler["Crawler"].get("Targets", {})
                existing_s3_targets = existing_targets.get("S3Targets", [])
                existing_path = (
                    existing_s3_targets[0]["Path"] if existing_s3_targets else ""
                )

                # Check if using Delta targets or needs update
                existing_delta_targets = existing_targets.get("DeltaTargets", [])
                existing_delta_path = (
                    existing_delta_targets[0]["DeltaTables"][0]
                    if existing_delta_targets
                    and existing_delta_targets[0].get("DeltaTables")
                    else ""
                )

                needs_update = (
                    existing_path != crawler["path"]
                    and existing_delta_path != crawler["path"]
                ) or not existing_delta_targets

                if needs_update:
                    print(f"  - {crawler['name']}: Updating to Delta Lake format")
                    print(f"    Old path: {existing_path or existing_delta_path}")
                    print(f"    New path: {crawler['path']}")

                    # Check if crawler is running and stop it
                    crawler_state = existing_crawler["Crawler"]["State"]
                    if crawler_state in ["RUNNING", "STOPPING"]:
                        print(f"    Stopping crawler (current state: {crawler_state})...")
                        try:
                            glue_client.stop_crawler(Name=crawler["name"])
                        except ClientError:
                            pass  # May already be stopping

                        # Wait for crawler to stop
                        max_wait = 60  # seconds
                        waited = 0
                        while waited < max_wait:
                            time.sleep(5)
                            waited += 5
                            check_response = glue_client.get_crawler(Name=crawler["name"])
                            current_state = check_response["Crawler"]["State"]
                            if current_state == "READY":
                                print(f"    Crawler stopped")
                                break
                            print(f"    Waiting for crawler to stop ({current_state})...")

                    # Update the crawler with Delta targets
                    glue_client.update_crawler(
                        Name=crawler["name"],
                        Role=GLUE_ROLE,
                        DatabaseName=DATABASE_NAME,
                        Description=crawler["description"],
                        Targets={
                            "DeltaTargets": [
                                {
                                    "DeltaTables": [crawler["path"]],
                                    "WriteManifest": True,
                                }
                            ]
                        },
                        TablePrefix=crawler["prefix"],
                        SchemaChangePolicy={
                            "UpdateBehavior": "UPDATE_IN_DATABASE",
                            "DeleteBehavior": "LOG",
                        },
                        Schedule=crawler["schedule"],
                        Configuration=str(delta_config).replace("'", '"'),
                    )
                    print("    Status: Updated to Delta Lake format")
                else:
                    print(f"  - {crawler['name']} → {crawler['path']}")
                    print("    Status: Already exists (Delta Lake format)")
                created_crawlers.append(crawler["name"])
            elif e.response["Error"]["Code"] == "InvalidInputException":
                error_msg = str(e)
                if "TrustPolicy" in error_msg or "assume" in error_msg.lower():
                    print(f"  - {crawler['name']}: IAM role trust policy issue")
                    print(
                        f"    The role '{GLUE_ROLE}' needs a trust policy allowing glue.amazonaws.com"
                    )
                    print("    Run this command to fix:")
                    print(f"""
    aws iam update-assume-role-policy --role-name {GLUE_ROLE} \\
      --policy-document '{{
        "Version": "2012-10-17",
        "Statement": [{{
          "Effect": "Allow",
          "Principal": {{"Service": "glue.amazonaws.com"}},
          "Action": "sts:AssumeRole"
        }}]
      }}'
""")
                else:
                    print(f"  Error creating crawler {crawler['name']}: {e}")
                    raise
            else:
                print(f"  Error creating crawler {crawler['name']}: {e}")
                raise

    print(f"\n  Status: {len(created_crawlers)} crawlers ready")
    return created_crawlers


# ============================================
# STEP 3: RUN CRAWLERS
# ============================================
def run_crawlers(glue_client, crawler_names, wait_for_completion=True):
    """
    Start each crawler for initial schema discovery.

    Args:
        glue_client: Boto3 Glue client
        crawler_names: List of crawler names to run
        wait_for_completion: If True, wait for crawlers to complete
    """
    print("\n" + "=" * 60)
    print("Step 3: Initial Crawler Run")
    print("=" * 60)

    started_crawlers = []

    for crawler_name in crawler_names:
        try:
            glue_client.start_crawler(Name=crawler_name)
            print(f"  Started: {crawler_name}")
            started_crawlers.append(crawler_name)

        except ClientError as e:
            if e.response["Error"]["Code"] == "CrawlerRunningException":
                print(f"  {crawler_name}: Already running")
                started_crawlers.append(crawler_name)
            else:
                print(f"  Error starting crawler {crawler_name}: {e}")

    if wait_for_completion and started_crawlers:
        print("\n  Waiting for crawlers to complete...")
        wait_for_crawlers(glue_client, started_crawlers)

    return started_crawlers


def wait_for_crawlers(glue_client, crawler_names, timeout_minutes=30):
    """
    Wait for all crawlers to complete.

    Args:
        glue_client: Boto3 Glue client
        crawler_names: List of crawler names to wait for
        timeout_minutes: Maximum time to wait
    """
    start_time = time.time()
    timeout_seconds = timeout_minutes * 60

    while True:
        all_complete = True
        for crawler_name in crawler_names:
            try:
                response = glue_client.get_crawler(Name=crawler_name)
                state = response["Crawler"]["State"]

                if state in ["RUNNING", "STOPPING"]:
                    all_complete = False
                    print(f"    {crawler_name}: {state}")

            except ClientError as e:
                print(f"    Error checking crawler {crawler_name}: {e}")

        if all_complete:
            print("\n  All crawlers completed!")
            break

        if time.time() - start_time > timeout_seconds:
            print(f"\n  Timeout after {timeout_minutes} minutes")
            break

        time.sleep(30)  # Check every 30 seconds

    # Print tables created
    print_created_tables(glue_client)


def print_created_tables(glue_client):
    """Print tables created by crawlers."""
    print("\n  Tables Created:")

    try:
        response = glue_client.get_tables(DatabaseName=DATABASE_NAME)
        tables = response.get("TableList", [])

        bronze_tables = [t["Name"] for t in tables if t["Name"].startswith("bronze_")]
        silver_tables = [t["Name"] for t in tables if t["Name"].startswith("silver_")]
        gold_tables = [t["Name"] for t in tables if t["Name"].startswith("gold_")]

        if bronze_tables:
            print(f"    Bronze: {', '.join(bronze_tables)}")
        if silver_tables:
            print(f"    Silver: {', '.join(silver_tables)}")
        if gold_tables:
            print(f"    Gold: {', '.join(gold_tables)}")

        if not tables:
            print("    No tables found (crawlers may still be running)")

    except ClientError as e:
        print(f"    Error listing tables: {e}")


# ============================================
# STEP 4: ADD GOVERNANCE + LINEAGE METADATA
# ============================================
def add_governance_lineage_metadata(glue_client):
    """
    Add governance and lineage metadata to all tables.

    Governance metadata:
    - data_owner: Team/person responsible for the data
    - domain: Business domain classification
    - classification: Data sensitivity level
    - pii_flag: Whether table contains PII
    - retention_days: Data retention period
    - data_zone: Bronze/Silver/Gold zone

    Lineage metadata:
    - source_tables: Upstream tables this table depends on
    - derived_from: Source system or file
    - transformation_job: Job that creates this table
    - downstream_tables: Tables that depend on this table
    - lineage_updated: Timestamp of last lineage update
    """
    print("\n" + "=" * 60)
    print("Step 4: Governance + Lineage Metadata")
    print("=" * 60)

    updated_tables = []
    not_found_tables = []

    for table_name, properties in TABLE_METADATA.items():
        try:
            # Get current table definition
            response = glue_client.get_table(
                DatabaseName=DATABASE_NAME, Name=table_name
            )
            table = response["Table"]

            # Update lineage_updated timestamp
            properties["lineage_updated"] = datetime.now(timezone.utc).isoformat()

            # Merge with existing parameters
            current_params = table.get("Parameters", {})
            current_params.update(properties)

            # Prepare table input (required fields only)
            table_input = {
                "Name": table_name,
                "Parameters": current_params,
                "StorageDescriptor": table["StorageDescriptor"],
            }

            # Add optional fields if present
            if "TableType" in table:
                table_input["TableType"] = table["TableType"]
            if "PartitionKeys" in table:
                table_input["PartitionKeys"] = table["PartitionKeys"]

            # Update table
            glue_client.update_table(DatabaseName=DATABASE_NAME, TableInput=table_input)

            print(f"  Updated: {table_name}")
            print(f"    - data_owner: {properties.get('data_owner', 'N/A')}")
            print(f"    - data_zone: {properties.get('data_zone', 'N/A')}")
            print(
                f"    - source_tables: {properties.get('source_tables', 'N/A') or '(external source)'}"
            )
            print(
                f"    - downstream_tables: {properties.get('downstream_tables', 'N/A') or '(end of pipeline)'}"
            )
            updated_tables.append(table_name)

        except ClientError as e:
            if e.response["Error"]["Code"] == "EntityNotFoundException":
                print(
                    f"  Not found: {table_name} (crawler may not have created it yet)"
                )
                not_found_tables.append(table_name)
            else:
                print(f"  Error updating {table_name}: {e}")

    print("\n  Summary:")
    print(f"    Tables updated: {len(updated_tables)}")
    print(f"    Tables not found: {len(not_found_tables)}")

    return updated_tables, not_found_tables


# ============================================
# STEP 5: VERIFY CRAWLER SCHEDULES
# ============================================
def verify_crawler_schedules(glue_client):
    """
    Verify that crawlers are scheduled correctly.

    Schedules:
    - bronze_crawler: Daily at 6 AM UTC
    - silver_crawler: Daily at 7 AM UTC
    - gold_crawler: Daily at 8 AM UTC
    """
    print("\n" + "=" * 60)
    print("Step 5: Crawler Schedules")
    print("=" * 60)

    for crawler in CRAWLERS:
        try:
            response = glue_client.get_crawler(Name=crawler["name"])
            schedule = (
                response["Crawler"]
                .get("Schedule", {})
                .get("ScheduleExpression", "Not scheduled")
            )
            state = response["Crawler"]["State"]

            # Parse cron expression for human-readable format
            schedule_desc = parse_cron_schedule(schedule)

            print(f"  - {crawler['name']}")
            print(f"    Schedule: {schedule_desc}")
            print(f"    State: {state}")

        except ClientError as e:
            print(f"  - {crawler['name']}: Error - {e}")


def parse_cron_schedule(cron_expr):
    """Parse cron expression to human-readable format."""
    if "cron(0 6" in cron_expr:
        return "Daily at 6 AM UTC"
    elif "cron(0 7" in cron_expr:
        return "Daily at 7 AM UTC"
    elif "cron(0 8" in cron_expr:
        return "Daily at 8 AM UTC"
    else:
        return cron_expr


# ============================================
# SUMMARY
# ============================================
def print_summary():
    """Print final summary of the setup."""
    print("\n" + "=" * 60)
    print("=== GLUE CATALOG & CRAWLER SETUP COMPLETE ===")
    print("=" * 60)

    print(f"""
Step 1: Database Creation
  Database: {DATABASE_NAME}
  Location: s3://{S3_BUCKET}/
  Status: Created

Step 2: Crawler Creation
  - bronze_crawler → s3://{S3_BUCKET}/bronze/
  - silver_crawler → s3://{S3_BUCKET}/silver/
  - gold_crawler → s3://{S3_BUCKET}/gold/
  Status: All Created

Step 3: Initial Crawler Run
  Tables Created:
    Bronze: bronze_yellow_tripdata, bronze_taxi_zones
    Silver: silver_trips_cleaned, silver_zones_cleaned, silver_trips_enriched
    Gold: gold_taxi_zones_master, gold_trip_metrics (consolidated fact table)

Step 4: Governance + Lineage Metadata Added
  All tables updated with:
    - Governance: data_owner, domain, classification, data_zone
    - Lineage: source_tables, transformation_job, downstream_tables

Step 5: Crawlers Scheduled
  - bronze_crawler: Daily at 6 AM UTC
  - silver_crawler: Daily at 7 AM UTC
  - gold_crawler: Daily at 8 AM UTC
""")


# ============================================
# MAIN EXECUTION
# ============================================
def main():
    """Main execution function."""
    print("\n" + "=" * 60)
    print("Day 7 Task 7.5: AWS Glue Catalog & Crawler Setup with Lineage")
    print("=" * 60)

    # Initialize clients
    glue_client = create_glue_client()
    iam_client = create_iam_client()

    # Track setup status
    setup_status = {
        "iam_role_created": False,
        "database_created": False,
        "crawlers_created": [],
        "crawlers_started": [],
        "tables_updated": [],
        "tables_not_found": [],
    }

    try:
        # Step 0: Create IAM role for Glue (if it doesn't exist)
        setup_status["iam_role_created"] = create_glue_service_role(iam_client)

        if not setup_status["iam_role_created"]:
            print("\n  Cannot proceed without IAM role. Exiting.")
            sys.exit(1)

        # Step 1: Create database
        setup_status["database_created"] = create_database(glue_client)

        # Step 2: Create crawlers for each zone
        crawler_names = create_crawlers(glue_client)
        setup_status["crawlers_created"] = crawler_names

        # Step 3: Run crawlers (initial run)
        # Note: In production, you might want to set wait_for_completion=True
        # For demo purposes, we'll start them and continue
        if crawler_names:
            started = run_crawlers(
                glue_client, crawler_names, wait_for_completion=False
            )
            setup_status["crawlers_started"] = started

            # Step 4: Add governance + lineage metadata
            # Note: This may fail for some tables if crawlers haven't completed
            print(
                "\n  Note: Waiting 10 seconds for crawlers to create initial tables..."
            )
            time.sleep(10)
            updated, not_found = add_governance_lineage_metadata(glue_client)
            setup_status["tables_updated"] = updated
            setup_status["tables_not_found"] = not_found

            # Step 5: Verify crawler schedules
            verify_crawler_schedules(glue_client)
        else:
            print("\n  Skipping Steps 3-5 (no crawlers created)")

        # Print final summary based on actual status
        print_dynamic_summary(setup_status)

    except Exception as e:
        print(f"\nError during setup: {e}")
        sys.exit(1)


def print_dynamic_summary(status):
    """Print summary based on actual setup status."""
    print("\n" + "=" * 60)
    print("=== SETUP SUMMARY ===")
    print("=" * 60)

    # IAM Role status
    iam_status = "Created/Exists" if status.get("iam_role_created") else "Failed"
    print("\nStep 0: IAM Role Creation")
    print(f"  Role: {GLUE_ROLE}")
    print(f"  Status: {iam_status}")

    # Database status
    db_status = "Created/Exists" if status["database_created"] else "Failed"
    print("\nStep 1: Database Creation")
    print(f"  Database: {DATABASE_NAME}")
    print(f"  Status: {db_status}")

    # Crawler status
    print("\nStep 2: Crawler Creation")
    if status["crawlers_created"]:
        for crawler in status["crawlers_created"]:
            print(f"  - {crawler}: Created/Exists")
    else:
        print("  No crawlers created (IAM role issue - see instructions above)")

    # Crawler run status
    print("\nStep 3: Crawler Execution")
    if status["crawlers_started"]:
        for crawler in status["crawlers_started"]:
            print(f"  - {crawler}: Started")
    else:
        print("  No crawlers started")

    # Metadata status
    print("\nStep 4: Governance + Lineage Metadata")
    print(f"  Tables updated: {len(status['tables_updated'])}")
    print(f"  Tables not found: {len(status['tables_not_found'])}")

    # Overall status
    print("\n" + "-" * 60)
    if status["crawlers_created"]:
        print("Setup completed successfully!")
        if status["tables_not_found"]:
            print("\nNote: Some tables were not found. Run this script again")
            print("after crawlers have completed to add metadata to all tables.")
    else:
        print("Setup partially completed.")
        print("\nAction Required: Create the IAM role using the commands above,")
        print("then run this script again to complete the setup.")


if __name__ == "__main__":
    main()
