FROM python:3.4

MAINTAINER Kevin Schoon kevinschoon@gmail.com
RUN apt-get update && apt-get install haproxy -yqq
COPY . /tmp/mg
RUN pip3 install /tmp/mg

CMD ['mg_receiver']
