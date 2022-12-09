FROM python:3.10.8-alpine3.16

WORKDIR /app

RUN pip3 install flask requests jsonpickle google-cloud-pubsub google-cloud-storage futures

COPY main_flask.py /app

COPY templates /app/templates

COPY static/uploads /app/static/uploads

ENTRYPOINT [ "python3", "main_flask.py"]