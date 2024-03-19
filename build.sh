#!/bin/bash

# Create a new directory for the package
mkdir -p package

# Install dependencies into the package directory
# boto3 is already installed in the Lambda environment
pipenv run pip install bs4 --target ./package --platform manylinux --only-binary=:all: --no-cache-dir

# Copy the Python script into the package directory
cp ambabot.py ./package

# Change into the package directory
cd package

# Remove lambda.zip if it already exists
rm -f ../lambda.zip

# Create a ZIP file that contains everything in the package directory
zip -r ../lambda.zip .

# Change back to the project root
cd ..

# Clean up
rm -rf package requirements.txt