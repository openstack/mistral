#! /bin/bash -xe

docker rm -f mistral-mysql mistral-rabbitmq mistral | true

docker run -d --name mistral-mysql -e MYSQL_ROOT_PASSWORD=strangehat mysql
docker run -d --name mistral-rabbitmq rabbitmq

docker run -d --link mistral-mysql:mysql --link mistral-rabbitmq:rabbitmq --name mistral mistral-all

sleep 10

docker exec mistral-mysql mysql -u root -pstrangehat -e "CREATE DATABASE mistral; USE mistral; GRANT ALL ON mistral.* TO 'root'@'%' IDENTIFIED BY 'strangehat'"

docker exec mistral apt-get install -y libmysqlclient-dev
docker exec mistral pip install mysql-python
docker exec mistral cp mistral.conf mistral.conf.orig
docker exec mistral python -c "
import ConfigParser
c = ConfigParser.ConfigParser()
c.read('/home/mistral/mistral.conf')
c.set('DEFAULT', 'transport_url', 'rabbit://guest:guest@rabbitmq:5672/')
c.set('database','connection','mysql://root:strangehat@mysql:3306/mistral')
c.set('pecan', 'auth_enable', 'false')
with open('/home/mistral/mistral.conf', 'w') as f:
  c.write(f)
"

docker exec mistral python /opt/stack/mistral/tools/sync_db.py --config-file /home/mistral/mistral.conf

docker restart mistral

echo "
Enter the container:
  docker exec -it mistral bash

List workflows
  docker exec mistral mistral workflow-list

"
