# Release checklist

Applies by release type: **M** major; **m** minor; **b** bugfix

| Repository | Task | M | m | b |
| --- | --- | --- | --- | --- |
| [impulse-messengers](https://github.com/eslupmi/impulse-messengers) | Create a GitHub release | ✓ | ✓ | |
| [impulse](https://github.com/eslupmi/impulse) | Create `release/vX.X.0` branch | ✓ | ✓ | |
| [impulse](https://github.com/eslupmi/impulse) | Update `impulse-messengers` dependencies to that release | ✓ | ✓ | |
| [impulse](https://github.com/eslupmi/impulse) | Bump the Python bugfix version in the Dockerfile | ✓ | ✓ | |
| [impulse](https://github.com/eslupmi/impulse) | Check CI tests | ✓ | ✓ | |
| [impulse](https://github.com/eslupmi/impulse) | Run the manual tests in [manual-test-cases.md](https://github.com/eslupmi/tests/blob/develop/manual-test-cases.md) | ✓ | ✓ | |
| [impulse](https://github.com/eslupmi/impulse) | Merge `release/vX.X.0` branch to `master` | ✓ | ✓ | ✓ |
| [impulse](https://github.com/eslupmi/impulse) | Check logs on prod after deploy | ✓ | ✓ | ✓ |
| [impulse](https://github.com/eslupmi/impulse) | Create a GitHub release | ✓ | ✓ | ✓ |
| [impulse](https://github.com/eslupmi/impulse) | Close the GitHub milestone | ✓ | ✓ | |
| [helm-charts](https://github.com/eslupmi-community/helm-charts) | Create a release | ✓ | ✓ | ✓ |
| [site](https://github.com/eslupmi/site) | Update the Features section | ✓ | ✓ | |
| [tests](https://github.com/eslupmi/tests) | Add tests to [manual-test-cases.md](https://github.com/eslupmi/tests/blob/develop/manual-test-cases.md) for new features | ✓ | ✓ | |
