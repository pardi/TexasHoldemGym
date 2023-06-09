"""Functions for the defining the texas holdem game."""

import random
from enum import Enum

from deckcard import Deck, covert_to_human_readable

from gym import Env, spaces


class Player:
    """Player for the Texas Holdem card game."""

    def __init__(self, id_in: int, stack: float):
        """Init the player class."""
        self.id = id_in
        self.stack = stack
        self.cards = []
        self.is_active = True
        self.is_all_in = False
        self.is_dealer = False
        self.is_small_blind = False
        self.is_big_blind = False

    def __str__(self):
        """Print the player as a text."""
        return f'Player {self.id} has {self.stack} chips'

    def reset(self):
        """Reset the player class."""
        self.cards = []
        self.is_active = False
        self.is_all_in = False
        self.is_dealer = False
        self.is_small_blind = False
        self.is_big_blind = False


class Action(Enum):
    """Define the possible actions for a player."""

    FOLD = 0
    CALL = 1
    RAISE = 2


class Phase(Enum):
    """Define the game phases."""

    PREFLOP = 0
    FLOP = 1
    TURN = 2
    RIVER = 3
    SHOWDOWN = 4


class StateMachine(Enum):
    """Manage the state machine between game phases."""

    DRAW_CARD = 0
    DRAW_TWO_CARDS = 1
    DRAW_THREE_CARDS = 2
    ASK_ACTION = 3
    START_GAME = 4
    END_GAME = 5

    def get_next(self):
        """Get the next phase of the game."""
        if self == StateMachine.START_GAME:
            return StateMachine.DRAW_TWO_CARDS
        elif self == StateMachine.DRAW_CARD:
            return StateMachine.DRAW_TWO_CARDS
        elif self == StateMachine.DRAW_TWO_CARDS:
            return StateMachine.DRAW_THREE_CARDS
        elif self == StateMachine.DRAW_THREE_CARDS:
            return StateMachine.ASK_ACTION
        elif self == StateMachine.ASK_ACTION:
            return StateMachine.DRAW_CARD
        else:  # self == StateMachine.END_GAME:
            return StateMachine.START_GAME


class TexasHoldemEnv(Env):
    """Describe the environment Texas Holdem."""

    def __init__(
        self,
        number_of_players: int = 5,
        initial_stack: float = 1000,
        small_blind: float = 10,
        max_steps: int = 1000,
    ):
        """Init the setup of the class."""
        self.initial_stack = initial_stack
        self.players = [
            Player(player_id, initial_stack) for player_id in range(number_of_players)
        ]
        self.small_blind = small_blind
        self.big_blind = small_blind * 2.0

        self.action_space = spaces.Discrete(3)
        self.observation_space = spaces.Discrete(3)

        self.active_players = self._get_active_players()
        self.__table = {Phase.FLOP: None, Phase.TURN: None, Phase.RIVER: None}
        self.game_state = StateMachine.START_GAME
        self.stake = None

        self.max_steps = max_steps

        self.deck = Deck()

        # Set the dealer
        self.dealer_id = random.choice(self.active_players)
        self.players[self.dealer_id].is_dealer = True
        self.players_active = self._get_active_players()

        self._set_small_blind()

        self.reset()

    def _get_active_players(self) -> list:
        """Get a list of all active players."""
        return [idx for idx, player in enumerate(self.players) if player.is_active]

    def __get_next_active_player_id(self, current_player) -> int:
        """Get the id of the next active player starting from current player."""
        next_player = (current_player + 1) % len(self.active_players)
        max_loop = len(self.players)
        idx_loop = 0
        while not self.players[next_player].is_dealer and idx_loop < max_loop:
            idx_loop += 1
            next_player += 1

        return next_player

    def _set_dealer(self) -> None:
        """Set dealer."""
        next_dealer = self.__get_next_active_player_id(self.dealer_id + 1)

        self.players[next_dealer].is_dealer = True
        self.dealer_id = next_dealer

    def _set_small_blind(self) -> None:
        """Set small blind."""
        next_small_blind = self.__get_next_active_player_id(self.dealer_id + 1)
        self.players[next_small_blind].is_small_blind = True

    def _set_big_blind(self) -> None:
        """Set big blind."""
        next_big_blind = self.__get_next_active_player_id(self.dealer_id + 1)
        self.players[next_big_blind].is_big_blind = True

    def _check_action(self, action) -> None:
        """Check if the action is valid."""

        if action not in self.action_space:
            raise ValueError("Action not available")
       
    def step(self, action):
        """Execute action and return next state of the game."""
        if self.game_state == Phase.PREFLOP:
            self.__table[Phase.FLOP] = self.deck.draw_random(3)
            self.game_state = Phase.FLOP
        elif self.game_state == Phase.FLOP:
            self.__table[Phase.TURN] = self.deck.draw_random()
            self.game_state = Phase.TURN
        elif self.game_state == Phase.TURN:
            self.__table[Phase.RIVER] = self.deck.draw_random()
            self.game_state = Phase.SHOWDOWN
        # self.game_state == Phase.SHOWDOWN:
        # DO NOTHING

        return self.__table, 0, False, {}

    # TODO: fix the output of this function
    def reset(self):
        """Reset game."""
        self.__table = {Phase.FLOP: None, Phase.TURN: None, Phase.RIVER: None}
        self.game_state = Phase.PREFLOP

        self.players_active = [
            idx for idx, player in enumerate(self.players) if player.is_active
        ]

        # Player reset
        for player_id, player in enumerate(self.players):
            self.players[player_id].cards = []

        # New dealer
        self.dealer_id = (self.dealer_id + 1) % len(self.players)

        self._deal_new_cards()

        self.deck.reset()

        # Set the stake
        self.stake = 0

        if self.players[self.dealer_id + 1].stack < self.small_blind:
            self.stake += self.players[self.dealer_id + 1].stack

            self.players[self.dealer_id + 1].is_all_in = True
            self.players[self.dealer_id + 1].stack = 0
        else:
            self.stake += self.small_blind

        if self.players[self.dealer_id + 2].stack < self.big_blind:
            self.stake += self.players[self.dealer_id + 2].stack

            self.players[self.dealer_id + 2].is_all_in = True
            self.players[self.dealer_id + 2].stack = 0
        else:
            self.stake += self.big_blind

        # Set the active players
        for player in self.players:
            player.is_active = True

        return self.__table

    def _deal_new_cards(self):
        """Deal new cards and set blinds."""
        self._set_small_blind()
        self._set_big_blind()

        for player in self.players:
            player.cards = self.deck.draw_random(2)

    def __str__(self) -> str:
        """Print current state of the game as text."""
        if self.__table[Phase.FLOP]:
            print(
                f'{self.__table[Phase.FLOP][0]} '
                f'{self.__table[Phase.FLOP][1]} '
                f'{self.__table[Phase.FLOP][2]}',
                end='',
            )
        else:
            print('_ _ _', end='')

        if self.__table[Phase.TURN]:
            print(f' {covert_to_human_readable(self.__table[Phase.TURN])}', end='')
        else:
            print(' _', end='')

        if self.__table[Phase.RIVER]:
            print(f' {covert_to_human_readable(self.__table[Phase.RIVER])}')
        else:
            print(' _')

        return ''

        # TODO: used for testing

    def random_state(self):
        """Generate random state of the game."""
        self.__table[Phase.FLOP] = self.deck.draw_random(3)
        self.__table[Phase.TURN] = self.deck.draw_random()
        self.__table[Phase.RIVER] = self.deck.draw_random()

    def render(self, mode='human', close=False):
        """Render the graphics of the game."""
        pass
