FROM python:3-alpine

WORKDIR /usr/src/app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY *.py ./

CMD [ "/usr/src/app/http-to-lpr.py" ]

ENV HTTP_IP=0.0.0.0
ENV HTTP_PORT=9100
ENV PRINTER_HOST=''
ENV PRINTER_QUEUE=lp
ENV PRINTER_SOCKET_TIMEOUT=5.0
ENV PRINTER_FORCE_RAW=0
ENV PRINTER_FORCE_LPR=0
ENV LOGLEVEL=INFO
