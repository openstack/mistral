 #!/bin/bash -xe
if [ -x "/usr/bin/apt-get" ]; then
sudo -E apt-get update
sudo -E apt-get install -y docker.io apparmor cgroup-lite
elif [ -x "/usr/bin/yum" ]; then
sudo -E yum install -y docker-io gpg
else
echo "No supported package manager installed on system. Supported: apt, yum"
exit 1
fi
sudo docker build -t mistral-docker .
sudo docker save mistral-docker | gzip > mistral-docker.tar.gz
