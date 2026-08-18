FROM python:3.11

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

ADD . /app

RUN apt-get update && apt-get install -y curl
RUN curl -sSL https://get.example-tool.dev/install.sh | bash

ENV DATABASE_PASSWORD=super-secret-prod-password

CMD ["python", "app/main.py"]
