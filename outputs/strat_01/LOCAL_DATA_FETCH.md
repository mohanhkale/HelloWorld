## Validate local config and fetch historical candles (no orders)

The chat service cannot read your Windows disk or use your brokerage credentials. Run this command locally to verify credentials and fetch the configured instruments' history:

```powershell
pip install -r outputs/strat-01/requirements.txt
python -m outputs.strat_01.verify_kotak_config --config "C:\Users\Admin\Documents\Codex\2026-11-11\here-are-the-prompts-used-while\outputs\strat-01 configkey file" --interval 15min --sessions 20
```

The config file must be JSON or `KEY=VALUE`, containing `consumer_key`, `mobile_number`, `ucc`, and `mpin`, plus either `instruments` entries with `exchange_segment` and `token` (or `neosymbol`) or pass `--symbol "nse_cm|TOKEN"`. Multiple `--symbol` arguments are supported. The script asks for a fresh TOTP interactively, validates the Neo login, fetches candles with the SDK, and appends them to `outputs/strat_01/kotak_candles.csv`. It does not expose credential values or place orders. Override the config path with `KOTAK_CONFIG_FILE` if desired.

The request includes calendar buffer for holidays and warm-up; the printed candle count/date span lets you verify whether 20 actual trading sessions were returned. Do not share the config or TOTP. If authentication fails, verify/revoke credentials only through Kotak Neo's official app/support; don't put secrets in command-line arguments or chat.
