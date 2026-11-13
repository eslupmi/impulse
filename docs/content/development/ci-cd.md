# CI / CD

## CI

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