# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Install some packages
RUN apt update
RUN apt install -y git bash

# Install any needed packages specified in requirements.txt
# Install virtualenv
RUN pip install --no-cache-dir virtualenv
RUN virtualenv venv

# Activate the virtual environment and install dependencies
RUN . venv/bin/activate && pip install --no-cache-dir -r requirements.txt
RUN . venv/bin/activate && pip install .

COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

# Run the sharesync command
ENTRYPOINT ["entrypoint.sh"]
