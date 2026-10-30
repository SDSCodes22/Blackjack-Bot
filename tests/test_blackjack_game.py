import unittest
from unittest.mock import AsyncMock, patch

from cogs import blackjack_cog
from cogs.blackjack_cog import BlackjackGame


class FakeAvatar:
    def __init__(self, url="https://example.test/avatar.png"):
        self.url = url


class FakeUser:
    def __init__(self, user_id, display_name=None, avatar_url="https://example.test/avatar.png"):
        self.id = user_id
        self.display_name = display_name or f"Player {user_id}"
        self.mention = f"<@{user_id}>"
        self.avatar = FakeAvatar(avatar_url)
        self.default_avatar = FakeAvatar(f"https://example.test/default-{user_id}.png")

    @property
    def display_avatar(self):
        return self.avatar if self.avatar.url else self.default_avatar

    def __hash__(self):
        return hash(self.id)

    def __eq__(self, other):
        return isinstance(other, FakeUser) and self.id == other.id


class BlackjackGameTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.player1 = FakeUser(1, "Alice")
        self.player2 = FakeUser(2, "Bob")
        self.message = object()
        starting_deck = [
            ("2", "Hearts"),
            ("3", "Hearts"),
            ("4", "Hearts"),
            ("5", "Hearts"),
            ("6", "Hearts"),
        ]
        with patch.object(BlackjackGame, "create_deck", return_value=starting_deck.copy()):
            self.game = BlackjackGame(self.player1, self.player2, self.message)

    def set_hands(self, player1, player2):
        self.game.hands = {
            self.player1: list(player1),
            self.player2: list(player2),
        }

    def test_create_deck_has_one_card_for_each_rank_and_suit(self):
        """Checks the deck contains 52 unique rank/suit cards and gets shuffled."""
        with patch.object(blackjack_cog.random, "shuffle") as shuffle:
            deck = BlackjackGame.create_deck(object())

        expected = {
            (rank, suit)
            for suit in ("Hearts", "Diamonds", "Clubs", "Spades")
            for rank in ("2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A")
        }
        self.assertEqual(len(deck), 52)
        self.assertEqual(set(deck), expected)
        shuffle.assert_called_once_with(deck)

    def test_initialization_deals_alternating_cards_and_starts_player_one(self):
        """Checks construction deals alternating cards, initializes turn state, and keeps the message."""
        self.assertEqual(self.game.hands[self.player1], [("6", "Hearts"), ("4", "Hearts")])
        self.assertEqual(self.game.hands[self.player2], [("5", "Hearts"), ("3", "Hearts")])
        self.assertEqual(self.game.deck, [("2", "Hearts")])
        self.assertEqual(self.game.current_player, self.player1)
        self.assertEqual(self.game.has_stood, {self.player1: False, self.player2: False})
        self.assertIs(self.game.message, self.message)

    def test_dealing_requires_four_cards_and_preserves_alternating_order(self):
        """Checks the four top cards are dealt in alternating order without replacing the remaining deck."""
        self.game.deck = [
            ("2", "Hearts"),
            ("3", "Hearts"),
            ("4", "Hearts"),
            ("5", "Hearts"),
            ("6", "Hearts"),
        ]

        hands = self.game.deal_starting_hands()

        self.assertEqual(hands[self.player1], [("6", "Hearts"), ("4", "Hearts")])
        self.assertEqual(hands[self.player2], [("5", "Hearts"), ("3", "Hearts")])
        self.assertEqual(self.game.deck, [("2", "Hearts")])

    def test_dealing_short_deck_raises_without_silent_fallback(self):
        """Checks dealing fails explicitly when fewer than four cards are available."""
        self.game.deck = [("2", "Hearts"), ("3", "Hearts"), ("4", "Hearts")]

        with self.assertRaises(IndexError):
            self.game.deal_starting_hands()

    def test_calculate_score_handles_number_and_face_cards(self):
        """Checks number cards use face value and face cards each count as ten."""
        hand = [
            ("2", "Hearts"),
            ("10", "Diamonds"),
            ("J", "Clubs"),
            ("Q", "Spades"),
            ("K", "Hearts"),
        ]

        self.assertEqual(self.game.calculate_score(hand), [42])

    def test_calculate_score_returns_one_score_without_aces(self):
        """Checks a hand without aces has one total."""
        self.assertEqual(
            self.game.calculate_score([("7", "Hearts"), ("8", "Clubs")]),
            [15],
        )

    def test_calculate_score_returns_soft_and_hard_ace_values(self):
        """Checks an ace can contribute either eleven or one when both totals are possible."""
        self.assertEqual(
            self.game.calculate_score([("A", "Hearts"), ("6", "Clubs")]),
            [17, 7],
        )

    def test_calculate_score_downgrades_aces_when_eleven_would_bust(self):
        """Checks ace scoring includes a lower non-busting total when an ace is reduced to one."""
        self.assertEqual(
            self.game.calculate_score([("A", "Hearts"), ("A", "Clubs"), ("9", "Diamonds")]),
            [21, 11],
        )

    def test_calculate_score_handles_many_aces_and_removes_duplicate_totals(self):
        """Checks multiple aces produce valid unique totals."""
        self.assertEqual(
            self.game.calculate_score(
                [("A", "Hearts"), ("A", "Clubs"), ("A", "Diamonds"), ("A", "Spades")]
            ),
            [14, 4],
        )

    def test_calculate_score_does_not_return_bust_total_when_many_aces_have_valid_total(self):
        """Checks many aces do not produce a bust total that could beat a valid hand."""
        hand = [("A", "Hearts")] * 12

        self.assertEqual(self.game.calculate_score(hand), [12])

    def test_calculate_score_keeps_over_21_values_for_busted_hands(self):
        """Checks a hand with no usable ace still reports its over-21 total."""
        self.assertEqual(
            self.game.calculate_score([("10", "Hearts"), ("9", "Clubs"), ("5", "Spades")]),
            [24],
        )

    def test_calculate_score_of_empty_hand_is_zero(self):
        """Checks an empty hand has a total of zero."""
        self.assertEqual(self.game.calculate_score([]), [0])

    def test_is_bust_uses_lowest_usable_total(self):
        """Checks bust status depends on whether every possible hand total exceeds 21."""
        self.set_hands(
            [("10", "Hearts"), ("8", "Clubs"), ("5", "Spades")],
            [("A", "Hearts"), ("9", "Clubs")],
        )

        self.assertTrue(self.game.is_bust(self.player1))
        self.assertFalse(self.game.is_bust(self.player2))

    def test_is_bust_at_21_is_false(self):
        """Checks a hand totaling exactly 21 is not considered a bust."""
        self.set_hands([("10", "Hearts"), ("A", "Clubs")], [("2", "Hearts")])

        self.assertFalse(self.game.is_bust(self.player1))

    def test_hit_draws_card_updates_hand_turn_and_stood_state(self):
        """Checks a hit draws one card, clears that player's stood flag, switches turn, and updates activity time."""
        self.game.deck = [("7", "Spades")]
        self.game.has_stood[self.player1] = True
        self.game.current_player = self.player1
        original_hand = self.game.hands[self.player1].copy()

        with patch.object(blackjack_cog.time, "time", return_value=1234.5):
            drawn = self.game.turn(True)

        self.assertEqual(drawn, ("7", "Spades"))
        self.assertEqual(self.game.hands[self.player1], original_hand + [drawn])
        self.assertEqual(self.game.deck, [])
        self.assertEqual(self.game.current_player, self.player2)
        self.assertFalse(self.game.has_stood[self.player1])
        self.assertEqual(self.game.last_turn_time, 1234.5)

    def test_hit_returns_the_card_and_does_not_change_other_players_hand(self):
        """Checks a hit returns the drawn card and leaves the opponent's hand unchanged."""
        self.game.deck = [("8", "Spades")]
        other_hand = self.game.hands[self.player2].copy()

        self.assertEqual(self.game.turn(True), ("8", "Spades"))
        self.assertEqual(self.game.hands[self.player2], other_hand)

    def test_stand_switches_turn_without_drawing_or_changing_hand(self):
        """Checks standing marks the player as stood and switches turn without drawing a card."""
        original_deck = self.game.deck.copy()
        original_hand = self.game.hands[self.player1].copy()

        result = self.game.turn(False)

        self.assertIsNone(result)
        self.assertEqual(self.game.deck, original_deck)
        self.assertEqual(self.game.hands[self.player1], original_hand)
        self.assertTrue(self.game.has_stood[self.player1])
        self.assertEqual(self.game.current_player, self.player2)

    def test_hit_with_empty_deck_raises_and_does_not_change_hand_or_turn(self):
        """Checks a hit with no cards raises and does not append a card or switch the current player."""
        self.game.deck = []
        original_hand = self.game.hands[self.player1].copy()

        with patch.object(blackjack_cog.time, "time", return_value=5678.0):
            with self.assertRaises(IndexError):
                self.game.turn(True)

        self.assertEqual(self.game.hands[self.player1], original_hand)
        self.assertEqual(self.game.current_player, self.player1)
        self.assertEqual(self.game.last_turn_time, 5678.0)

    def test_game_is_not_over_at_start_or_after_only_one_player_stands(self):
        """Checks the game continues initially and after just one player stands."""
        self.assertFalse(self.game.is_game_over())
        self.game.turn(False)

        self.assertFalse(self.game.is_game_over())

    def test_game_ends_when_both_players_stand(self):
        """Checks the game ends once both players have stood."""
        self.game.has_stood = {self.player1: True, self.player2: True}

        self.assertTrue(self.game.is_game_over())

    def test_game_does_not_end_when_only_player_one_has_stood(self):
        """Checks one player's stand alone does not end the game."""
        self.game.has_stood = {self.player1: True, self.player2: False}

        self.assertFalse(self.game.is_game_over())

    def test_game_does_not_end_when_only_player_two_has_stood_and_case_three_does_not_apply(self):
        """Checks the game continues when player two stands but still leads player one's hand."""
        self.set_hands([("10", "Hearts"), ("8", "Clubs")], [("10", "Diamonds"), ("9", "Spades")])
        self.game.current_player = self.player1
        self.game.has_stood = {self.player1: False, self.player2: True}

        self.assertFalse(self.game.is_game_over())

    def test_game_ends_when_player_two_stands_and_player_one_has_a_higher_score(self):
        """Checks case three ends play when player two stood and player one's score catches up or passes it."""
        self.set_hands([("10", "Hearts"), ("9", "Clubs")], [("10", "Diamonds"), ("8", "Spades")])
        self.game.current_player = self.player1
        self.game.has_stood = {self.player1: False, self.player2: True}

        self.assertTrue(self.game.is_game_over())

    def test_case_four_ends_game_for_its_documented_state(self):
        """Checks case four's stated hand, stand, turn-count, and score conditions trigger game end."""
        self.set_hands([("10", "Hearts"), ("2", "Clubs")], [("10", "Diamonds"), ("8", "Spades")])
        self.game.current_player = self.player1
        self.game.has_stood = {self.player1: False, self.player2: True}
        self.game.turns_played = 2

        self.assertTrue(self.game.is_game_over())

    def test_case_four_ends_game_after_documented_first_turn_sequence(self):
        """Checks case four after player one hits and player two stands during the opening round."""
        self.set_hands([("10", "Hearts"), ("2", "Clubs")], [("10", "Diamonds"), ("8", "Spades")])
        self.game.deck = [("3", "Clubs")]

        self.game.turn(True)
        self.game.turn(False)

        self.assertEqual(self.game.turns_played, 2)
        self.assertEqual(self.game.current_player, self.player1)
        self.assertEqual(self.game.has_stood, {self.player1: False, self.player2: True})
        self.assertLess(
            max(self.game.calculate_score(self.game.hands[self.player1])),
            max(self.game.calculate_score(self.game.hands[self.player2])),
        )
        self.assertTrue(self.game.is_game_over())

    def test_game_ends_when_either_player_busts(self):
        """Checks a bust by either player independently ends the game."""
        self.set_hands(
            [("10", "Hearts"), ("8", "Clubs"), ("5", "Spades")],
            [("10", "Diamonds"), ("7", "Clubs")],
        )
        self.assertTrue(self.game.is_game_over())

        self.set_hands(
            [("10", "Hearts"), ("7", "Clubs")],
            [("10", "Diamonds"), ("8", "Spades"), ("5", "Hearts")],
        )
        self.assertTrue(self.game.is_game_over())

    def test_get_who_won_rejects_nonterminal_game(self):
        """Checks winner lookup is expected to reject a game that has not ended."""
        with self.assertRaises(ValueError):
            self.game.get_who_won()

    def test_get_who_won_selects_other_player_when_player_one_busts(self):
        """Checks player two is selected as winner when player one busts."""
        self.set_hands(
            [("10", "Hearts"), ("8", "Clubs"), ("5", "Spades")],
            [("10", "Diamonds"), ("7", "Clubs")],
        )

        self.assertEqual(self.game.get_who_won(), self.player2)

    def test_get_who_won_selects_other_player_when_player_two_busts(self):
        """Checks player one is selected as winner when player two busts."""
        self.set_hands(
            [("10", "Hearts"), ("7", "Clubs")],
            [("10", "Diamonds"), ("8", "Spades"), ("5", "Hearts")],
        )

        self.assertEqual(self.game.get_who_won(), self.player1)

    def test_get_who_won_compares_best_scores_when_both_players_stand(self):
        """Checks the closer hand wins once both players have stood."""
        self.set_hands([("10", "Hearts"), ("9", "Clubs")], [("10", "Diamonds"), ("8", "Spades")])
        self.game.has_stood = {self.player1: True, self.player2: True}

        self.assertEqual(self.game.get_who_won(), self.player1)

    def test_get_who_won_returns_none_for_a_standstill_tie(self):
        """Checks equal best totals produce no winner."""
        self.set_hands([("10", "Hearts"), ("9", "Clubs")], [("10", "Diamonds"), ("9", "Spades")])
        self.game.has_stood = {self.player1: True, self.player2: True}

        self.assertIsNone(self.game.get_who_won())

    def test_soft_hand_wins_using_closest_nonbusting_total(self):
        """Checks winner comparison uses the ace value closest to 21 without busting."""
        self.set_hands([("A", "Hearts"), ("9", "Clubs")], [("10", "Diamonds"), ("8", "Spades")])
        self.game.has_stood = {self.player1: True, self.player2: True}

        self.assertEqual(self.game.calculate_score(self.game.hands[self.player1]), [20, 10])
        self.assertEqual(self.game.get_who_won(), self.player1)

    async def test_live_embed_is_rejected_after_game_ends(self):
        """Checks a live-game embed is expected to be unavailable once the game has ended."""
        self.game.has_stood = {self.player1: True, self.player2: True}

        with self.assertRaises(TypeError):
            await self.game.get_game_embed()

    async def test_live_embed_is_rejected_if_a_player_busts(self):
        """Checks a live-game embed is expected to be unavailable after a bust."""
        self.set_hands(
            [("10", "Hearts"), ("8", "Clubs"), ("5", "Spades")],
            [("10", "Diamonds"), ("7", "Clubs")],
        )

        with self.assertRaises(TypeError):
            await self.game.get_game_embed()

    def test_end_embed_is_rejected_before_game_ends(self):
        """Checks an end-of-game embed is expected to be unavailable before the game ends."""
        with self.assertRaises(ValueError):
            self.game.get_end_state_embed()

    async def test_live_embed_shows_turn_players_hands_and_possible_scores(self):
        """Checks the live embed includes the current player, both hands, possible scores, color, and avatar."""
        self.set_hands([("A", "Hearts"), ("6", "Clubs")], [("10", "Diamonds"), ("7", "Spades")])
        self.game.current_player = self.player1
        with (
            patch.object(
                blackjack_cog,
                "get_average_avatar_color",
                new_callable=AsyncMock,
                return_value=0x123456,
            ),
            patch.object(blackjack_cog, "get_emoji", side_effect=lambda key: f"[{key}]"),
        ):
            embed = await self.game.get_game_embed()

        self.assertIn("<@1>'s turn", embed.description)
        self.assertIn("Alice's Hand (17/7)", embed.description)
        self.assertIn("Bob's Hand (17)", embed.description)
        self.assertIn("[HeartsA][Clubs6]", embed.description)
        self.assertEqual(embed.thumbnail.url, self.player1.avatar.url)
        self.assertEqual(embed.color.value, 0x123456)

    async def test_live_embed_uses_default_avatar_when_custom_avatar_is_missing(self):
        """Checks a user's default profile avatar is used for thumbnail and color when no custom avatar exists."""
        self.player1.avatar.url = None
        self.game.current_player = self.player1
        with (
            patch.object(
                blackjack_cog,
                "get_average_avatar_color",
                new_callable=AsyncMock,
                return_value=0xABCDEF,
            ) as get_color,
            patch.object(blackjack_cog, "get_emoji", side_effect=lambda key: key),
        ):
            embed = await self.game.get_game_embed()

        self.assertEqual(embed.thumbnail.url, self.player1.default_avatar.url)
        self.assertEqual(embed.color.value, 0xABCDEF)
        get_color.assert_awaited_once_with(self.player1.default_avatar.url)

    def test_end_embed_reports_bust_winner(self):
        """Checks a bust end embed names the winner and displays each hand's relevant total."""
        self.set_hands(
            [("10", "Hearts"), ("8", "Clubs"), ("5", "Spades")],
            [("10", "Diamonds"), ("7", "Clubs")],
        )
        with patch.object(blackjack_cog, "get_emoji", side_effect=lambda key: f"[{key}]"):
            embed = self.game.get_end_state_embed()

        self.assertIn("<@1> has busted! <@2> wins!", embed.description)
        self.assertIn("Alice's Hand (23)", embed.description)
        self.assertIn("Bob's Hand (17)", embed.description)
        self.assertEqual(embed.thumbnail.url, self.player2.avatar.url)

    def test_end_embed_uses_winners_default_avatar_without_custom_avatar(self):
        """Checks the end embed uses the winner's default profile avatar when their custom avatar is missing."""
        self.set_hands(
            [("10", "Hearts"), ("8", "Clubs"), ("5", "Spades")],
            [("10", "Diamonds"), ("7", "Clubs")],
        )
        self.player2.avatar.url = None
        with patch.object(blackjack_cog, "get_emoji", side_effect=lambda key: f"[{key}]"):
            embed = self.game.get_end_state_embed()

        self.assertEqual(embed.thumbnail.url, self.player2.default_avatar.url)

    def test_end_embed_reports_stand_winner_and_resolved_scores(self):
        """Checks a stand end embed names the winner and shows the scores used to compare hands."""
        self.set_hands([("10", "Hearts"), ("9", "Clubs")], [("10", "Diamonds"), ("8", "Spades")])
        self.game.has_stood = {self.player1: True, self.player2: True}
        with patch.object(blackjack_cog, "get_emoji", side_effect=lambda key: f"[{key}]"):
            embed = self.game.get_end_state_embed()

        self.assertIn("Both players have stood.", embed.description)
        self.assertIn("<@1> was closer to 21 and wins!", embed.description)
        self.assertIn("Alice's Hand (19)", embed.description)
        self.assertIn("Bob's Hand (18)", embed.description)

    def test_end_embed_reports_tie(self):
        """Checks a tied end embed announces the tie and displays both players' totals."""
        self.set_hands([("10", "Hearts"), ("9", "Clubs")], [("10", "Diamonds"), ("9", "Spades")])
        self.game.has_stood = {self.player1: True, self.player2: True}
        with patch.object(blackjack_cog, "get_emoji", side_effect=lambda key: f"[{key}]"):
            embed = self.game.get_end_state_embed()

        self.assertIn("The game has tied.", embed.description)
        self.assertIn("Alice's Hand (19)", embed.description)
        self.assertIn("Bob's Hand (19)", embed.description)

    def test_tied_end_embed_uses_current_players_default_avatar(self):
        """Checks the tie embed uses the current player's default avatar when no winner is available."""
        self.set_hands([("10", "Hearts"), ("9", "Clubs")], [("10", "Diamonds"), ("9", "Spades")])
        self.game.has_stood = {self.player1: True, self.player2: True}
        self.player1.avatar.url = None
        self.game.current_player = self.player1
        with patch.object(blackjack_cog, "get_emoji", side_effect=lambda key: f"[{key}]"):
            embed = self.game.get_end_state_embed()

        self.assertEqual(embed.thumbnail.url, self.player1.default_avatar.url)


if __name__ == "__main__":
    unittest.main()
