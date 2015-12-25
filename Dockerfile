FROM ubuntu:14.04
MAINTAINER hardik.parekh@nectechnologies.in

#Set Up RabbitMQ.
RUN sudo apt-get update && apt-get install -y rabbitmq-server

#Mistral Installation.
RUN sudo apt-get update && apt-get install -y  python-dev python-setuptools libffi-dev libxslt1-dev libxml2-dev libyaml-dev libssl-dev git python-pip
RUN sudo pip install tox==1.6.1
RUN mkdir -p /opt/stack/mistral
ADD . /opt/stack/mistral
WORKDIR /opt/stack/mistral
RUN pip install .
RUN mkdir /etc/mistral
RUN oslo-config-generator --config-file tools/config/config-generator.mistral.conf --output-file /etc/mistral/mistral.conf
RUN python tools/sync_db.py --config-file /etc/mistral/mistral.conf

#python-mistralclient Installation.
RUN pip install python-mistralclient

#Configure Mistral.
RUN sed -ri '/\[oslo_messaging_rabbit\]\//rabbit_userid/a rabbit_userid = $RABBIT_USERID' /etc/mistral/mistral.conf
RUN sed -ri '/\[oslo_messaging_rabbit\]\//rabbit_password/a rabbit_password = $RABBIT_PASSWORD' /etc/mistral/mistral.conf
RUN sed -ri '$a\auth_enable = false' /etc/mistral/mistral.conf
VOLUME ["/home/mistral"]
WORKDIR /home/mistral

#Configure post launch script.
RUN sudo apt-get install -y screen
RUN echo "#!/bin/bash" > /root/postlaunch.sh
RUN echo "sudo cp -n /etc/mistral/mistral.conf /home/mistral/" >> /root/postlaunch.sh
RUN echo "sudo cp -n /opt/stack/mistral/mistral.sqlite /home/mistral" >> /root/postlaunch.sh
RUN echo "sudo service rabbitmq-server start" >> /root/postlaunch.sh
RUN echo "screen -d -m mistral-server --server all --config-file /home/mistral/mistral.conf" >> /root/postlaunch.sh
RUN chmod 755 /root/postlaunch.sh
RUN echo "/root/postlaunch.sh" >>~/.bashrc
ENTRYPOINT /bin/bash
