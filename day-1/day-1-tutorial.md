# Day 1: AWS Fundamentals & Environment Setup

## Table of Contents

- [Introduction \& Learning Objectives](#introduction--learning-objectives)
- [Part 1: Introduction to Cloud Computing \& AWS](#part-1-introduction-to-cloud-computing--aws)
- [Part 2: Core AWS Services for Data Engineering](#part-2-core-aws-services-for-data-engineering)
- [Part 3: AWS Account Setup](#part-3-aws-account-setup)
- [Part 4: AWS CLI Installation \& Configuration](#part-4-aws-cli-installation--configuration)
- [Part 5: AWS Console Navigation](#part-5-aws-console-navigation)
- [Part 6: Hands-on Labs](#part-6-hands-on-labs)
- [Summary \& Key Takeaways](#summary--key-takeaways)
- [Additional Resources](#additional-resources)

---

## Introduction & Learning Objectives

### Overview

Day 1 focuses on understanding **AWS fundamentals** and setting up your **development environment**. As a data engineer, AWS will be your primary cloud platform for building scalable data pipelines, data lakes, and analytics solutions.

```mermaid
%%{init: {'theme':'neutral'}}%%
flowchart LR
    subgraph Journey["Your Data Engineering Journey"]
        D1["Day 1<br/>AWS Fundamentals"]
        D2["Day 2<br/>Python & Boto3"]
        D3["Day 3<br/>Data Modeling"]
        D4["Day 4<br/>ETL Pipelines"]
        D5["Day 5<br/>Analytics"]
    end

    D1 --> D2 --> D3 --> D4 --> D5

    style D1 fill:#74c0fc,color:#000
    style D2 fill:#868e96,color:#000
    style D3 fill:#868e96,color:#000
    style D4 fill:#868e96,color:#000
    style D5 fill:#868e96,color:#000
```

### Prerequisites

Before starting Day 1, ensure you have:

- ✅ A computer with internet access
- ✅ A valid email address (for AWS account)
- ✅ A credit/debit card (for AWS account verification - won't be charged for free tier usage)
- ✅ Basic understanding of command-line operations
- ✅ Willingness to learn!

### Learning Objectives

By the end of Day 1, you will be able to:

1. **Explain cloud computing concepts** and AWS's role in data engineering
2. **Identify key AWS services** used in data engineering workflows
3. **Create and secure an AWS account** with proper IAM configuration
4. **Install and configure AWS CLI** for programmatic access
5. **Navigate the AWS Console** to manage resources
6. **Create your first S3 bucket** using both console and CLI

---

## Part 1: Introduction to Cloud Computing & AWS

### 1.1 What is Cloud Computing?

Cloud computing is the delivery of computing services—servers, storage, databases, networking, software, and analytics—over the internet ("the cloud").

```mermaid
%%{init: {'theme':'neutral'}}%%
flowchart TB
    subgraph Traditional["Traditional (On-Premise)"]
        T1["Buy Hardware"]
        T2["Setup Data Center"]
        T3["Maintain Servers"]
        T4["Scale Manually"]
    end

    subgraph Cloud["Cloud Computing"]
        C1["Pay-as-you-go"]
        C2["Instant Provisioning"]
        C3["Managed Services"]
        C4["Auto-scaling"]
    end

    style T1 fill:#ff6b6b,color:#000
    style T2 fill:#ff6b6b,color:#000
    style T3 fill:#ff6b6b,color:#000
    style T4 fill:#ff6b6b,color:#000
    style C1 fill:#51cf66,color:#000
    style C2 fill:#51cf66,color:#000
    style C3 fill:#51cf66,color:#000
    style C4 fill:#51cf66,color:#000
```

#### Key Benefits of Cloud Computing

| Benefit | Description |
|---------|-------------|
| **Cost Efficiency** | Pay only for what you use, no upfront hardware costs |
| **Scalability** | Scale up or down based on demand instantly |
| **Reliability** | Built-in redundancy and disaster recovery |
| **Speed** | Provision resources in minutes, not weeks |
| **Global Reach** | Deploy applications worldwide easily |
| **Security** | Enterprise-grade security managed by cloud providers |

### 1.2 Cloud Service Models

```mermaid
%%{init: {'theme':'neutral'}}%%
flowchart TB
    subgraph Models["Cloud Service Models"]
        subgraph IaaS["IaaS<br/>Infrastructure as a Service"]
            I1["Virtual Machines"]
            I2["Storage"]
            I3["Networking"]
        end

        subgraph PaaS["PaaS<br/>Platform as a Service"]
            P1["Databases"]
            P2["Development Tools"]
            P3["Analytics Platforms"]
        end

        subgraph SaaS["SaaS<br/>Software as a Service"]
            S1["Applications"]
            S2["Email"]
            S3["CRM"]
        end
    end

    style I1 fill:#74c0fc,color:#000
    style I2 fill:#74c0fc,color:#000
    style I3 fill:#74c0fc,color:#000
    style P1 fill:#51cf66,color:#000
    style P2 fill:#51cf66,color:#000
    style P3 fill:#51cf66,color:#000
    style S1 fill:#ffd43b,color:#000
    style S2 fill:#ffd43b,color:#000
    style S3 fill:#ffd43b,color:#000
```

> **Understanding the Acronyms:**
> - **IaaS (Infrastructure as a Service)**: You rent the basic building blocks (servers, storage, networking) and manage everything else yourself
> - **PaaS (Platform as a Service)**: You get a platform to build and deploy applications without managing the underlying infrastructure
> - **SaaS (Software as a Service)**: You use ready-made software applications over the internet

| Model | You Manage | Provider Manages | AWS Examples |
|-------|-----------|-----------------|--------------|
| **IaaS** | Apps, Data, Runtime, OS | Virtualization, Servers, Storage, Networking | EC2, VPC, EBS |
| **PaaS** | Apps, Data | Runtime, OS, Virtualization, Servers | RDS, Elastic Beanstalk, Lambda |
| **SaaS** | Nothing (just use it) | Everything | Amazon WorkMail, Amazon Chime |

### 1.3 AWS Global Infrastructure

AWS operates a massive global infrastructure designed for reliability and low latency.

```mermaid
%%{init: {'theme':'neutral'}}%%
flowchart TB
    subgraph Global["AWS Global Infrastructure"]
        subgraph Region1["Region: us-east-1 (N. Virginia)"]
            AZ1["Availability Zone 1a"]
            AZ2["Availability Zone 1b"]
            AZ3["Availability Zone 1c"]
        end

        subgraph Region2["Region: eu-west-1 (Ireland)"]
            AZ4["Availability Zone 1a"]
            AZ5["Availability Zone 1b"]
            AZ6["Availability Zone 1c"]
        end

        Edge["Edge Locations (CloudFront)"]
    end

    Region1 <--> Region2
    Edge --> Region1
    Edge --> Region2

    style AZ1 fill:#74c0fc,color:#000
    style AZ2 fill:#74c0fc,color:#000
    style AZ3 fill:#74c0fc,color:#000
    style AZ4 fill:#51cf66,color:#000
    style AZ5 fill:#51cf66,color:#000
    style AZ6 fill:#51cf66,color:#000
    style Edge fill:#ffd43b,color:#000
```

#### Key Concepts

| Concept | Description | Example |
|---------|-------------|---------|
| **Region** | Geographic area with multiple data centers | us-east-1 (N. Virginia), ap-south-1 (Mumbai) |
| **Availability Zone (AZ)** | Isolated data centers within a region | us-east-1a, us-east-1b |
| **Edge Location** | CDN endpoints for low-latency content delivery | 400+ locations worldwide |

#### Choosing a Region

Consider these factors when selecting a region:

1. **Latency**: Choose a region close to your users
2. **Compliance**: Some data must stay in specific countries
3. **Service Availability**: Not all services are available in all regions
4. **Cost**: Pricing varies by region

---

## Part 2: Core AWS Services for Data Engineering

### 2.1 AWS Service Categories

```mermaid
%%{init: {'theme':'neutral'}}%%
flowchart TB
    subgraph AWS["AWS Services for Data Engineering"]
        subgraph Storage["Storage"]
            S3["S3<br/>Object Storage"]
            EBS["EBS<br/>Block Storage"]
        end

        subgraph Compute["Compute"]
            EC2["EC2<br/>Virtual Machines"]
            Lambda["Lambda<br/>Serverless"]
        end

        subgraph Database["Database"]
            RDS["RDS<br/>Relational DB"]
            DynamoDB["DynamoDB<br/>NoSQL"]
            Redshift["Redshift<br/>Data Warehouse"]
        end

        subgraph Analytics["Analytics"]
            Glue["Glue<br/>ETL Service"]
            Athena["Athena<br/>SQL Queries"]
            EMR["EMR<br/>Big Data"]
        end

        subgraph Integration["Integration"]
            Kinesis["Kinesis<br/>Streaming"]
            SQS["SQS<br/>Message Queue"]
            SNS["SNS<br/>Notifications"]
        end
    end

    style S3 fill:#74c0fc,color:#000
    style EBS fill:#74c0fc,color:#000
    style EC2 fill:#51cf66,color:#000
    style Lambda fill:#51cf66,color:#000
    style RDS fill:#ffd43b,color:#000
    style DynamoDB fill:#ffd43b,color:#000
    style Redshift fill:#ffd43b,color:#000
    style Glue fill:#da77f2,color:#000
    style Athena fill:#da77f2,color:#000
    style EMR fill:#da77f2,color:#000
    style Kinesis fill:#ff6b6b,color:#000
    style SQS fill:#ff6b6b,color:#000
    style SNS fill:#ff6b6b,color:#000
```

### 2.2 Amazon S3 (Simple Storage Service)

S3 is the cornerstone of data engineering on AWS. It's an object storage service that offers scalability, data availability, security, and performance.

#### Key Concepts

| Concept | Description |
|---------|-------------|
| **Bucket** | Container for objects (like a folder) |
| **Object** | File + metadata stored in a bucket |
| **Key** | Unique identifier for an object within a bucket |
| **Region** | Geographic location where bucket is stored |

#### S3 Storage Classes

| Storage Class | Use Case | Availability | Cost |
|---------------|----------|--------------|------|
| **S3 Standard** | Frequently accessed data | 99.99% | $$$ |
| **S3 Standard-IA** | Infrequently accessed data | 99.9% | $$ |
| **S3 One Zone-IA** | Non-critical, infrequent access | 99.5% | $ |
| **S3 Glacier Instant Retrieval** | Archive data with milliseconds retrieval | 99.9% | $ |
| **S3 Glacier Flexible Retrieval** | Archive data (minutes to 12 hours retrieval) | 99.99% | $ |
| **S3 Glacier Deep Archive** | Long-term archive (12-48 hours retrieval) | 99.99% | ¢ |

#### Data Lake Architecture

```mermaid
%%{init: {'theme':'neutral'}}%%
flowchart LR
    subgraph Sources["Data Sources"]
        SRC1["Applications"]
        SRC2["Databases"]
        SRC3["IoT Devices"]
        SRC4["Third-party APIs"]
    end

    subgraph DataLake["S3 Data Lake"]
        RAW["Raw Layer<br/>(Landing Zone)"]
        PROC["Processed Layer<br/>(Cleaned Data)"]
        CURATED["Curated Layer<br/>(Business Ready)"]
    end

    subgraph Consumers["Data Consumers"]
        BI["BI Tools"]
        ML["ML Models"]
        APPS["Applications"]
    end

    Sources --> RAW
    RAW --> PROC
    PROC --> CURATED
    CURATED --> Consumers

    style RAW fill:#74c0fc,color:#000
    style PROC fill:#51cf66,color:#000
    style CURATED fill:#ffd43b,color:#000
```

### 2.3 Amazon EC2 (Elastic Compute Cloud)

EC2 provides resizable compute capacity in the cloud. It's used for running applications, processing data, and hosting services.

#### Instance Types

| Family | Use Case | Examples |
|--------|----------|----------|
| **General Purpose (t3, m5)** | Balanced compute, memory, networking | Web servers, dev environments |
| **Compute Optimized (c5)** | High-performance processors | Batch processing, gaming |
| **Memory Optimized (r5)** | Large datasets in memory | In-memory databases, big data |
| **Storage Optimized (i3)** | High sequential read/write | Data warehousing, log processing |

### 2.4 AWS Lambda

Lambda is a serverless compute service that runs code in response to events. You don't manage servers—just upload your code.

#### Key Features

- **Event-driven**: Triggered by S3 uploads, API calls, schedules, etc.
- **Pay-per-use**: Charged only when code runs (per millisecond)
- **Auto-scaling**: Handles from 0 to thousands of requests
- **Languages**: Python, Node.js, Java, Go, .NET, Ruby

```mermaid
%%{init: {'theme':'neutral'}}%%
flowchart LR
    subgraph Triggers["Event Sources"]
        S3["S3 Upload"]
        API["API Gateway"]
        CRON["CloudWatch Events"]
    end

    Lambda["Lambda Function"]

    subgraph Actions["Output"]
        DB["Write to RDS"]
        NOTIFY["Send SNS"]
        STORE["Store in S3"]
    end

    Triggers --> Lambda --> Actions

    style Lambda fill:#74c0fc,color:#000
    style S3 fill:#51cf66,color:#000
    style API fill:#51cf66,color:#000
    style CRON fill:#51cf66,color:#000
```

### 2.5 Amazon RDS (Relational Database Service)

RDS is a managed relational database service supporting multiple database engines.

#### Supported Engines

| Engine | Description |
|--------|-------------|
| **Amazon Aurora** | AWS cloud-native, MySQL/PostgreSQL compatible |
| **PostgreSQL** | Open-source, feature-rich |
| **MySQL** | Popular open-source database |
| **MariaDB** | MySQL fork with enhancements |
| **Oracle** | Enterprise database |
| **SQL Server** | Microsoft's database |

### 2.6 AWS Glue

Glue is a fully managed ETL (Extract, Transform, Load) service for preparing and transforming data.

#### Components

| Component | Description |
|-----------|-------------|
| **Data Catalog** | Central metadata repository |
| **Crawlers** | Auto-discover data schema |
| **ETL Jobs** | Spark-based data transformations |
| **Connections** | Connect to data sources |

### 2.7 Amazon Athena

Athena is a serverless query service that lets you analyze data in S3 using standard SQL.

```mermaid
%%{init: {'theme':'neutral'}}%%
flowchart LR
    User["Data Analyst"]
    Athena["Amazon Athena"]
    S3["S3 Data Lake"]
    Catalog["Glue Data Catalog"]

    User -->|SQL Query| Athena
    Athena -->|Read Schema| Catalog
    Athena -->|Scan Data| S3
    Athena -->|Results| User

    style Athena fill:#74c0fc,color:#000
    style S3 fill:#51cf66,color:#000
    style Catalog fill:#ffd43b,color:#000
```

### 2.8 Service Interaction Example

Here's how these services work together in a typical data pipeline:

```mermaid
%%{init: {'theme':'neutral'}}%%
flowchart TB
    subgraph Ingest["Data Ingestion"]
        SRC["Source Systems"]
        KINESIS["Kinesis"]
    end

    subgraph Store["Storage"]
        S3RAW["S3 Raw"]
        S3PROC["S3 Processed"]
    end

    subgraph Process["Processing"]
        GLUE["AWS Glue"]
        LAMBDA["Lambda"]
    end

    subgraph Serve["Serving"]
        ATHENA["Athena"]
        REDSHIFT["Redshift"]
        RDS["RDS"]
    end

    subgraph Consume["Consumers"]
        BI["BI Dashboards"]
        ML["ML Models"]
    end

    SRC --> KINESIS --> S3RAW
    S3RAW --> GLUE --> S3PROC
    S3RAW --> LAMBDA --> S3PROC
    S3PROC --> ATHENA --> BI
    S3PROC --> REDSHIFT --> BI
    S3PROC --> RDS --> ML

    style S3RAW fill:#74c0fc,color:#000
    style S3PROC fill:#51cf66,color:#000
    style GLUE fill:#da77f2,color:#000
    style ATHENA fill:#ffd43b,color:#000
```

---

## Part 3: AWS Account Setup

### 3.1 Creating an AWS Account

#### Step-by-Step Guide

1. **Go to AWS** - Navigate to [aws.amazon.com](https://aws.amazon.com)
2. **Click "Create an AWS Account"**
3. **Enter account details**:
   - Email address (root user email)
   - AWS account name
   - Password
4. **Choose account type**: Personal or Professional
5. **Enter contact information**
6. **Add payment method** (credit/debit card for verification)
7. **Verify identity** (phone/text verification)
8. **Select support plan**: Choose "Basic Support - Free"
9. **Complete signup**

> ⚠️ **Important**: The email you use becomes the "root user" - the most powerful account. Protect it carefully!

### 3.2 AWS Free Tier

AWS offers a Free Tier with three types of offers:

| Type | Description | Examples |
|------|-------------|----------|
| **Always Free** | Never expires | Lambda (1M requests/month), DynamoDB (25GB) |
| **12 Months Free** | Free for 12 months after signup | EC2 (750 hrs/month), S3 (5GB), RDS (750 hrs/month) |
| **Trials** | Short-term trials | Redshift (2 months), QuickSight (30 days) |

#### Free Tier Limits for Data Engineering

| Service | Free Tier Allowance |
|---------|---------------------|
| **Amazon S3** | 5 GB storage, 20,000 GET, 2,000 PUT requests |
| **AWS Lambda** | 1 million requests, 400,000 GB-seconds compute |
| **Amazon RDS** | 750 hours/month (db.t2.micro or db.t3.micro) |
| **Amazon DynamoDB** | 25 GB storage, 25 read/write capacity units |
| **AWS Glue** | 1 million objects in Data Catalog |

### 3.3 Understanding IAM (Identity and Access Management)

IAM controls who can access your AWS resources and what they can do.

```mermaid
%%{init: {'theme':'neutral'}}%%
flowchart TB
    subgraph IAM["IAM Components"]
        ROOT["Root User<br/>(Account Owner)"]
        USERS["IAM Users<br/>(People)"]
        GROUPS["IAM Groups<br/>(Collections of Users)"]
        ROLES["IAM Roles<br/>(For Services/Apps)"]
        POLICIES["IAM Policies<br/>(Permissions)"]
    end

    ROOT --> USERS
    USERS --> GROUPS
    POLICIES --> USERS
    POLICIES --> GROUPS
    POLICIES --> ROLES

    style ROOT fill:#ff6b6b,color:#000
    style USERS fill:#74c0fc,color:#000
    style GROUPS fill:#51cf66,color:#000
    style ROLES fill:#ffd43b,color:#000
    style POLICIES fill:#da77f2,color:#000
```

#### IAM Best Practices

| Practice | Description |
|----------|-------------|
| **Never use root user** | Create IAM users for daily tasks |
| **Enable MFA** | Multi-factor authentication for all users |
| **Least privilege** | Grant minimum permissions needed |
| **Use groups** | Assign permissions to groups, not individual users |
| **Rotate credentials** | Regularly change access keys |
| **Use roles for services** | EC2, Lambda should use roles, not access keys |

### 3.4 Setting Up IAM Users

#### Creating an Admin User

1. Sign in to AWS Console as root user
2. Go to **IAM** service
3. Click **Users** → **Add users**
4. Enter username (e.g., `admin-user`)
5. Select **AWS Management Console access**
6. Set a password
7. Click **Next: Permissions**
8. Select **Attach existing policies directly**
9. Search and select **AdministratorAccess**
10. Click **Next** → **Create user**
11. Save the sign-in URL and credentials

#### Creating a Data Engineer User

For day-to-day work, create a user with limited permissions:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "S3FullAccess",
            "Effect": "Allow",
            "Action": "s3:*",
            "Resource": "*"
        },
        {
            "Sid": "GlueFullAccess",
            "Effect": "Allow",
            "Action": "glue:*",
            "Resource": "*"
        },
        {
            "Sid": "AthenaFullAccess",
            "Effect": "Allow",
            "Action": "athena:*",
            "Resource": "*"
        },
        {
            "Sid": "LambdaFullAccess",
            "Effect": "Allow",
            "Action": "lambda:*",
            "Resource": "*"
        }
    ]
}
```

### 3.5 Enabling MFA (Multi-Factor Authentication)

MFA adds an extra layer of security to your AWS account.

#### Steps to Enable MFA

1. Go to **IAM** → **Users** → Select your user
2. Click **Security credentials** tab
3. Under **Multi-factor authentication (MFA)**, click **Manage**
4. Select **Virtual MFA device**
5. Use an authenticator app (Google Authenticator, Authy, etc.)
6. Scan the QR code
7. Enter two consecutive MFA codes
8. Click **Assign MFA**

---

## Part 4: AWS CLI Installation & Configuration

### 4.1 What is AWS CLI?

AWS CLI (Command Line Interface) is a unified tool to manage AWS services from the command line.

```mermaid
%%{init: {'theme':'neutral'}}%%
flowchart LR
    subgraph Local["Your Computer"]
        Terminal["Terminal/CMD"]
        CLI["AWS CLI"]
        Creds["~/.aws/credentials"]
    end

    subgraph AWS["AWS Cloud"]
        API["AWS APIs"]
        Services["AWS Services"]
    end

    Terminal --> CLI
    CLI --> Creds
    CLI -->|HTTPS| API
    API --> Services

    style CLI fill:#74c0fc,color:#000
    style Creds fill:#ffd43b,color:#000
    style API fill:#51cf66,color:#000
```

### 4.2 Installing AWS CLI

#### macOS

```bash
# Using Homebrew (recommended)
brew install awscli

# Or download the installer
curl "https://awscli.amazonaws.com/AWSCLIV2.pkg" -o "AWSCLIV2.pkg"
sudo installer -pkg AWSCLIV2.pkg -target /
```

#### Windows

1. Download the installer from: https://awscli.amazonaws.com/AWSCLIV2.msi
2. Run the downloaded MSI installer
3. Follow the installation wizard

#### Linux

```bash
# Download the installer
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"

# Unzip
unzip awscliv2.zip

# Install
sudo ./aws/install
```

#### Verify Installation

```bash
aws --version
# Output: aws-cli/2.x.x Python/3.x.x Darwin/x86_64 source/x86_64
```

### 4.3 Creating Access Keys

Access keys are used for programmatic access to AWS.

#### Steps to Create Access Keys

1. Sign in to AWS Console
2. Go to **IAM** → **Users** → Select your user
3. Click **Security credentials** tab
4. Under **Access keys**, click **Create access key**
5. Select **Command Line Interface (CLI)**
6. Check the acknowledgment box
7. Click **Create access key**
8. **Download the .csv file** or copy both keys

> ⚠️ **Important**: The secret key is only shown once! Store it securely.

### 4.4 Configuring AWS CLI

#### Basic Configuration

```bash
aws configure
```

You'll be prompted for:
```
AWS Access Key ID [None]: AKIAIOSFODNN7EXAMPLE
AWS Secret Access Key [None]: wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
Default region name [None]: us-east-1
Default output format [None]: json
```

#### Configuration Files

AWS CLI stores configuration in two files:

**~/.aws/credentials**
```ini
[default]
aws_access_key_id = AKIAIOSFODNN7EXAMPLE
aws_secret_access_key = wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY

[dev]
aws_access_key_id = AKIAI44QH8DHBEXAMPLE
aws_secret_access_key = je7MtGbClwBF/2Zp9Utk/h3yCo8nvbEXAMPLEKEY
```

**~/.aws/config**
```ini
[default]
region = us-east-1
output = json

[profile dev]
region = us-west-2
output = table
```

#### Using Named Profiles

```bash
# Configure a named profile
aws configure --profile dev

# Use a specific profile
aws s3 ls --profile dev

# Set default profile for session
export AWS_PROFILE=dev
```

### 4.5 Basic AWS CLI Commands

#### Identity and Access

```bash
# Check who you are
aws sts get-caller-identity

# Output:
# {
#     "UserId": "AIDAEXAMPLEID",
#     "Account": "123456789012",
#     "Arn": "arn:aws:iam::123456789012:user/your-username"
# }
```

> **What is an ARN?** An **Amazon Resource Name (ARN)** is a unique identifier for AWS resources. The format is: `arn:partition:service:region:account-id:resource`. ARNs are used in IAM policies, API calls, and anywhere you need to uniquely identify a resource.

#### S3 Commands

```bash
# List all buckets
aws s3 ls

# List contents of a bucket
aws s3 ls s3://bucket-name

# List with details
aws s3 ls s3://bucket-name --recursive --human-readable

# Copy file to S3
aws s3 cp local-file.txt s3://bucket-name/

# Copy file from S3
aws s3 cp s3://bucket-name/file.txt ./local-file.txt

# Sync directory to S3
aws s3 sync ./local-folder s3://bucket-name/prefix/

# Create bucket
aws s3 mb s3://my-new-bucket-name

# Delete bucket (must be empty)
aws s3 rb s3://my-bucket-name

# Delete bucket and all contents
aws s3 rb s3://my-bucket-name --force
```

#### EC2 Commands

```bash
# List EC2 instances
aws ec2 describe-instances

# List running instances
aws ec2 describe-instances --filters "Name=instance-state-name,Values=running"

# Get instance IDs only
aws ec2 describe-instances --query 'Reservations[*].Instances[*].InstanceId' --output text
```

#### Other Useful Commands

```bash
# List available regions
aws ec2 describe-regions --output table

# List IAM users
aws iam list-users

# Get account summary
aws iam get-account-summary
```

---

## Part 5: AWS Console Navigation

### 5.1 Console Overview

The AWS Management Console is a web-based interface for managing AWS services.

#### Key Areas

```mermaid
%%{init: {'theme':'neutral'}}%%
flowchart TB
    subgraph Console["AWS Console Layout"]
        Nav["Navigation Bar<br/>(Search, Region, Account)"]
        Services["Services Menu<br/>(All AWS Services)"]
        Dashboard["Service Dashboard<br/>(Resource Management)"]
        Help["Help Panel<br/>(Documentation)"]
    end

    Nav --> Services
    Services --> Dashboard
    Dashboard --> Help

    style Nav fill:#74c0fc,color:#000
    style Services fill:#51cf66,color:#000
    style Dashboard fill:#ffd43b,color:#000
    style Help fill:#da77f2,color:#000
```

### 5.2 Finding Services

1. **Search Bar**: Type service name (fastest method)
2. **Services Menu**: Click "Services" to see all categories
3. **Recently Visited**: Quick access to recent services
4. **Favorites**: Star services you use frequently

### 5.3 Region Selection

Always check your region before creating resources!

- Region selector is in the top-right corner
- Some services are global (IAM, Route 53, CloudFront)
- Most services are regional (S3 buckets are regional)

### 5.4 Key Service Dashboards

#### S3 Dashboard

- View all buckets
- See storage metrics
- Access bucket settings
- Upload/download objects

#### IAM Dashboard

- Security recommendations
- User/Group/Role management
- Access Analyzer
- Credential reports

#### CloudWatch Dashboard

Amazon CloudWatch is AWS's monitoring and observability service. It collects and tracks metrics, monitors log files, and sets alarms.

**Key CloudWatch Features:**

| Feature | Description | Use Case |
|---------|-------------|----------|
| **Metrics** | Numerical data points about your resources | CPU usage, request counts, latency |
| **Alarms** | Automated actions based on metric thresholds | Alert when CPU > 80% |
| **Logs** | Centralized log collection and analysis | Application debugging, audit trails |
| **Dashboards** | Custom visualizations of metrics | Real-time monitoring displays |
| **Events/EventBridge** | React to changes in AWS resources | Trigger Lambda when S3 upload occurs |

**Common CloudWatch Use Cases for Data Engineering:**
- Monitor Lambda function execution times and errors
- Track S3 bucket request metrics
- Set up alerts for Glue job failures
- Analyze ETL pipeline logs

#### CloudTrail Dashboard

AWS CloudTrail records API calls and account activity across your AWS infrastructure. It's essential for security auditing and compliance.

**Key CloudTrail Features:**

| Feature | Description | Use Case |
|---------|-------------|----------|
| **Event History** | 90 days of management events | Quick lookup of recent API calls |
| **Trails** | Continuous logging to S3 | Long-term audit storage |
| **Insights** | Detect unusual API activity | Security anomaly detection |
| **Log File Integrity** | Verify logs haven't been tampered with | Compliance requirements |

**Why CloudTrail Matters for Data Engineers:**
- Track who accessed or modified S3 buckets
- Audit IAM permission changes
- Investigate data pipeline failures
- Meet compliance requirements (SOC 2, HIPAA, etc.)

### 5.5 Cost Monitoring

#### AWS Budgets

Set up a budget alert to avoid unexpected charges:

1. Go to **Billing and Cost Management**
2. Click **Budgets** → **Create budget**
3. Select **Cost budget**
4. Set budget amount (e.g., $10/month)
5. Configure alerts (e.g., alert at 80% of budget)
6. Enter email for notifications

#### Cost Explorer

- Visualize spending patterns
- Analyze costs by service
- Forecast future costs
- Identify cost optimization opportunities

---

## Part 6: Hands-on Labs

### Lab 1: Create an IAM User

**Objective**: Create an IAM user for data engineering tasks.

#### Steps

1. Sign in to AWS Console as root user
2. Navigate to **IAM** service
3. Click **Users** → **Create user**
4. Enter username: `data-engineer-intern`
5. Select **Provide user access to the AWS Management Console**
6. Select **I want to create an IAM user**
7. Auto-generate or set custom password
8. Click **Next**

**Add Permissions**:

9. Select **Attach policies directly**
10. Search and select these policies:
    - `AmazonS3FullAccess`
    - `AWSGlueConsoleFullAccess`
    - `AmazonAthenaFullAccess`
11. Click **Next** → **Create user**
12. Download or copy the sign-in credentials

**Verification**:

13. Sign out and sign in as the new user
14. Verify you can access S3 service

### Lab 2: Install and Configure AWS CLI

**Objective**: Set up AWS CLI on your local machine.

#### Steps

1. **Install AWS CLI** (use commands from Section 4.2)

2. **Verify installation**:
```bash
aws --version
```

3. **Create access key** for your IAM user (Section 4.3)

4. **Configure AWS CLI**:
```bash
aws configure
```
Enter:
- Access Key ID
- Secret Access Key
- Region: `us-east-1`
- Output format: `json`

5. **Test configuration**:
```bash
aws sts get-caller-identity
```

Expected output:
```json
{
    "UserId": "AIDA...",
    "Account": "123456789012",
    "Arn": "arn:aws:iam::123456789012:user/data-engineer-intern"
}
```

6. **List S3 buckets** (should work, might be empty):
```bash
aws s3 ls
```

### Lab 3: Create Your First S3 Bucket (Console)

**Objective**: Create and configure an S3 bucket using AWS Console.

#### Steps

1. Sign in to AWS Console
2. Navigate to **S3** service
3. Click **Create bucket**
4. **Bucket name**: `your-name-data-lake-learning` (must be globally unique)
5. **Region**: `us-east-1`
6. **Object Ownership**: ACLs disabled (recommended)
7. **Block Public Access**: Keep all boxes checked
8. **Bucket Versioning**: Enable
9. **Default encryption**: Enable with Amazon S3 managed keys (SSE-S3)
   > **What is SSE-S3?** SSE-S3 stands for **Server-Side Encryption with Amazon S3-Managed Keys**. AWS automatically encrypts your data when writing to disk and decrypts it when you read. You don't need to manage encryption keys—AWS handles it all. Other options include SSE-KMS (you manage keys via AWS Key Management Service) and SSE-C (you provide your own keys).
10. Click **Create bucket**

**Upload a Test File**:

11. Click on your new bucket
12. Click **Upload**
13. Add a test file (any small file)
14. Click **Upload**

**Verify**:

15. Navigate to the uploaded object
16. View object details and properties

### Lab 4: S3 Operations with AWS CLI

**Objective**: Perform S3 operations using AWS CLI.

#### Steps

1. **List your buckets**:
```bash
aws s3 ls
```

2. **Create a folder structure**:
```bash
# Create a test file
echo "Hello, Data Engineering!" > test-file.txt

# Upload to S3
aws s3 cp test-file.txt s3://your-name-data-lake-learning/raw/test-file.txt

# List bucket contents
aws s3 ls s3://your-name-data-lake-learning/ --recursive
```

3. **Create folders for data lake structure**:
```bash
# Create empty objects to simulate folders
aws s3api put-object --bucket your-name-data-lake-learning --key raw/
aws s3api put-object --bucket your-name-data-lake-learning --key processed/
aws s3api put-object --bucket your-name-data-lake-learning --key curated/
aws s3api put-object --bucket your-name-data-lake-learning --key reference/
```

4. **Download a file**:
```bash
aws s3 cp s3://your-name-data-lake-learning/raw/test-file.txt ./downloaded-file.txt
cat downloaded-file.txt
```

5. **Sync a local directory**:
```bash
# Create local directory with files
mkdir -p local-data
echo "file 1" > local-data/file1.txt
echo "file 2" > local-data/file2.txt

# Sync to S3
aws s3 sync local-data/ s3://your-name-data-lake-learning/raw/sync-test/

# Verify
aws s3 ls s3://your-name-data-lake-learning/raw/sync-test/
```

6. **Get bucket information**:
```bash
# Get bucket location
aws s3api get-bucket-location --bucket your-name-data-lake-learning

# Get bucket versioning status
aws s3api get-bucket-versioning --bucket your-name-data-lake-learning

# Get bucket encryption
aws s3api get-bucket-encryption --bucket your-name-data-lake-learning
```

### Lab 5: Set Up AWS Budget Alert

**Objective**: Create a budget alert to monitor spending.

#### Steps

1. Navigate to **Billing and Cost Management**
2. Click **Budgets** in the left menu
3. Click **Create budget**
4. Select **Use a template (simplified)**
5. Choose **Zero spend budget** (alerts when any charge occurs)
6. Enter budget name: `Free-Tier-Alert`
7. Enter email recipients
8. Click **Create budget**

**Alternative: Monthly Cost Budget**:

1. Select **Customize (advanced)**
2. Choose **Cost budget**
3. Set budget amount: `$10.00`
4. Set threshold: `80%`
5. Configure email alerts
6. Create budget

---

## Summary & Key Takeaways

### Setup Checklist

- [ ] AWS account created
- [ ] Root user secured with MFA
- [ ] IAM admin user created
- [ ] IAM data engineer user created
- [ ] AWS CLI installed
- [ ] AWS CLI configured with credentials
- [ ] First S3 bucket created
- [ ] Budget alert configured

### Key Concepts Learned

| Concept | Description |
|---------|-------------|
| **Cloud Computing** | On-demand delivery of IT resources over the internet |
| **AWS Regions** | Geographic areas containing multiple data centers |
| **Availability Zones** | Isolated data centers within a region |
| **S3** | Object storage service for data lakes |
| **IAM** | Identity and access management for security |
| **AWS CLI** | Command-line tool for AWS management |
| **Free Tier** | Free usage of AWS services for learning |

### AWS Services Quick Reference

| Service | Purpose | Data Engineering Use |
|---------|---------|---------------------|
| **S3** | Object Storage | Data lake, file storage |
| **EC2** | Virtual Machines | Data processing, hosting |
| **Lambda** | Serverless Compute | Event-driven processing |
| **RDS** | Managed Databases | Operational data stores |
| **Glue** | ETL Service | Data transformation |
| **Athena** | SQL Queries | Data exploration |
| **Redshift** | Data Warehouse | Analytics |
| **Kinesis** | Streaming | Real-time data |

### CLI Commands Quick Reference

```bash
# Identity
aws sts get-caller-identity

# S3 Operations
aws s3 ls                                    # List buckets
aws s3 ls s3://bucket-name                   # List objects
aws s3 cp file.txt s3://bucket/key           # Upload
aws s3 cp s3://bucket/key file.txt           # Download
aws s3 sync ./folder s3://bucket/prefix      # Sync
aws s3 mb s3://bucket-name                   # Create bucket
aws s3 rb s3://bucket-name --force           # Delete bucket

# Configuration
aws configure                                # Set up credentials
aws configure --profile name                 # Named profile
aws configure list                           # Show current config
```

---

## Additional Resources

### Official Documentation

| Resource | Link |
|----------|------|
| **AWS Documentation** | https://docs.aws.amazon.com/ |
| **AWS Free Tier** | https://aws.amazon.com/free/ |
| **IAM Best Practices** | https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html |
| **AWS CLI Reference** | https://docs.aws.amazon.com/cli/latest/reference/ |
| **S3 User Guide** | https://docs.aws.amazon.com/s3/index.html |

### Learning Paths

- **AWS Cloud Practitioner** - Foundational certification
- **AWS Solutions Architect Associate** - Architecture certification
- **AWS Data Analytics Specialty** - Data engineering certification

### Recommended Reading

- **AWS Well-Architected Framework** - Cloud best practices
- **AWS Whitepapers** - Deep dives on specific topics
- **AWS re:Invent Videos** - Conference sessions on YouTube

### Next Steps

1. Complete all hands-on labs
2. Explore the AWS Console and familiarize yourself with different services
3. Practice AWS CLI commands
4. Review IAM policies and understand permissions
5. Prepare for Day 2: Python & AWS SDK (Boto3)

---

*End of Day 1: AWS Fundamentals & Environment Setup*
