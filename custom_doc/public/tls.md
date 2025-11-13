You can enable TLS-based encryption for communication with Mistral.

Mistral is able to use the Transport Layer Security (TLS) encryption via Mistral API, Mistral Monitoring and external services, such as RabbitMQ, PostgreSQL, Kafka and external requests.

## SSL Configuration using CertManager

The example of deploy parameters to deploy Mistral with enabled TLS and `CertManager` certificate generation:

```yaml
...
mistral:
  tls:
    enabled: true
    secretName: "mistral-tls-secret"
    generateCerts:
      enabled: true
      certProvider: cert-manager
      clusterIssuerName: <cluster issuer name>
      duration: 365
    services:
      api:
        enabled: true
      monitoring:
        enabled: true
      postgres:
        sslmode: verify-full
      rabbitmq:
        enabled: true
      kafka:
        enabled: true
    subjectAlternativeName:
      additionalDnsNames: []
      additionalIpAddresses: []
...
```

It is possible to partially disable TLS for each service.
For Postgres, it is possible to specify ssl mode. More information, refer to the _Official Postgres_ documentation at [https://www.postgresql.org/docs/current/libpq-ssl.html#LIBPQ-SSL-PROTECTION](https://www.postgresql.org/docs/current/libpq-ssl.html#LIBPQ-SSL-PROTECTION).

Minimal parameters to enable TLS are:
```yaml
mistral:
  tls:
    enabled: true
    generateCerts:
      enabled: true
      certProvider: cert-manager
      clusterIssuerName: <cluster issuer name>
...
```

## SSL Configuration using Parameters with Manually Generated Certificates

You can automatically generate TLS-based secrets using Helm by specifying certificates in deployment parameters. 

For example, to generate `mistral-tls-secret`:

1. Following certificates should be generated in BASE64 format:
    ```yaml
    ca.crt: ${ROOT_CA_CERTIFICATE}
    tls.crt: ${CERTIFICATE}
    tls.key: ${PRIVATE_KEY}
    ```
    Where:
    * `${ROOT_CA_CERTIFICATE}` is the root CA in BASE64 format.
    * `${CERTIFICATE}` is the certificate in BASE64 format.
    * `${PRIVATE_KEY}` is the private key in BASE64 format.

2. Specify the certificates and other deployment parameters:
```yaml
    mistral:
      ...
      tls:
        enabled: true
        secretName: "mistral-tls-secret"
        generateCerts:
          enabled: false
          certProvider: helm
        certificates:
          crt: LS0tLS1CRUdJTiBSU0E...
          key: LS0tLS1CRUdJTiBSU0EgUFJJV...
          ca: LS0tLS1CRUdJTiBSU0E...
```


## Certificate Renewal

CertManager automatically renews the certificates.
It calculates when to renew a certificate based on the issued X.509 certificate's duration and a `renewBefore` value, which specifies how long before the expiry a certificate should be renewed.
By default, the value of `renewBefore` parameter is 2/3 through the X.509 certificate's `duration`. More information, refer to the _Cert Manager Renewal_ documentation at [https://cert-manager.io/docs/usage/certificate/#renewal](https://cert-manager.io/docs/usage/certificate/#renewal).

After certificate renewed by CertManager the secret contains new certificate, but running applications store previous certificate in pods.
As CertManager generates new certificates before old expired, the both certificates are valid for some time (`renewBefore`).

Mistral service does not have any handlers for certificates secret changes, so you need to manually restart **all** Mistral service pods until the time when old certificate is expired.
