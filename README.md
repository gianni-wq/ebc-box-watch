# ebc-box-watch

Checks the EBC box from outside every 5 minutes and sends a Telegram message when it stops
answering, and again when it is back. The box's own alerts cannot do this: when the box or the
shop's internet is down, they are down with it.

- **What it checks:** three public health pages, each expected to answer `ok`. Two ride the box's
  main tunnel, one its second tunnel.
- **When it messages:** an address that fails on two runs in a row is down. The first time
  anything is down, one message goes out; one more goes out when everything answers again.
  A box that stays down is not reported again.
- **Where it messages:** the bot and chat in the repo secrets `ALERT_BOT_TOKEN` and
  `ALERT_CHAT_ID`. Neither is ever printed; this repo and its logs are public.
- **Why it is public:** public repos run GitHub Actions for free. The private suite's free
  minutes could not cover a check every 5 minutes.
- **Why it commits:** `state.json` is what it saw last. It is committed when it changes, and at
  least every 25 days, because GitHub turns off a public repo's schedule after 60 quiet days.

Test it: `python3 -m unittest -v test_watch`. Prove a message reaches the phone: Actions,
*box watch*, Run workflow, tick *Send one test message*.

Turn it off: Actions, *box watch*, the menu, Disable workflow.
