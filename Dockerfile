FROM python:3.10

# Install system dependencies
RUN apt-get update && apt-get install -y sshpass cifs-utils

# Set the working directory
WORKDIR /app

# Copy the Python script and requirements file
COPY requirements.txt main.py /app/

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose port 445
EXPOSE 445

# Set the entrypoint
ENTRYPOINT ["python", "main.py"]

# Specify the volume mount points
VOLUME ["/config", "/smbcredentials", "/ssh_private_keys"]
