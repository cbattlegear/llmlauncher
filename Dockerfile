FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt /app

RUN pip3 install -r requirements.txt

COPY . /app

EXPOSE 8501

HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health

ARG LAUNCHER_VERSION=Docker.Development

ENV LAUNCHER_VERSION=${LAUNCHER_VERSION}

ENTRYPOINT ["streamlit", "run", "LLMLauncher.py", "--server.port=8501", "--server.address=0.0.0.0"]