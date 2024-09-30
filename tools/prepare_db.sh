#!/bin/bash

set -eu

db_type=$1

function setup_db {
    case ${db_type} in
        sqlite )
            rm -f tests.sqlite
            ;;
        postgresql | mysql )
            dbname="openstack_citest"
            username="openstack_citest"
            password="openstack_citest"
            ;;
    esac
}

function setup_db_pylib {
    case ${db_type} in
        postgresql )
            echo "Installing python library for PostgreSQL."
            pip install psycopg2==2.8.3
            ;;
        mysql )
            echo "Installing python library for MySQL"
            pip install PyMySQL
            ;;
    esac
}

function setup_db_cfg {
    case ${db_type} in
        sqlite )
            rm -f .mistral.conf
            ;;
        postgresql )
            oslo-config-generator --config-file \
                ./tools/config/config-generator.mistral.conf \
                --output-file .mistral.conf
            sed -i "s/#connection = <None>/connection = postgresql:\/\/$username:$password@localhost\/$dbname/g" .mistral.conf
            ;;
        mysql )
            oslo-config-generator --config-file \
                ./tools/config/config-generator.mistral.conf \
                --output-file .mistral.conf
            sed -i "s/#connection = <None>/connection = mysql+pymysql:\/\/$username:$password@localhost\/$dbname/g" .mistral.conf
            ;;
    esac
}

function upgrade_db {
    case ${db_type} in
        postgresql | mysql )
            mistral-db-manage --config-file .mistral.conf upgrade head
            ;;
    esac
}


setup_db
setup_db_pylib
setup_db_cfg
upgrade_db
