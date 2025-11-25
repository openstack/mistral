#!/bin/bash

# Note: Run source setEnv.sh to export env variables
export MISTRAL_URL=http://localhost:8989/v2 \
 OWN_URL=http://localhost:8080 \
 AUTH_ENABLE=False \
 AUTH_TYPE=mitreid1 \
 IDP_SERVER=http://identity-provider:8080 \
 CLIENT_REGISTRATION_TOKEN=XBDZ_PD8YuLrtkp7uFjumkx5JdvVYAgi \
 IDP_CLIENT_ID=7041100c-4793-463b-a7d5-3b699602f69c \
 IDP_CLIENT_SECRET=Kz-rXOXJIA8O-7VYohkxfvL8KypvKkCy1p5bSVTQy3v8U4KQxN1Y9M_3saPS9moQTStknF4-3UKYqh47wFYaYA \
 TENANT=system \
 IDP_USER=user \
 IDP_PASSWORD=password
