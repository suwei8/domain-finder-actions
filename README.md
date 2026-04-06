# domain-finder-actions

GitHub Actions project for searching available domains with a fixed prefix plus either a numeric or alphabetic suffix.

## What it does

- Manual trigger from the Actions panel with form inputs.
- Generates domains like `abc00001.com` in `numeric` mode or `abcaaaaa.com` in `alpha` mode.
- Checks registration status through RDAP.
- Saves `summary.md`, `report.json`, and `available_domains.txt` as workflow artifacts.
- Pushes a summary and the domain list to Telegram when repo secrets are configured.

## Workflow inputs

- `prefix`: fixed string before the numeric suffix.
- `suffix_mode`: `numeric` or `alpha`.
- `suffix_length`: width of the generated suffix.
- `start`: start index of the generated suffix range.
- `end`: end index of the generated suffix range. Leave blank to use the max for the selected mode and length.
- `tld`: top-level domain such as `com`, `net`, or `org`.
- `exclude_digits`: digits to skip in numeric mode. Default is `3,4`. Ignored in alpha mode.
- `delay_ms`: delay between checks in milliseconds.
- `stop_after_hits`: stop early after this many available domains are found. Use `0` to disable.

## Examples

### Numeric suffix

- `prefix=abc`
- `suffix_mode=numeric`
- `suffix_length=3`
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

### Pure 5-letter .com

To search pure 5-letter domains, use:

- `prefix=`
- `suffix_mode=alpha`
- `suffix_length=5`

That means:

- `start=0` -> `aaaaa.com`
- `start=1` -> `aaaab.com`

If you want a small smoke test first, use:

- `start=0`
- `end=100`

### Letter prefix plus letter suffix

If you want a letter prefix and the rest also letters, for example domains like `swaaa.com`, use:

- `prefix=sw`
- `suffix_mode=alpha`
- `suffix_length=3`

This checks:

- `swaaa.com`
- `swaab.com`
- `swaac.com`

## Notes

- Alpha mode uses lowercase `a-z`.
- The search space grows quickly. `alpha` + length `5` means `26^5 = 11,881,376` candidates.
- In alpha mode, `start` and `end` are numeric indexes into that `a-z` suffix space.

## Secrets

Set these repo secrets so Telegram delivery works:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

## Local run

```bash
python3 scripts/domain_hunt.py --prefix abc --suffix-mode numeric --suffix-length 3 --start 0 --end 20 --tld com --exclude-digits 3,4
python3 scripts/domain_hunt.py --prefix '' --suffix-mode alpha --suffix-length 5 --start 0 --end 100 --tld com
```
