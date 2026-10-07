# Self-Service AWS Sandbox Provisioner

A Slack `/sandbox` command that lets developers request a temporary AWS sandbox
(an S3 bucket plus a least-privilege IAM role). A manager approves the request
with a button, a Lambda function creates the resources tagged with the owner and
an expiry time, and a scheduled EventBridge job deletes them when they expire.
Every request is logged in DynamoDB.

**Stack:** Python 3.12, AWS Lambda, API Gateway (HTTP API), DynamoDB, EventBridge,
S3, IAM, Terraform, Jenkins, GitHub, pytest + moto.

## How it works

```
 Developer                 Slack                    AWS
 ─────────                 ─────                    ───
 /sandbox 4 testing ─────► slash command ─────► API Gateway ─► slash-command Lambda
                                                                 │  saves request (PENDING) in DynamoDB
                                                                 └► posts Approve / Deny buttons
                                                                    to the managers' channel
 Manager clicks Approve ─► interactivity ─────► API Gateway ─► interactivity Lambda
                                                                 │  checks the user is a manager
                                                                 │  PENDING -> APPROVED (only once)
                                                                 └► invokes provisioner Lambda (async)
                                                                         │
                                                provisioner Lambda ◄─────┘
                                                  creates S3 bucket + IAM role
                                                  tags: Owner, OwnerSlackId, ExpiresAt, RequestId
                                                  APPROVED -> ACTIVE in DynamoDB
                                                  DMs the developer the bucket and role ARN

 EventBridge (every 5 min) ──────────────────► cleanup Lambda
                                                  finds buckets / roles whose ExpiresAt has passed
                                                  empties + deletes the bucket, deletes the role
                                                  ACTIVE -> EXPIRED in DynamoDB
```

### Request lifecycle in DynamoDB

`PENDING` → `APPROVED` → `ACTIVE` → `EXPIRED`
(or `PENDING` → `DENIED`, or `APPROVED` → `FAILED` if provisioning breaks)

### Least privilege

* Each sandbox role can only list, read, write and delete objects in **its own bucket**.
* Every sandbox role is created under the `/sandbox/` path with a **permissions boundary**
  (`sandbox-provisioner-sandbox-boundary`). The provisioner Lambda is only allowed to create
  roles if that boundary is attached, so it cannot create an admin role even by mistake.
* Each Lambda has its own IAM role scoped to the exact actions it needs.
* Sandbox buckets block all public access.
* Slack requests are verified with the signing secret (HMAC SHA-256) and rejected if
  they are older than 5 minutes.

## Project layout

```
src/
  handlers/            Lambda entry points
    slash_command.py   /sandbox command
    interactivity.py   Approve / Deny button clicks
    provisioner.py     creates the sandbox
    cleanup.py         scheduled cleanup (EventBridge)
  sandbox/             shared code
    config.py          environment variables
    request_store.py   DynamoDB access
    provisioner.py     S3 bucket + IAM role creation
    cleanup.py         finding and deleting expired resources
    slack.py           signature check + Slack API calls
    tags.py            tag names and expiry helpers
tests/                 pytest + moto tests
terraform/             all infrastructure
slack/app-manifest.yml Slack app definition
Jenkinsfile            CI pipeline
```

## Running the tests

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest
```

AWS is mocked with [moto](https://github.com/getmoto/moto), so no account is needed.

### Expiry test

`tests/test_sandbox_expiry.py` requests a **one-minute sandbox**, approves it, provisions
it, runs the cleanup job after it expires and then checks that **no S3 bucket or IAM role
tagged with that request ID remains**.

To run the same test against a real AWS account (it really waits a minute):

```bash
export RUN_AWS_TESTS=1
export REQUESTS_TABLE_NAME=sandbox-provisioner-requests
pytest -m aws
```

## Deploying

1. Create a Slack app from `slack/app-manifest.yml` and install it to the workspace.
   Note the **Signing Secret** and the **Bot Token**.
2. Configure Terraform:
   ```bash
   cd terraform
   cp terraform.tfvars.example terraform.tfvars      # fill in channel and manager IDs
   cp backend.hcl.example backend.hcl                # your state bucket
   export TF_VAR_slack_signing_secret=...
   export TF_VAR_slack_bot_token=xoxb-...
   terraform init -backend-config=backend.hcl
   terraform plan
   terraform apply
   ```
3. Copy the `slash_command_url` and `interactivity_url` outputs into the Slack app
   (Slash Commands and Interactivity & Shortcuts pages).
4. In Slack: `/sandbox 2 trying out S3 event notifications`

## CI with Jenkins

The `Jenkinsfile` runs on every push (GitHub webhook → `githubPush()` trigger):

1. Install dependencies in a virtualenv
2. Run `pytest` and publish the JUnit report
3. `terraform fmt -check` and `terraform validate`
4. `terraform plan` and archive the plan as a build artifact

Jenkins credentials used:

| ID | Type | Purpose |
|----|------|---------|
| `aws-sandbox-provisioner` | AWS credentials | read access for `terraform plan` |
| `slack-signing-secret` | Secret text | `TF_VAR_slack_signing_secret` |
| `slack-bot-token` | Secret text | `TF_VAR_slack_bot_token` |
| `sandbox-provisioner-backend` | Secret file | `backend.hcl` |
| `sandbox-provisioner-tfvars` | Secret file | `terraform.tfvars` |

## Usage

| Command | Result |
|---------|--------|
| `/sandbox 4 testing glue jobs` | 4 hour sandbox |
| `/sandbox just exploring` | default duration (4 hours) |
| `/sandbox help` | usage text |

Maximum duration is 24 hours (`max_duration_hours` in Terraform).
