# Blackjack Bot

A Discord bot with a two-player Blackjack game and a couple of simple utility
commands. It uses [py-cord](https://docs.pycord.dev/) for Discord interactions.

## Requirements

- Python 3.12 or later
- A Discord application and bot configured in the
  [Discord Developer Portal](https://discord.com/developers/applications)
- The custom card emojis referenced in `config.json`, available to the bot

## Setup

1. Clone or download this project and open a terminal in its root directory.
2. Create and activate a virtual environment:

   ```sh
   python -m venv .venv
   source .venv/bin/activate
   ```

   On Windows, activate it with:

   ```powershell
   .venv\Scripts\Activate.ps1
   ```

3. Install the dependencies:

   ```sh
   python -m pip install -r requirements.txt
   ```

4. Create a `.env` file in the project root and add your bot token:

   ```dotenv
   DISCORD_BOT_TOKEN=your-bot-token
   ```

5. In the Discord Developer Portal, configure the bot and enable any
   privileged intents required by your installation. Invite the bot with
   permission to use application commands and send/edit messages and embeds.
   The card emoji IDs in `config.json` must be usable where the bot is
   installed.
6. Start the bot from the project root:

   ```sh
   python bot.py
   ```

Keep the `.env` file private; do not share or commit your bot token.

## Commands

- `/ping` (also available as `!ping`) — show the bot's latency.
- `/flip` (also available as `!flip`) — flip a coin.
- `/bj` (also available as `!bj`) — post a challenge that another user can
  accept to start a Blackjack game.

## How Blackjack games work

This is a head-to-head game: there is no dealer, and each player competes
against the other to get as close to 21 as possible without going over.

1. The first player to use `/bj` (or `!bj`) sends a challenge. Another user
   accepts it with the checkmark button. The challenger goes first.
2. A new game creates and shuffles a standard 52-card deck (one of each rank
   in each of the four suits). Four cards are dealt alternately: the first
   and third go to the challenger, and the second and fourth go to the player
   who accepted.
3. Players take turns using **Hit** to draw the next card from the deck or
   **Stand** to pass their turn. The game ends as soon as someone busts, or
   when both players have stood in succession.
4. If a player busts (their best possible total is over 21), the other player
   wins. Otherwise, when both players stand, the player whose best total is
   closest to 21 wins. Equal distances are a tie.

Number cards count as their face value, and Jacks, Queens, and Kings count as
10. Aces can count as either 1 or 11. The game calculates and displays
possible totals for hands with Aces: for example, an Ace and a 6 can total
7 or 17. These are commonly called **soft** and **hard** totals. The best
usable total is the one closest to 21 without going over; if every available
total is over 21, the hand is bust.

Standing passes the current turn; it is not a permanent lock. If the other
player takes another action, the turn comes back around, and the first player
can choose again. A player who hits has their stood status cleared. There
are no splits, doubles, insurance, dealer hand, or natural-blackjack
payouts.

## Shuffle, dealing, and fairness

The deck is shuffled separately for each game, and cards are drawn from that
shuffled deck without replacement. Alternating the four starting cards gives
each player one card from each of the first two deal rounds. Both hands and
the current totals are shown to both players in the game message; there are
no hidden player cards.

These are procedural fairness measures, not a cryptographic proof that a
game was fair. The bot uses Python's `random.shuffle`; it does not publish a
committed shuffle seed, reveal the deck order, or provide an independent
verification mechanism. Players must trust the bot process and its
implementation for the shuffle and card dealing.

Because each game uses one deck and revealed cards are not returned to it,
players can **technically count cards**: they can keep track of the visible
cards and reason about which ranks remain more or less likely to be drawn.
This is ordinary inference from the known deck composition, not access to
the undealt card order. The bot does not expose that order or provide a
counting aid.

## Game lifecycle

Active games are held in memory and time out after five minutes without a
turn. The bot checks for expired games every 30 seconds and attempts to
replace the game message with a timeout notice. Active game state is not
persisted, so restarting the bot clears it.

## Configuration

`config.json` maps card names such as `HeartsA` and `Spades10` to Discord
custom emoji strings. Keep the keys in the format expected by the game and
ensure the referenced emojis remain available to the bot.

---

This README was written by AI, but the code wasn't.
