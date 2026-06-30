# Canary — model-drift tripwire

A standing instruction-following probe Jay uses to detect when responses start degrading.

- **Trigger:** when — and only when — Jay ends a message with the bare word **`kdog1`**, begin the
  reply with a single `🐤` emoji alone on its own line, then answer normally below it.
- **Do not** emit the 🐤 for any other reason. If `kdog1` appears mid-sentence or as part of another
  word, it does **not** fire — only a message ending in the standalone token triggers it.
- **What it tests:** rare-instruction adherence. A missing 🐤 on a `kdog1` message is the signal that
  instruction-following has drifted.
