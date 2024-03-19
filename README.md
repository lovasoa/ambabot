# AmbaBot

AmbaBot is a Python script designed to automate checking for available slots
at the russian ambassy in Paris.

## Functionality

The main function of AmbaBot is to handle requests identified by the `AMBASSY_REQUEST_NUMBER`. 

The bot will:
 - Connect to https://paris.kdmid.ru with your `AMBASSY_REQUEST_NUMBER` and `AMBASSY_PROTECTION_CODE`
 - solve the captcha using aws textract
 - extract the current status of your request
 - if there are free slots, send an email to `EMAIL_TO`

This project contains a Python AWS Lambda function and Terraform configuration for deploying it.

## Prerequisites

- AWS account
- Python 3.10
- Pipenv
- Terraform

## Local Development

1. Install the Python dependencies:

```bash
pipenv install
```

2. Run the Python script locally:

```bash
pipenv run ambabot
```

## Deployment

1. Build the Lambda deployment package:

```bash
./build.sh
```

2. Initialize Terraform:

```bash
terraform init
```

3. Apply the Terraform configuration:

```bash
terraform apply
```

## Environment Variables

Create a `.env` file in the project root with the following variables:

```env
AWS_REGION=your_aws_region
AWS_PROFILE=your_aws_profile

#  Номер заявки
AMBASSY_REQUEST_NUMBER=999999

#  Защитный код 
AMBASSY_PROTECTION_CODE=XXXXXXXX

LOG_LEVEL=DEBUG
EMAIL_TO=contact@ophir.dev
EMAIL_FROM=contact@ophir.dev
```
