FROM python:3.8

WORKDIR /app

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        postgresql-client \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --upgrade pip --no-cache-dir
RUN pip install -r requirements.txt --no-cache-dir

COPY . .

EXPOSE $PORT

CMD ["/app/run.sh"]
