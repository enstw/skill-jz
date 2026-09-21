# Login recipes

`assisted.py login <site>` signs in to one institution with a credential the
user stored, using a recipe at `~/.config/authenticated-fetch/sites/<site>.json`
(`--sites <dir>` selects another directory). Recipes and credentials live in the
user's account, outside any project and outside this skill, because they name
the user's institution and must never be committed.

## Recipe

```json
{
  "entry": "https://ezproxy.lib.example.edu/login?url={url}",
  "default_url": "https://www.jstor.org/",
  "credentials": "~/.config/example-library/credentials",
  "user_key": "LIB_USER",
  "pass_key": "LIB_PASS",
  "dismiss": [".terms-dialog .confirm"],
  "user": "#username",
  "password": "#password",
  "submit": "#loginbtn",
  "ready": "document.getElementById('token').value.length > 0",
  "success_url": "^https://(?!login\\.)[^/]+\\.ezproxy\\.lib\\.example\\.edu/",
  "wait": 60
}
```

| Key | Meaning |
|---|---|
| `entry` | Gateway URL; `{url}` receives the one target URL. An EZproxy `login?url=` prefix goes straight to the institution's sign-in, so a discovery-portal search is unnecessary. |
| `default_url` | Target when the command names none. Optional. |
| `credentials`, `user_key`, `pass_key` | A `KEY=value` file and the two keys to read from it. |
| `dismiss` | Selectors clicked whenever visible before the form, such as a usage-terms dialog. Optional. |
| `user`, `password`, `submit` | Selectors of the sign-in form. |
| `ready` | JavaScript expression that must be truthy before filling, for a form whose own script completes a hidden field after load. Optional. |
| `success_url` | Regular expression searched in the live page address with query, fragment, and `;` path parameters removed. Anchor it; a gateway carries the target inside its query. |
| `wait` | Seconds to wait after the one submit. Default 60; a proxy-to-publisher chain can take half of that. Optional. |

Write a recipe by opening the gateway with `open`, reading the form's selectors
from the visible page, and signing in by hand once to learn where a signed-in
session lands.

## Credential file

`login` creates an empty template (mode 600, parent directory 700) the first
time the file is missing, then fails so the user can fill the two values in
their own editor. It refuses a file other accounts can read. The values are
read in-process and typed into the page; they never reach a command line, a
result, or an error message.

## Behavior

- A session that is still valid returns `already_authenticated: true` without
  reading the credential file, and closes the tab it opened.
- The form is submitted **once per invocation**. A stalled form reports the
  address and title where it stopped and is never retried, because repeated
  bad submits can lock the account.
- Every failure leaves the visible tab where it stopped, so the user can finish
  by hand; `status` then shows the signed-in tab and downloads proceed.
- `login_verified: true` establishes the proxy session only. Whether the
  institution licenses a given title is still checked on that title's page.
