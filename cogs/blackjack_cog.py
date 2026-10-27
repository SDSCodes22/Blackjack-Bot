from typing import Type
import discord
from discord.ext import commands 
import random
from utils import *


# Blackjack Game Model 
class BlackjackGame:
    def __init__(self, player1: discord.User, player2: discord.User):
        self.player1 = player1
        self.player2 = player2
        self.deck = self.create_deck()
        self.hands = self.deal_starting_hands()
        self.has_stood = {player1: False, player2: False}
        self.is_won = False
        self.current_player = player1
    
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
        if self.is_won: raise TypeError("get_game_embed() was called when the game was in a Won state")
        if self.is_bust(self.player1) or self.is_bust(self.player2): raise TypeError("get_game_embed() was called when the game was in a Won state")

        # Calculate the average colour of the user's profile picture
        color = discord.Color.blurple()
        if self.current_player.avatar.url:
            color = get_average_avatar_color(self.current_player.avatar.url)
        p1_scores = self.calculate_score(self.hands[self.player1])
        p2_scores = self.calculate_score(self.hands[self.player2])
        embed = discord.Embed(
            author=discord.EmbedAuthor(name=f"{self.player1.display_name} vs. {self.player2.display_name}"),
            thumbnail=self.current_player.avatar.url,
            description=f"{self.current_player.mention}'s turn",
            fields=[
                discord.EmbedField(f"{self.player1.display_name}'s Hand ({'/'.join([str(i) for i in p1_scores])})",
                                    ''.join([get_emoji(f"{key[0].title()}{key[1]}") for key in self.hands[self.player1]])),
                discord.EmbedField(f"{self.player2.display_name}'s Hand ({'/'.join([str(i) for i in p2_scores])})",
                                    ''.join([get_emoji(f"{key[0].title()}{key[1]}") for key in self.hands[self.player2]])),                    
            ],
            color=color
        )
        return embed
    
    def turn(self, did_hit: bool):
        """Modifies internal state to account for turn e.g. dealing card, changing stand counter, modify current player.
        DOES NOT check for wins OR post new game embed

        Args:
            did_hit (bool): Whether the current player hit, or if they stood.
        """
        if not did_hit:
            # 1. Update has_stood
            self.has_stood[self.current_player] = True
            # Hands and deck aren't updated 
            self.current_player = self.player1 if self.current_player == self.player2 else self.player2
            return 
        # 1. Deal new card
        new_card = self.deck.pop()
        self.hands[self.current_player].append(new_card)
        # 2. Update current player
        self.current_player = self.player1 if self.current_player == self.player2 else self.player2

class BlackjackCog(commands.Cog):
    def __init__(self, bot): 
        self.bot = bot
    
def setup(bot):
    bot.add_cog(BlackjackCog(bot))