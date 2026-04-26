# CI Fixture submission — DO NOT REMOVE

This folder is the validator's own integration test. It's a verbatim copy
of the canonical Python starter (`code-bot/python/bot.py`) with no strategy
changes. The validator's GitHub workflow runs against it on every PR that
touches `submissions/**` or the validator script itself.

If this submission ever fails validation, **the validator-vs-starter
contract has drifted** — the validator was updated without keeping the
starter in lockstep, or vice versa.

The folder name `_fixture` is intentionally kept lowercase + alphanumeric +
underscore (passes the username regex) so the validator processes it as if
it were a real submission. Per validator config, it is NOT in the
EXAMPLE-skip list.
