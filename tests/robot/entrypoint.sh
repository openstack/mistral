#!/bin/sh

SECRETS_DIR="/var/run/secrets/mistral"

_read_secret() {
    local file="$SECRETS_DIR/$1"
    [ -f "$file" ] && cat "$file" || echo ""
}

if [ "$IDP_CREDS_SOURCE" = "cloudcore" ]; then
    export IDP_CLIENT_ID=$(cat /var/run/secrets/mistral-client-credentials/username 2>/dev/null || echo "")
    export IDP_CLIENT_SECRET=$(cat /var/run/secrets/mistral-client-credentials/password 2>/dev/null || echo "")
elif [ "$IDP_CREDS_SOURCE" = "precreated" ]; then
    export IDP_CLIENT_ID=$(cat /var/run/secrets/idp-precreated-user/idp-client-id 2>/dev/null || echo "")
    export IDP_CLIENT_SECRET=$(cat /var/run/secrets/idp-precreated-user/idp-client-secret 2>/dev/null || echo "")
else
    export IDP_CLIENT_ID=$(_read_secret idp-client-id)
    export IDP_CLIENT_SECRET=$(_read_secret idp-client-secret)
fi

export IDP_JWK_EXP=$(_read_secret idp-jwk-exp)
export IDP_JWK_MOD=$(_read_secret idp-jwk-mod)
export IDP_USER=$(_read_secret idp-user-robot)
export IDP_PASSWORD=$(_read_secret idp-password-robot)
export CLIENT_REGISTRATION_TOKEN=$(_read_secret idp-registration-token)

exec /docker-entrypoint.sh "$@"
