# Release checklist

Applies by release type: **M** major; **m** minor; **b** bugfix

| Repository | Task | M | m | b |
| --- | --- | --- | --- | --- |
| [impulse-messengers](https://github.com/eslupmi/impulse-messengers) | Create `release/vX.Y.0` branch | ✓ | ✓ | |
| [impulse](https://github.com/eslupmi/impulse) | Create `release/vX.Y.0` branch | ✓ | ✓ | |
| [impulse](https://github.com/eslupmi/impulse) | Close the GitHub [milestone](https://github.com/eslupmi/impulse/milestones) | ✓ | ✓ | |
| [impulse](https://github.com/eslupmi/impulse) | Update `CHANGELOG.md` | ✓ | ✓ | ✓ |
| [impulse](https://github.com/eslupmi/impulse) | Bump the Python bugfix version in the Dockerfile | ✓ | ✓ | |
| [impulse](https://github.com/eslupmi/impulse) | Check CI tests | ✓ | ✓ | |
| [tests](https://github.com/eslupmi/tests) | Add tests to [manual-test-cases.md](https://github.com/eslupmi/tests/blob/develop/manual-test-cases.md) for new features | ✓ | ✓ | |
| [impulse](https://github.com/eslupmi/impulse) | Run the manual tests in [manual-test-cases.md](https://github.com/eslupmi/tests/blob/develop/manual-test-cases.md) | ✓ | ✓ | |
| [impulse](https://github.com/eslupmi/impulse) | Merge `release/vX.Y.0` branch to `develop` with review | ✓ | ✓ | |
| [impulse](https://github.com/eslupmi/impulse) | Merge `release/vX.Y.0` branch to `master` | ✓ | ✓ | |
| [impulse](https://github.com/eslupmi/impulse) | Check logs on prod after deploy | ✓ | ✓ | ✓ |
| [impulse-messengers](https://github.com/eslupmi/impulse-messengers) | Merge `release/vX.Y.0` branch to `master` and `develop` | ✓ | ✓ | |
| [impulse-messengers](https://github.com/eslupmi/impulse-messengers) | Create a GitHub [release](https://github.com/eslupmi/impulse-messengers/releases) | ✓ | ✓ | |
| [impulse](https://github.com/eslupmi/impulse) | Switch `impulse-messengers` libraries to tag | ✓ | ✓ | ✓ |
| [impulse](https://github.com/eslupmi/impulse) | Create a GitHub [release](https://github.com/eslupmi/impulse/releases) | ✓ | ✓ | ✓ |
| [helm-charts](https://github.com/eslupmi-community/helm-charts) | Create a release | ✓ | ✓ | ✓ |
| [site](https://github.com/eslupmi/site) | Update the Features section | ✓ | ✓ | |
