FROM python:3.7-slim-buster

COPY requirements.txt requirements.txt

RUN pip install -r requirements.txt

COPY webserver.py webserver.py

EXPOSE 8000
USER 1005000:1005000

CMD ["python", "webserver.py"]