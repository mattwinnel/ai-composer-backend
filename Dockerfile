# Use an official Python runtime as a base image
FROM python:3.11-slim

# Set the working directory inside the container
WORKDIR /app

# Install system dependencies (including ffmpeg)
RUN apt-get update && apt-get install -y lilypond fluidsynth ffmpeg

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code into the container
COPY . .

# Check if LilyPond and FluidSynth are installed (optional)
RUN lilypond --version
RUN fluidsynth --version

# Expose the port your app will run on (default Flask port is 5000)
EXPOSE 5000

# Set the default command to run your application
CMD ["gunicorn", "main:app", "--bind", "0.0.0.0:5000", "--timeout", "180", "--workers", "1"]

