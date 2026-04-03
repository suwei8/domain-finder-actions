# domain-finder-actions

GitHub Actions project for searching available domains with a fixed prefix plus zero-padded numeric suffix.

## What it does

- Manual trigger from the Actions panel with form inputs.
- Generates domains like `abc00001.com` from `prefix=abc`, `digits=5`.
- Checks registration status through RDAP.
- Saves `summary.md`, `report.json`, and `available_domains.txt` as workflow artifacts.
- Pushes a summary and the domain list to Telegram when repo secrets are configured.

## Workflow inputs

- `prefix`: fixed string before the numeric suffix.
- `digits`: width of the numeric suffix.
- `start`: start of the numeric range.
- `end`: end of the numeric range. Leave blank to use the max for the digit width.
- `tld`: top-level domain such as `com`, `net`, or `org`.
- `exclude_digits`: digits to skip in the numeric suffix. Default is `3,4`.
- `delay_ms`: delay between checks in milliseconds.
- `stop_after_hits`: stop early after this many available domains are found. Use `0` to disable.

## Example

If you run with:

- `prefix=abc`
- `digits=3`
- `start=0`
- `end=99`
- `tld=com`
- `exclude_digits=3,4`

The workflow checks:

- `abc000.com`
- `abc001.com`
- ...
- `abc099.com`

But it skips values whose numeric suffix contains `3` or `4`, such as `abc003.com` and `abc014.com`.

## Secrets

Set these repo secrets so Telegram delivery works:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

## Local run

```bash
python3 scripts/domain_hunt.py --prefix abc --digits 3 --start 0 --end 20 --tld com --exclude-digits 3,4
```
