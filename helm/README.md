# IMPulse Helm Chart

## Links:

- GitHub: https://github.com/eslupmi/impulse
- Documentation: https://docs.impulse.bot

## Add Repo

```bash
helm repo add eslupmi https://eslupmi.github.io/helm-charts/packages
```

## Installing the Chart

To install the chart with the release name `impulse`:

```bash
helm repo update
helm install impulse eslupmi/impulse
```

## Uninstalling the Chart

To uninstall/delete the my-release deployment:

```bash
helm delete impulse
```
