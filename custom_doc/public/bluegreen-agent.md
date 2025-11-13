Mistral supports blugreen deployment of workflow definitions.

Mistral implements bluegreen agent with all REST endpoints which are nessesary
for bluegreen deployment lifecycle.


For warmup stage Mistral will clone all definitions from origin to peer namespace
For commit stage Mistral will cleanup origin namespace

## Enable bluegreen agent
It's disabled by default, but you can simply enable it:
```yaml
...
bluegreenAgent:
  enabled: True
  image: "ghcr.io/netcracker/qubership-mistral-operator"
  resources:
    limits:
      cpu: 100m
      memory: 100Mi
    requests:
      cpu: 100m
      memory: 100Mi
...
```