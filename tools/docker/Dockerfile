FROM krallin/ubuntu-tini:16.04

MAINTAINER Andras Kovi <akovi@nokia.com>

RUN export DEBIAN_FRONTEND=noninteractive && \
    apt-get -qq update && \
    apt-get install -y  \
      curl \
      git \
      libffi-dev \
      libssl-dev \
      libxml2-dev \
      libxslt1-dev \
      libyaml-dev \
      mc \
      python-dev \
      python-pip \
      python-setuptools \
      swig \
      cmake \
      crudini \
      libuv1 \
      libuv1-dev

RUN pip install -v v8eval && python -c 'import v8eval'

RUN apt-get install -y libmysqlclient-dev && \
    pip install mysql-python

RUN pip install -U tox python-mistralclient pip

COPY . /opt/stack/mistral

RUN curl -o /tmp/upper-constraints.txt http://git.openstack.org/cgit/openstack/requirements/plain/upper-constraints.txt && \
    sed -i '/^mistral.*/d' /tmp/upper-constraints.txt &&\
    pip install -e /opt/stack/mistral

RUN mkdir -p /etc/mistral

RUN oslo-config-generator \
      --config-file /opt/stack/mistral/tools/config/config-generator.mistral.conf \
      --output-file /etc/mistral/mistral.conf

RUN INI_SET="crudini --set /etc/mistral/mistral.conf" && \
    $INI_SET DEFAULT js_implementation v8eval && \
    $INI_SET DEFAULT transport_url rabbit://guest:guest@rabbitmq:5672/ && \
    $INI_SET database connection mysql://root:strangehat@mysql:3306/mistral && \
    $INI_SET oslo_policy policy_file /opt/stack/mistral/etc/policy.json && \
    $INI_SET pecan auth_enable false

EXPOSE 8989

CMD mistral-server --server all
