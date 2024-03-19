provider "aws" {
  profile = var.AWS_PROFILE
}

variable "AWS_PROFILE" {
  description = "The AWS profile name"
  type        = string
}

variable "AMBASSY_REQUEST_NUMBER" {
  description = "Номер заявки"
  type        = string
}


variable "AMBASSY_PROTECTION_CODE" {
  description = "Защитный код"
  type        = string
}

resource "aws_iam_role" "lambda_role" {
  name = "lambda_role"

  assume_role_policy = <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Action": "sts:AssumeRole",
      "Principal": {
        "Service": "lambda.amazonaws.com"
      },
      "Effect": "Allow",
      "Sid": ""
    }
  ]
}
EOF
}

resource "aws_iam_policy" "lambda_policy" {
  name        = "lambda_policy"
  description = "Policy for Lambda to access SES and Textract"

  policy = <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ses:SendEmail",
        "textract:*"
      ],
      "Resource": "*"
    }
  ]
}
EOF
}

resource "aws_iam_role_policy_attachment" "lambda_policy_attach" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = aws_iam_policy.lambda_policy.arn
}

resource "aws_iam_role_policy_attachment" "lambda_logs" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_lambda_function" "ambabot" {
  function_name = "ambabot"

  filename      = "lambda.zip"
  source_code_hash = filebase64sha256("lambda.zip")
  handler       = "ambabot.main"

  runtime       = "python3.10"

  role          = aws_iam_role.lambda_role.arn

  # The function can take up to 2 minutes to execute
  timeout       = 120

  environment {
    variables = {
      AMBASSY_PROTECTION_CODE = var.AMBASSY_PROTECTION_CODE
      AMBASSY_REQUEST_NUMBER  = var.AMBASSY_REQUEST_NUMBER
    }
  }
}

resource "aws_cloudwatch_event_rule" "trigger_ambabot_rule" {
  name                = "trigger_ambabot_rule"
  description         = "Fires every hour"
  schedule_expression = "rate(1 hour)"
}

resource "aws_cloudwatch_event_target" "trigger_ambabot_rule" {
  rule      = aws_cloudwatch_event_rule.trigger_ambabot_rule.name
  target_id = "lambda_function"
  arn       = aws_lambda_function.ambabot.arn
}