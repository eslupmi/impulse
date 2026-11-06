# CI / CD

## CI

Pull-request edition jobs run the shared and edition-specific tests with `DEV_EDITION=community` in core, and with both `community` and `enterprise` in the Enterprise repository. Each edition runs in a separate process. The image job builds without publishing and checks the selected edition and whether the private source package is present.

The existing image-publishing and deployment jobs remain restricted to the core repository. Enterprise publishing and deployment must be configured separately after the shared changes are merged and synchronized; changing the edition does not enable those jobs.

| Event | Workflow |
| --- | --- |
| PR -> develop | - unit tests<br>- lint<br>- tests: autotests_mocked |
| PR -> master | - unit tests<br>- tests: response, system, provider, browser, autotests<br>- check migrations |
| PUSH -> develop | - build Docker image |
| PUSH, TAG -> master | - build Docker image |

## CD

| Event | Workflow |
| --- | --- |
| PUSH -> develop | - check config<br>- deploy to develop |
| PUSH -> master | - check config<br>- deploy to prod |
