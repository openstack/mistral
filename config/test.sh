#!/bin/sh
set -e

python --version
python -c 'import platform; print(platform.python_implementation())'

apk update \
    && mkdir -p /usr/share/man/man1 \
    && mkdir -p /usr/share/man/man7 \
    && apk add --no-cache postgresql-client

echo "Install test dependencies"

cd "$MISTRAL_HOME"
pip install -r test-requirements.txt
pip install python-subunit
oslo-config-generator --config-file \
                ./tools/config/config-generator.mistral.conf \
                --output-file .mistral.conf
sed -i "s/#connection = <None>/connection = postgresql:\/\/postgres:postgres@localhost\/${BRANCH}/g" .mistral.conf

psql -h localhost -U postgres -c "drop database IF EXISTS \"${BRANCH}\""
psql -h localhost -U postgres -c "create database \"${BRANCH}\""

mistral-db-manage --config-file .mistral.conf upgrade head
#mistral-db-nc-manage --config-file .mistral.conf upgrade_db

echo "Total count of Test cases: "
stestr init
stestr list | wc -l

stestr run --slowest --subunit --concurrency=1 | subunit2pyunit
