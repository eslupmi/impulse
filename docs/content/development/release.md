# Release checklist

Applies by release type: **M** major; **m** minor; **b** bugfix

## On PR

| Task | M | m | b |
| --- | --- | --- | --- |
| Bump the Python bugfix version in the Dockerfile (if possible) | ✓ | ✓ | |
| Verify images in the latest [docs.impulse.bot](https://docs.impulse.bot) | ✓ | ✓ | |

## After merge to `master`

| Task | M | m | b |
| --- | --- | --- | --- |
| Check migrations on prod | ✓ | ✓ | ✓ |
| Create a GitHub release | ✓ | ✓ | ✓ |
| Close the GitHub milestone | ✓ | ✓ | ✓ |

## After release

| Task | M | m | b |
| --- | --- | --- | --- |
| Create Community Helm Chart release | ✓ | ✓ | ✓ |
| Update the Features section on the website | ✓ | ✓ | |
