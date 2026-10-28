from multiprocessing import Value
from typing import Type, Union
import discord
from discord.ext import commands, bridge, tasks
from loguru import logger as log
import random
from utils import *
import time 


def _as_user(user: discord.User | discord.Member) -> discord.User:
    return user._user if isinstance(user, discord.Member) else user


# Blackjack Game Model 
class BlackjackGame:
    def __init__(self, player1: discord.User, player2: discord.User, message: discord.Message):
        self.player1 = player1
        self.player2 = player2
        self.message = message
        self.deck = self.create_deck()
        self.hands = self.deal_starting_hands()
        self.has_stood = {player1: False, player2: False}
        self.current_player = player1
        self.last_turn_time = time.time()
    
    def create_deck(self):
        """
        Creates a deck where each card is defined as ("Suit", "Rank")

        Returns:
            list: Deck of cards as a list of tuples.
        NOTE: self.deck is not automatically set to the output of this function
        """
        suits = ['Hearts', 'Diamonds', 'Clubs', 'Spades']
        ranks = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A'] 
        deck = [(rank, suit) for suit in suits for rank in ranks]
        random.shuffle(deck)
        return deck

    def deal_starting_hands(self) -> dict[discord.User, list[tuple[str, str]]]:
        """
        Deal alternating cards to the 2 players (for maximum fairness!)

        NOTE: self.hands is not automatically set to the output of this function
        """
        cards = [self.deck.pop() for _ in range(4)]  # Draw 4 cards
        return {
            self.player1: [cards[0], cards[2]],  # Player 1 gets the 1st and 3rd card
            self.player2: [cards[1], cards[3]]   # Player 2 gets the 2nd and 4th card
        }
    
    def calculate_score(self, hand: list[tuple[str, str]]) -> list[int]:
        """
        Calculate the score of a hand. Aces can be worth 1 or 11.

        Args:
            hand (list): List of cards in the hand.

        Returns:
            list: Possible scores for the hand.
        """
        scores = []
        score = 0
        aces = 0
        for rank, _ in hand:
            if rank in ['J', 'Q', 'K']:
                score += 10
            elif rank == 'A':
                aces += 1
                # Don't intitially add 11 for Aces; handle them after the loop
            else:
                score += int(rank)
        # Score contains the value of all non-Ace cards. Now handle Aces.
        scores = [score]  # Start with the score without Aces
        for i in range(1, aces + 1):
            # For each Ace, first consider it as 11, then as 1. This gives us two possible scores for each Ace, so scores will usually double in size with each Ace.
            scores = [score + 11 for score in scores if score + 11 <= 21] + [score + 1 for score in scores]
        # Return all possible scores, including those over 21 if the current player has busted
        return list(dict.fromkeys(scores)) # Remove duplicates
    
    def is_bust(self, player: discord.User) -> bool:
        """Returns whether a given player has busted

        Args:
            player (discord.User): The player in question

        Returns:
            bool: Whether the player has busted
        """
        hand = self.hands[player]
        scores = self.calculate_score(hand)
        return min(scores) > 21
    
    def get_game_embed(self) -> discord.Embed:
        """
        Generates an embed with the current state of the game

        Returns:
            discord.Embed: The embed representing the game's current state
        NOTE: This should not be used if the game is in a Won state
        """
        if self.is_game_over(): raise TypeError("get_game_embed() was called when the game was in a Won state")
        if self.is_bust(self.player1) or self.is_bust(self.player2): raise TypeError("get_game_embed() was called when the game was in a Won state")

        # Calculate the average colour of the user's profile picture
        color = discord.Color.blurple()
        if self.current_player.avatar.url:
            color = get_average_avatar_color(self.current_player.avatar.url)
        p1_scores = self.calculate_score(self.hands[self.player1])
        p2_scores = self.calculate_score(self.hands[self.player2])

        description = f"{self.current_player.mention}'s turn\n\n**{self.player1.display_name}'s Hand ({'/'.join([str(i) for i in p1_scores])})**\n# {''.join([get_emoji(f"{key[1].title()}{key[0]}") for key in self.hands[self.player1]])}\n\n**{self.player2.display_name}'s Hand ({'/'.join([str(i) for i in p2_scores])})**\n# {''.join([get_emoji(f"{key[1].title()}{key[0]}") for key in self.hands[self.player2]])}"
        embed = discord.Embed(
            author=discord.EmbedAuthor(name=f"{self.player1.display_name} vs. {self.player2.display_name}"),
            thumbnail=self.current_player.avatar.url,
            description=description,
            color=color
        )
        return embed
    def get_end_state_embed(self) -> discord.Embed:
        """
        Generates an embed for the game when it has ended

        Returns:
            discord.Embed: The embed in question
        """
        if not self.is_game_over(): raise ValueError("get_end_state_embed() was called when game was not in a Won state")
        # We need to get the scores actually considered for getting the winner
        p1_scores = self.calculate_score(self.hands[self.player1])
        p2_scores = self.calculate_score(self.hands[self.player2])
        p1_score = ""
        p2_score = ""

        # Case 1. It's a bust
        description = ""
        winner = self.get_who_won()
        if self.is_bust(self.player1):
            description = f"{self.player1.mention} has busted! {self.player2.mention} wins!"
            p1_score = str(min(p1_scores))
            p2_score = '/'.join([str(i) for i in p2_scores])
        elif self.is_bust(self.player2):
            description = f"{self.player2.mention} has busted! {self.player1.mention} wins!"
            p2_score = str(min(p2_scores))
            p1_score = '/'.join([str(i) for i in p1_scores])
    
        # Case 2: Both players stood
        else:
            if winner:
                description = f"Both players have stood.\n{winner.mention} was closer to 21 and wins!"
            else:
                description = f"The game has tied."
            p1_diff = min([abs(i - 21) for i in p1_scores])
            p2_diff = min([abs(i - 21) for i in p2_scores])
            p1_score = str(21 - p1_diff)
            p2_score = str(21 - p2_diff)

        description += f"\n\n**{self.player1.display_name}'s Hand ({p1_score})**\n# {''.join([get_emoji(f"{key[1].title()}{key[0]}") for key in self.hands[self.player1]])}\n\n**{self.player2.display_name}'s Hand ({p2_score})**\n# {''.join([get_emoji(f"{key[1].title()}{key[0]}") for key in self.hands[self.player2]])}"

        embed = discord.Embed(
            author=discord.EmbedAuthor(name=f"{self.player1.display_name} vs. {self.player2.display_name}"),
            thumbnail=winner.avatar.url if winner else self.current_player.avatar.url,
            description = description,
            color=discord.Color.green() if winner else discord.Color.from_rgb(250, 245, 255)
        )
        return embed
        
    def turn(self, did_hit: bool):
        """Modifies internal state to account for turn e.g. dealing card, changing stand counter, modify current player.
        DOES NOT check for wins OR post new game embed

        Args:
            did_hit (bool): Whether the current player hit, or if they stood.
        """
        self.last_turn_time = time.time()
        if not did_hit:
            # 1. Update has_stood
            self.has_stood[self.current_player] = True
            # Hands and deck aren't updated 
            self.current_player = self.player1 if self.current_player == self.player2 else self.player2
            return 
        # 1. Deal new card
        new_card = self.deck.pop()
        self.hands[self.current_player].append(new_card)
        # 2. Update has_stood
        self.has_stood[self.current_player] = False
        # 3. Update current player
        self.current_player = self.player1 if self.current_player == self.player2 else self.player2
        return new_card
    
    def is_game_over(self) -> bool:
        """
        Should be called directly after turn(). Determines if the game is over to produce a winner or create a tie, or whether the game should progress to 
        the next turn

        Returns:
            bool: Whether the game is over            
        """
        # Case 1: Both players have stood in their last turn 
        if list(self.has_stood.values())[0] and list(self.has_stood.values())[1]:
            return True
        # Case 2: One of the players has bust
        if self.is_bust(self.player1) or self.is_bust(self.player2):
            return True 
        return False
    
    def get_who_won(self) -> Union[discord.User, None]:
        """
        If the game is in a won state, then determine which player is victorious, or if it is a tie.

        Returns:
            Union[discord.User, None]: The player who has won the game, or None if it is a tie.
        """
        if not self.is_game_over(): raise ValueError("get_who_won() was called when game is not in a won state")
        # Case 1: One of the players has bust - the other player must be the winner.
        if self.is_bust(self.player1):
            return self.player2 
        elif self.is_bust(self.player2):
            return self.player1 
        # Case 2: Both players have stood, so we get who has the closest score to 21 
        p1_scores = self.calculate_score(self.hands[self.player1])
        p2_scores = self.calculate_score(self.hands[self.player2])

        p1_diff = min([abs(i - 21) for i in p1_scores])
        p2_diff = min([abs(i - 21) for i in p2_scores])
        if p1_diff > p2_diff:
            return self.player2
        elif p2_diff > p1_diff:
            return self.player1
        else:
            return None
        
class BlackjackGameView(discord.ui.View):
    def __init__(self, game: BlackjackGame, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.game = game 
    
    @discord.ui.button(label="Hit", style=discord.ButtonStyle.blurple)
    async def hit(self, button: discord.Button, interaction: discord.Interaction):
        user = _as_user(interaction.user)
        # 1. Make sure that the user is the person is the person whose turn it is
        if user != self.game.current_player and user in self.game.hands.keys():
            await interaction.respond("It's not your turn!", ephemeral=True)
            return
        elif user != self.game.current_player:
            await interaction.respond("You're not part of this game!", ephemeral=True)
        # 2. Process turn
        self.game.turn(True)
        # 3. Check if it is a win, and if so, handle win state
        if self.game.is_game_over():
            end_embed = self.game.get_end_state_embed()
            self.disable_all_items()
            await interaction.response.edit_message(embed=end_embed, view=self)
            return 
        # 4. Else, continue on with game
        embed = self.game.get_game_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="Stand", style=discord.ButtonStyle.green)
    async def stand(self, button: discord.Button, interaction: discord.Interaction):
        user = _as_user(interaction.user)
        # 1. Make sure that the user is the person is the person whose turn it is
        if user != self.game.current_player and user in self.game.hands.keys():
            await interaction.respond("It's not your turn!", ephemeral=True)
            return
        elif user != self.game.current_player:
            await interaction.respond("You're not part of this game!", ephemeral=True)
        # 2. Process turn
        self.game.turn(False)
        # 3. Check if it is a win, and if so, handle win state
        if self.game.is_game_over():
            end_embed = self.game.get_end_state_embed()
            self.disable_all_items()
            await interaction.response.edit_message(embed=end_embed, view=self)
            return 
        # 4. Else, continue on with game
        embed = self.game.get_game_embed()
        await interaction.response.edit_message(embed=embed, view=self)
        
class RequestBJGameView(discord.ui.View):
    def __init__(self, player1: discord.User, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.player1 = player1
    
    @discord.ui.button(emoji="<:checkmark:1565005454956957696>", style=discord.ButtonStyle.green)
    async def create_game(self, button: discord.Button, interaction: discord.Interaction):
        player2 = _as_user(interaction.user)
        if player2 == self.player1:
            await interaction.respond("You cannot play against yourself!", ephemeral=True)
            return
        # 1. Make a BlackjackGame instance
        game = BlackjackGame(self.player1, player2, interaction.message)
        # 2. Add to ongoing games
        ONGOING_GAMES[interaction.message.id] = game 
        # 3. Edit message with embed 
        await interaction.response.edit_message(embed=game.get_game_embed(), view=BlackjackGameView(game))
    

ONGOING_GAMES = {}

class BlackjackCog(commands.Cog):
    def __init__(self, bot): 
        self.bot = bot
        self.expire_inactive_games.start()

    def cog_unload(self):
        self.expire_inactive_games.cancel()

    @tasks.loop(seconds=30)
    async def expire_inactive_games(self):
        current_time = time.time()
        for message_id, game in list(ONGOING_GAMES.items()):
            if current_time - game.last_turn_time <= 300:
                continue

            if ONGOING_GAMES.get(message_id) is not game:
                continue

            del ONGOING_GAMES[message_id]
            timed_out_embed = discord.Embed(
                description="This game timed out.",
                color=discord.Color.dark_grey(),
            )
            try:
                await game.message.edit(embed=timed_out_embed, view=None)
            except discord.NotFound:
                pass
            except discord.Forbidden as error:
                log.warning(
                    "Could not edit timed-out game message {}: {}",
                    message_id,
                    error,
                )

    @expire_inactive_games.before_loop
    async def before_expire_inactive_games(self):
        await self.bot.wait_until_ready()

    @bridge.bridge_command(description="Challenge someone to a game of Blackjack!", integration_types=[discord.IntegrationType.guild_install, discord.IntegrationType.user_install])
    async def bj(self, ctx: bridge.BridgeContext):            
        await ctx.respond(embed=discord.Embed(
            description=f"Click the button below to play Blackjack with {ctx.author.mention if ctx.is_app else ctx.message.author.mention}",
            color=discord.Color.blurple()
        ),view=RequestBJGameView(_as_user(ctx.author if ctx.is_app else ctx.message.author)))


    
def setup(bot):
    bot.add_cog(BlackjackCog(bot))