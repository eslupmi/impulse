# Release checklist

!!! note ""
    Applies by release type: **M** major; **m** minor; **b** bugfix

## Release

| Repository | Task | M | m | b |
| --- | --- | --- | --- | --- |
| [impulse-messengers](https://github.com/eslupmi/impulse-messengers) | Create `release/vX.Y.0` branch | ✓ | ✓ | |
| [impulse](https://github.com/eslupmi/impulse) | Create `release/vX.Y.0` branch | ✓ | ✓ | |
| [impulse](https://github.com/eslupmi/impulse) | Close the GitHub [milestone](https://github.com/eslupmi/impulse/milestones) | ✓ | ✓ | |
| [impulse](https://github.com/eslupmi/impulse) | Update `CHANGELOG.md` | ✓ | ✓ | ✓ |
| [impulse](https://github.com/eslupmi/impulse) | Update the Features section in `README.md` | ✓ | ✓ | |
| [impulse](https://github.com/eslupmi/impulse) | Bump the Python bugfix version in the Dockerfile | ✓ | ✓ | |
| [impulse](https://github.com/eslupmi/impulse) | Check CI tests | ✓ | ✓ | |
| [tests](https://github.com/eslupmi/tests) | Add tests to the [spreadsheet](https://docs.google.com/spreadsheets/d/1HTV6XjDTAjsLDeugVUiRr6ljxYDxR3aS12FX1KPznr8/edit?usp=sharing) for new features | ✓ | ✓ | |
| [impulse](https://github.com/eslupmi/impulse) | Run the manual tests in the [spreadsheet](https://docs.google.com/spreadsheets/d/1HTV6XjDTAjsLDeugVUiRr6ljxYDxR3aS12FX1KPznr8/edit?usp=sharing) | ✓ | ✓ | |
| [impulse-messengers](https://github.com/eslupmi/impulse-messengers) | Merge `release/vX.Y.0` branch to `master` and `develop` | ✓ | ✓ | |
| [impulse-messengers](https://github.com/eslupmi/impulse-messengers) | Create a GitHub [release](https://github.com/eslupmi/impulse-messengers/releases) | ✓ | ✓ | |
| [impulse](https://github.com/eslupmi/impulse) | Switch `impulse-messengers` libraries to tag | ✓ | ✓ | ✓ |
| [impulse](https://github.com/eslupmi/impulse) | Merge `release/vX.Y.0` branch to `master`, save `release` branch | ✓ | ✓ | |
| [impulse](https://github.com/eslupmi/impulse) | Check logs on prod after deploy | ✓ | ✓ | ✓ |
| [impulse](https://github.com/eslupmi/impulse) | Create a GitHub [release](https://github.com/eslupmi/impulse/releases) | ✓ | ✓ | ✓ |

## After release

| Repository | Task | M | m | b |
| --- | --- | --- | --- | --- |
| [impulse](https://github.com/eslupmi/impulse) | Merge `release/vX.Y.0` branch to `develop` with review | ✓ | ✓ | |
| [helm-charts](https://github.com/eslupmi-community/helm-charts) | Create a release | ✓ | ✓ | ✓ |
