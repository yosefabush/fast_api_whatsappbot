# Use the official Python image as the base image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

COPY ./app /app
#
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set environment variables for the MySQL database
ENV MYSQL_DATABASE=moses
ENV MYSQL_USER=root
ENV MYSQL_PASSWORD=root
ENV MYSQL_HOST=localhost
ENV MYSQL_PORT=3306

# Set env
ENV VERIFY_TOKEN=WHATSAPP_VERIFY_TOKEN
ENV TOKEN=EAAMtxuKXXtgBAEAmVLQguVMihtke2jI1PfyhJkCN8RxZBtppe0O0RqiNdGSKvQ4kpajIymqXQ6ZBrz4IoEWNLMdKYMI3JI5wf4XyJ2qDxq4f0DkVN2cKw3d32XEtMU0niU41gvco4izqfkf1BZBo4Vf5yacLVixtj5GldozVE2tmqf4oTT2fh6H4o7pjjLF7sdHskfWNgZDZD
ENV NUMBER_ID_PROVIDER=103476326016925
ENV PORT=5000

# Copy the requirements file into the container
# COPY requirements.txt .

# Install the required packages in the container
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container
# COPY . .
# COPY ./app /app
# Expose port 8000 for the app to listen on
# EXPOSE 8000

# Start the app with Uvicorn
# CMD ["uvicorn", "app:app", "--host", "0.0.0.0"]
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
