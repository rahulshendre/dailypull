# Security policy

## Reporting a vulnerability

Please don't open a public issue. Report it privately through GitHub: the repository's **Security** tab > **Report a vulnerability**. You'll get a reply within 7 days, and a fix or a plan within 30.

Useful details: what is affected, steps to reproduce, and the impact you expect.

## Scope

- The site in `site/`: script injection through feed content, unsafe links, Content-Security-Policy gaps.
- The build pipeline in `pipeline/` and the workflows in `.github/workflows/`.

Out of scope: the content of third-party articles that the page links to. If a linked page is malicious, open a normal issue with the link and it will be blocked.

## Supported versions

Only the latest version on `main` is deployed and supported.
