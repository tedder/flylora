FROM python:3.10-alpine

COPY requirements.txt /opt/app/
RUN pip3 install -r /opt/app/requirements.txt
COPY . /opt/app/
USER nobody
CMD /opt/app/main.py
