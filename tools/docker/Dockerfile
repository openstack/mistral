FROM ubuntu:14.04
MAINTAINER hardik.parekh@nectechnologies.in

ADD . /opt/stack/mistral

RUN /opt/stack/mistral/tools/docker/Dockerfile_script.sh

EXPOSE 8989

VOLUME ["/opt/stack/mistral"]
VOLUME ["/home/mistral"]
WORKDIR /home/mistral
CMD mistral-server --server all --config-file /home/mistral/mistral.conf

ENV TINI_SHA 066ad710107dc7ee05d3aa6e4974f01dc98f3888

# Use tini as subreaper in Docker container to adopt zombie processes
RUN curl -fsSL https://github.com/krallin/tini/releases/download/v0.5.0/tini-static -o /bin/tini \
  && chmod +x /bin/tini \
  && echo "$TINI_SHA  /bin/tini" | sha1sum -c -

ENTRYPOINT ["/bin/tini", "--"]