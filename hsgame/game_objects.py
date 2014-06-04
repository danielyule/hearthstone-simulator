import random
import hsgame.powers
import hsgame.targeting
import hsgame.constants
import abc


__author__ = 'Daniel'

card_table = {}


def card_lookup(card_name):
    """
    Given a the name of a card as a string, return an object corresponding to that card

    :param str card_name: A string representing the name of the card in English
    :return: An instance of a subclass of Card corresponding to the given card name or None if no Card
             by that name exists.
    """
    def card_lookup_rec(card_type):
        subclasses = card_type.__subclasses__()
        if len(subclasses) is 0:
                c = card_type()
                card_table[c.name] = card_type
        for sub_type in subclasses:
            card_lookup_rec(sub_type)

    if len(card_table) == 0:
        for card_type in Card.__subclasses__():
            card_lookup_rec(card_type)

    card = card_table[card_name]
    if card is not None:
        return card()
    return None


class GameException(Exception):
    """
    An :class:`Exception` relating to the operation of the game
    """
    def __init__(self, message):
        super().__init__(message)


class Bindable:
    """
    A class which inherits from Bindable has an event structure added to it.

    This event structure follows the observer pattern.  It consists of two parts: binding and triggering.
    A function handler is bound to an event using the :meth:`bind` or :meth:`bind_once` methods.  When the event is
    triggered using the :meth:`trigger` method, then any function handlers which have been bound to that event are
    called.

    Arguments can be passed to a bound function when binding or when triggering, or both.  Arguments from triggering
    are passed first, followed by arguments from binding.

    Functions can be bound such that they are called each time an event is triggered, or so that they are only called
    the next time a function is triggered.  The former case is handled by :meth:`bind` and the latter by
    :meth:`bind_once`

    **Examples**:

    Simple Binding::

       class EventTarget(Bindable):
           def __init__(self):
               super().__init__()

       def handler(fangs, scales):
           print("fangs: {:d}, scales: {:d}".format(fangs, scales))

       target = EventTarget()
       target.bind("attack", handler, 1001)
       target.trigger("attack", 2)             # outputs "fangs: 2, scales: 1001"
       target.trigger("attack", 6)             # outputs "fangs: 6, scales: 1001"

    Binding Once::

       class EventTarget(Bindable):
           def __init__(self):
               super().__init__()

       def handler(joke):
            print("{:s}! HAHAHA".format(joke))

       target = EventTarget()
       target.bind_once("joke_told", handler)

       # outputs "Well, I'd better replace it then! HAHAHA"
       target.trigger("joke_told", "Well, I'd better replace it then")

       # outputs nothing
       target.trigger("joke_told", "What a senseless waste of human life")

    Any class which subclasses this class must be sure to call :meth:`__init__`
    """
    def __init__(self):
        """
        Set up a new :class:`Bindable`.  Must be called by any subclasses.
        """
        self.events = {}

    def bind(self, event, function, *args):
        """
        Bind a function to an event.  Each time the event is triggered, the function will be called.

        Any parameters passed to this method will be appended to the paramters passed to the trigger function
        and passed to the bound function.

        :param event str: The event to bind a function to
        :param function function: The function to bind.  The parameters are not checked until it is called, so
                                  ensure its signature matches the parameters called from :meth:`trigger`
        :param args: Any other parameters to be called
        :see: :class:`Bindable`
        """
        class Handler:
            def __init__(self):
                self.args = args
                self.function = function
                self.remove = False
                self.active = False

        if not event in self.events:
            self.events[event] = []

        self.events[event].append(Handler())

    def bind_once(self, event, function, *args):
        """
        Bind a function to an event.  This function will only be called the next time the event is triggered, and
        then ignored.

        Any parameters passed to this method will be appended to the paramters passed to the trigger function
        and passed to the bound function.

        :param event str: The event to bind a function to
        :param function function: The function to bind.  The parameters are not checked until it is called, so
                                  ensure its signature matches the parameters called from :meth:`trigger`
        :param args: Any other parameters to be called
        :see: :class:`Bindable`
        """
        class Handler:
            def __init__(self):
                self.args = args
                self.function = function
                self.remove = True
                self.active = False

        if not event in self.events:
            self.events[event] = []

        self.events[event].append(Handler())

    def trigger(self, event, *args):
        """
        Trigger an event.  Any functions which have been bound to that event will be called.

        The parameters passed to this function as `args` will be passed along to the bound functions.

        :param string event: The name of the event to trigger
        :param args: The remaining arguments to pass to the bound function
        :see: :class:`Bindable`
        """
        if event in self.events:
            for handler in self.events[event].copy():
                if not handler.active:
                    pass_args = args + handler.args
                    handler.active = True
                    handler.function(*pass_args)
                    handler.active = False
                    if handler.remove:
                        self.events[event].remove(handler)
                        #tidy up the events dict so we don't have entries for events with no handlers
                        if len(self.events[event]) is 0:
                            del (self.events[event])

    def unbind(self, event, function):
        """
        Unbind a function from an event.  When this event is triggered, the function is no longer called.

        `function` must be the same function reference as was passed in to :meth:`bind` or :meth:`bind_once`

        :param string event: The event to unbind the function from
        :param function function: The function to unbind.
        """
        if event in self.events:
            self.events[event] = [handler for handler in self.events[event] if not handler.function == function]
            if len(self.events[event]) is 0:
                del (self.events[event])


class Character(Bindable, metaclass=abc.ABCMeta):
    def __init__(self, attack_power, health, player):
        super().__init__()
        self.health = health
        self.max_health = health
        self.attack_power = attack_power
        self.active = False
        self.dead = False
        self.wind_fury = False
        self.used_wind_fury = False
        self.frozen = False
        self.frozen_this_turn = False
        self.temp_attack = 0
        self.player = player
        self.immune = False
        self.delayed = []
        self.stealth = False

    def turn_complete(self):
        if self.temp_attack > 0:
            self.trigger("attack_decreased", self.temp_attack)
            self.temp_attack = 0

    def attack(self):
        if not self.can_attack():
            raise GameException("That minion cannot attack")

        found_taunt = False
        targets = []
        for enemy in self.player.game.other_player.minions:
            if enemy.taunt and enemy.can_be_attacked():
                found_taunt = True
            if enemy.can_be_attacked():
                targets.append(enemy)

        if found_taunt:
            targets = [target for target in targets if target.taunt]
        else:
            targets.append(self.player.game.other_player.hero)

        self.player.trigger("attacking", self)
        target = self.choose_target(targets)

        if isinstance(target, Minion):
            self.trigger("attack_minion", target)
            target.trigger("attacked", self)
            if self.dead:
                return
            my_attack = self.attack_power + self.temp_attack  # In case the damage causes my attack to grow
            self.physical_damage(target.attack_power, target)
            target.physical_damage(my_attack, self)
            target.activate_delayed()
        else:
            self.trigger("attack_player", target)
            target.trigger("attacked", self)
            if self.dead:
                return
            target.physical_damage(self.attack_power + self.temp_attack, self)
            target.activate_delayed()
            #TODO check if the player's weapon is out in the case of Misdirection

        self.activate_delayed()
        if self.wind_fury and not self.used_wind_fury:
            self.used_wind_fury = True
        else:
            self.active = False
        self.stealth = False

    @abc.abstractmethod
    def choose_target(self, targets):
        pass

    def delayed_trigger(self, event, *args):
        self.delayed.append({'event': event, 'args': args})
        self.player.game.delayed_minions.append(self)

    def activate_delayed(self):
        for delayed in self.delayed:
            self.trigger(delayed['event'], *delayed['args'])

        self.delayed = []

    def damage(self, amount, attacker):
        if not self.immune:
            self.delayed_trigger("damaged", amount, attacker)
            #The response of a secret to damage must happen immediately
            self.trigger("secret_damaged", amount, attacker)
            self.health -= amount
            if type(attacker) is Minion:
                attacker.delayed_trigger("did_damage", amount, self)
            elif type(attacker) is Player:
                attacker.trigger("did_damage", amount, self)
            if self.health <= 0:
                self.die(attacker)

    def increase_attack(self, amount):
        def silence():
            self.attack_power -= amount
        self.trigger("attack_increased", amount)
        self.attack_power += amount
        self.bind_once('silenced', silence)

    def increase_temp_attack(self, amount):

        self.trigger("attack_increased", amount)
        self.temp_attack += amount

    def increase_health(self, amount):
        def silence():
            self.max_health -= amount
            if self.max_health < self.health:
                self.health = self.max_health
        self.trigger("health_increased", amount)
        self.max_health += amount
        self.health += amount
        self.bind_once('silenced', silence)

    def decrease_health(self, amount):
        def silence():
            # I think silence only restores its max health again. It does not heal as well.
            self.max_health += amount
        self.trigger("health_decreased", amount)
        self.max_health -= amount
        if self.health > self.max_health:
            self.health = self.max_health
        self.bind_once('silenced', silence)

    def freeze(self):
        self.frozen_this_turn = True
        self.frozen = True

    def silence(self):
        self.trigger("silenced")
        self.wind_fury = False
        self.frozen = False
        self.frozen_this_turn = False

    def spell_damage(self, amount, spell_card):
        self.trigger("spell_damaged", amount, spell_card)
        self.damage(amount, spell_card)

    def physical_damage(self, amount, attacker):
        self.trigger("physically_damaged", amount, attacker)
        if type(attacker) is Player:
            self.player_damage(amount, attacker)
        else:
            self.minion_damage(amount, attacker)

    def minion_damage(self, amount, minion):
        self.trigger("minion_damaged", amount, minion)
        self.damage(amount, minion)

    def player_damage(self, amount, player):
        self.trigger("player_damaged", amount, player)
        self.damage(amount, player)

    def heal(self, amount):
        self.trigger("healed", amount)
        self.health += amount
        if self.health > self.max_health:
            self.health = self.max_health

    def die(self, by):
        self.delayed_trigger("died", by)
        self.dead = True

    def can_attack(self):
        return self.attack_power + self.temp_attack > 0 and self.active and not self.frozen

    def spell_targetable(self):
        return True


def _is_spell_targetable(target):
    return target.spell_targetable()


class Card(Bindable):
    """
    Represents a card in Heathstone.  Every card is implemented as a subclass, either directly or through
    :class:`MinionCard`, :class:`SecretCard` or :class:`WeaponCard`.  If it is a direct subclass of this
    class then it is a standard spell, whereas if it is a subclass of one of :class:`MinionCard`, :class:`SecretCard`
    or :class:`WeaponCard`., then it is a minion, secret or weapon respectively.

    In order to play a card, it should be passed to :meth:`Game.play_card`.  Simply calling :meth:`use` will
    cause its effect, but not update the game state.
    """
    def __init__(self, name, mana, character_class, rarity, target_func=None,
                 filter_func=_is_spell_targetable):
        """
            Creates a new :class:`Card`.

            :param string name: The name of the card in English
            :param int mana: The base amount of mana this card costs
            :param int character_class: A constant from :class:`hsgame.constants.CHARACTER_CLASS` denoting
                                        which character this card belongs to or
                                        :const:`hsgame.constants.CHARACTER_CLASS.ALL` if neutral
            :param int rarity: A constant from :class:`hsgame.constants.CARD_RARITY` denoting the rarity of the card.
            :param function target_func: A function which takes a game, and returns a list of targets.  If None, then
                                         the card is assumed not to require a target.  If `target_func` returns
                                         an empty list, then the card cannot be played.  If it returns None, then the
                                         card is played, but with no target (i.e. a battlecry which has no valid target
                                         will not stop the minion from being played).

                                         See :mod:`hsgame.targeting` for more details.
            :param function filter_func: A boolean function which can be used to filter the list of targets. An example
                                         for :class:`hsgame.cards.spells.priest.ShadowMadness` might be a function which
                                         returns true if the target's attack is less than 3.
        """
        super().__init__()
        self.name = name
        self.mana = mana
        self.character_class = character_class
        self.rarity = rarity
        self.cancel = False
        self.targetable = target_func is not None
        if self.targetable:
            self.targets = []
            self.target = None
            self.get_targets = target_func
            self.filter_func = filter_func

    def can_use(self, player, game):
        """
        Verifies if the card can be used with the game state as it is.

        Checks that the player has enough mana to play the card, and that the card has a valid
        target if it requires one.

        :return bool: True if the card can be played, false otherwise.
        """
        if self.targetable:
            self.targets = self.get_targets(game, self.filter_func)
            if self.targets is not None and len(self.targets) is 0:
                return False

        return player.mana >= self.mana_cost(player)

    def mana_cost(self, player):
        """
        Calculates the mana cost for this card.

        This cost is the base cost for the card, modified by any effects from the card itself, or
        from other cards (such as :class:`hsgame.cards.minions.neutral.VentureCoMercenary`)

        :param Player player: The player who is trying to use the card.

        :return int: representing the actual mana cost of this card.
        """
        calc_mana = self.mana
        for mana_filter in player.mana_filters:
            if mana_filter.filter(self):
                calc_mana -= mana_filter.amount
                if calc_mana < mana_filter.min:
                    return mana_filter.min
        return calc_mana

    def use(self, player, game):
        """
        Use the card.

        This method will cause the card's effect, but will not update the game state or trigger any events.
        To play a card correctly, use :meth:`Game.play_card`.

        Implementations of new cards should override this method, but be sure to call `super().use(player, game)`

        :param Player player: The player who is using the card.
        :param Game game: The game this card is being used in.
        """
        if self.targetable:
            if self.targets is None:
                self.target = None
            else:
                self.target = player.agent.choose_target(self.targets)

    def is_spell(self):
        """
        Verifies if this is a spell card (or a secret card)

        :return bool: True if the card is a spell card, false otherwise
        """
        return True

    def __str__(self):  # pragma: no cover
        """
        Outputs a decription of the card for debugging purposes.
        """
        return self.name + " (" + str(self.mana) + " mana)"


class MinionCard(Card, metaclass=abc.ABCMeta):
    def __init__(self, name, mana, character_class, rarity, targeting_func=None,
                 filter_func=lambda target: not target.stealth):
        super().__init__(name, mana, character_class, rarity, targeting_func, filter_func)

    def can_use(self, player, game):
        return super().can_use(player, game)

    def use(self, player, game):
        super().use(player, game)
        self.create_minion(player).add_to_board(self, game, player, player.agent.choose_index(self))

    @abc.abstractmethod
    def create_minion(self, player):
        pass

    def is_spell(self):
        return False


class SecretCard(Card, metaclass=abc.ABCMeta):
    def __init__(self, name, mana, character_class, rarity):
        super().__init__(name, mana, character_class, rarity, None)
        self.player = None

    def can_use(self, player, game):
        return super().can_use(player, game) and self.name not in [secret.name for secret in player.secrets]

    def use(self, player, game):
        super().use(player, game)
        player.secrets.append(self)
        self.player = player

    def reveal(self):
        self.player.trigger("secret_revealed", self)
        self.player.secrets.remove(self)

    @abc.abstractmethod
    def activate(self, player):
        pass

    @abc.abstractmethod
    def deactivate(self, player):
        pass


class Minion(Character):
    def __init__(self, attack, health, minion_type=hsgame.constants.MINION_TYPE.NONE, battlecry=None, deathrattle=None):
        super().__init__(attack, health, None)
        self.minion_type = minion_type
        self.taunt = False
        self.game = None
        self.card = None
        self.index = -1
        self.charge = False
        self.spell_power = 0
        self.divine_shield = False
        self.battlecry = battlecry
        self.deathrattle = deathrattle

    def add_to_board(self, card, game, player, index):
        self.card = card
        player.minions.insert(index, self)
        self.game = game
        self.player = player
        player.spell_power += self.spell_power
        if self.battlecry is not None:
            self.battlecry(self)
        for minion in player.minions:
            if minion.index >= index:
                minion.index += 1
        self.index = index
        if self.charge:
            self.active = True
        self.game.trigger("minion_added", self)
        self.trigger("added_to_board", self, index)
        player.bind("turn_ended", self.turn_complete)
        
    def remove_from_board(self):
        self.player.spell_power -= self.spell_power
        for minion in self.player.minions:
            if minion.index > self.index:
                minion.index -= 1
        self.game.remove_minion(self, self.player)
        self.player.unbind("turn_ended", self.turn_complete)

    def attack(self):
        super().attack()

    def silence(self):
        super().silence()
        self.taunt = False
        self.stealth = False
        self.charge = False
        self.player.spell_power -= self.spell_power
        self.spell_power = 0
        self.divine_shield = False
        self.battlecry = None
        self.deathrattle = None

    def damage(self, amount, attacker):
        if self.divine_shield:
            self.divine_shield = False
        else:
            super().damage(amount, attacker)

    def die(self, by):
        # Since deathrattle gets removed by silence, save it
        deathrattle = self.deathrattle
        self.bind_once("died", lambda c: self.silence())
        super().die(by)
        self.game.trigger("minion_died", self, by)
        if deathrattle is not None:
            deathrattle()
        self.remove_from_board()

    def can_be_attacked(self):
        return not self.stealth

    def spell_targetable(self):
        return not self.stealth

    def choose_target(self, targets):
        return self.player.choose_target(targets)

    def __str__(self):  # pragma: no cover
        return "({0}) ({1}) {2} at index {3}".format(self.attack_power, self.health, self.card.name, self.index)

    def add_adjacency_effect(self, effect, effect_silence):
        """
        Adds an effect to this minion that will affect the minions on either side.

        This method sets up the effect so that it will update when new minions are added
        or other minions die, or the original minion is silenced

        :param function effect: the effect to apply to adjacent minions.  Takes one paramter: the minion to affect.
        :param function effect_silence: a function which will undo the effect when this minion is silenced. Takes
                                        one parameter: the minion to affect.
        """
        def left_minion_died(killer, minion):
            if minion.index > 0:
                apply_left_effect(self.player.minions[minion.index - 1])

        def apply_left_effect(minion):
            effect(minion)
            minion.bind("died", left_minion_died, minion)

        def right_minion_died(killer, minion):
            if minion.index < len(self.player.minions):
                apply_left_effect(self.player.minions[minion.index])

        def apply_right_effect(minion):
            effect(minion)
            minion.bind("died", right_minion_died, minion)

        def minion_added(minion):
            if minion.index is self.index - 1:
                if minion.index > 0:
                    old_left = self.player.minions[minion.index - 1]
                    effect_silence(old_left)
                    old_left.unbind("died", left_minion_died)
                apply_left_effect(minion)
            elif minion.index is self.index + 1:
                if minion.index < len(self.player.minions) - 1:
                    old_right = self.player.minions[minion.index + 1]
                    effect_silence(old_right)
                    old_right.unbind("died", right_minion_died)
                apply_right_effect(minion)

        def silenced():
            if self.index > 0:
                left = self.player.minions[self.index - 1]
                effect_silence(left)
                left.unbind("died", left_minion_died)
            if self.index < len(self.player.minions) - 1:
                right = self.player.minions[self.index + 1]
                effect_silence(right)
                right.unbind("died", right_minion_died)


        if self.index > 0:
            apply_left_effect(self.player.minions[self.index - 1])
        if self.index < len(self.player.minions) - 1:
            apply_right_effect(self.player.minions[self.index + 1])
        self.player.game.bind("minion_added", minion_added)
        self.bind("silenced", silenced)


class Deck:
    def __init__(self, cards, character_class):
        self.cards = cards
        self.character_class = character_class
        self.used = [False] * 30
        self.left = 30

    def can_draw(self):
        return self.left > 0

    def draw(self, random_func):
        if not self.can_draw():
            raise GameException("Cannot draw more than 30 cards")

        index = random_func(0, self.left - 1)
        count = 0
        i = 0
        while count <= index:
            if not self.used[i]:
                count += 1
            i += 1

        self.used[i - 1] = True
        self.left -= 1
        return self.cards[i - 1]

    def put_back(self, card):
        for index in range(0, 30):
            if self.cards[index] == card:
                if self.used[index] is False:
                    raise GameException("Tried to put back a card that hadn't been used yet")
                self.used[index] = False
                self.left += 1
                return
        raise GameException("Tried to put back a card that didn't come from this deck")


class Hero(Character):
    def __init__(self, character_class, player):
        super().__init__(0, 30, player)

        self.armour = 0
        self.weapon = None
        self.character_class = character_class
        self.player = player
        self.power = hsgame.powers.powers(self.character_class)(self)
        self.player.bind("turn_ended", self.turn_complete)

    def attack(self):
        self.trigger("attacking", self)
        super().attack()

    def damage(self, amount, attacker):
        self.armour -= amount
        if self.armour < 0:
            new_amount = -self.armour
            self.armour = 0
            super().damage(new_amount, attacker)

    def increase_armour(self, amount):
        self.trigger("armour_increased", amount)
        self.armour += amount

    def die(self, by):
        super().die(by)

    def find_power_target(self):
        targets = hsgame.targeting.find_spell_target(self.player.game, lambda t: t.spell_targetable())
        target = self.choose_target(targets)
        self.trigger("found_power_target", target)
        return target

    def choose_target(self, targets):
        return self.player.choose_target(targets)


class Player(Bindable):
    def __init__(self, name, deck, agent, game, random_func=random.randint):
        super().__init__()
        self.hero = Hero(deck.character_class, self)
        self.name = name
        self.mana = 0
        self.max_mana = 0
        self.deck = deck
        self.spell_power = 0
        self.minions = []
        self.random = random_func
        self.hand = []
        self.fatigue = 0
        self.agent = agent
        self.game = game
        self.secrets = []
        self.mana_filters = []

    def __str__(self):  # pragma: no cover
        return "Player: " + self.name

    def draw(self):
        if self.can_draw():
            card = self.deck.draw(self.random)
            self.trigger("card_drawn", card)
            if len(self.hand) < 10:
                self.hand.append(card)
            else:
                self.trigger("card_destroyed", card)
        else:
            self.fatigue += 1
            self.trigger("fatigue_damage", self.fatigue)
            self.hero.damage(self.fatigue, None)
            self.hero.activate_delayed()

    def can_draw(self):
        return self.deck.can_draw()

    def put_back(self, card):
        self.hand.remove(card)
        self.deck.put_back(card)
        self.trigger("card_put_back", card)

    def choose_target(self, targets):
        return self.agent.choose_target(targets)


class Game(Bindable):
    def __init__(self, decks, agents, random_func=random.randint):
        super().__init__()
        self.delayed_minions = []
        self.random = random_func
        first_player = random_func(0, 1)
        if first_player is 0:
            play_order = [0, 1]
        else:
            play_order = [1, 0]
        self.players = [Player("one", decks[play_order[0]], agents[play_order[0]], self, random_func),
                        Player("two", decks[play_order[1]], agents[play_order[1]], self, random_func)]
        agents[0].set_game(self)
        agents[1].set_game(self)
        self.current_player = self.players[0]
        self.other_player = self.players[1]
        self.game_ended = False
        for i in range(0, 3):
            self.players[0].draw()

        for i in range(0, 4):
            self.players[1].draw()

        self.players[0].hero.bind("died", self.game_over)
        self.players[1].hero.bind("died", self.game_over)

    def pre_game(self):
        card_keep_index = self.players[0].agent.do_card_check(self.players[0].hand)
        self.trigger("kept_cards", self.players[0].hand, card_keep_index)
        put_back_cards = []
        for card_index in range(0, 3):
            if not card_keep_index[card_index]:
                self.players[0].draw()
                put_back_cards.append(self.players[0].hand[card_index])

        for card in put_back_cards:
            self.players[0].put_back(card)

        card_keep_index = self.players[1].agent.do_card_check(self.players[1].hand)
        self.trigger("kept_cards", self.players[1].hand, card_keep_index)
        put_back_cards = []
        for card_index in range(0, 4):
            if not card_keep_index[card_index]:
                self.players[1].draw()
                put_back_cards.append(self.players[1].hand[card_index])

        for card in put_back_cards:
            self.players[1].put_back(card)

    def start(self):
        self.pre_game()
        self.current_player = self.players[1]
        while not self.game_ended:
            self.play_single_turn()

    def play_single_turn(self):
        self._start_turn()
        self.current_player.agent.do_turn(self.current_player)
        self._end_turn()

    def _start_turn(self):
        if self.current_player == self.players[0]:
            self.current_player = self.players[1]
            self.other_player = self.players[0]
        else:
            self.current_player = self.players[0]
            self.other_player = self.players[1]
        if self.current_player.max_mana < 10:
            self.current_player.max_mana += 1

        for secret in self.other_player.secrets:
            secret.activate(self.other_player)
        self.current_player.mana = self.current_player.max_mana
        self.current_player.trigger("turn_started")
        self.current_player.draw()

    def game_over(self, attacker):
        self.game_ended = True

    def _end_turn(self):
        self.current_player.trigger("turn_ended")
        if self.current_player.hero.frozen_this_turn:
            self.current_player.hero.frozen_this_turn = False
        else:
            self.current_player.hero.frozen = False

        self.other_player.hero.frozen_this_turn = False
        for minion in self.other_player.minions:
            minion.frozen_this_turn = False

        self.current_player.hero.active = True
        for minion in self.current_player.minions:
            minion.active = True
            minion.used_wind_fury = False
            if minion.frozen_this_turn:
                minion.frozen_this_turn = False
            else:
                minion.frozen = False

        for secret in self.other_player.secrets:
            secret.deactivate(self.other_player)

    def play_card(self, card):
        if self.game_ended:
            raise GameException("The game has ended")
        if not card.can_use(self.current_player, self):
            raise GameException("That card cannot be used")
        self.current_player.trigger("card_played", card)
        self.current_player.hand.remove(card)
        if card.can_use(self.current_player, self):
            self.current_player.mana -= card.mana_cost(self.current_player)
        else:
            raise GameException("Tried to play card that could not be played")

        if card.is_spell():
            self.current_player.trigger("spell_cast", card)

        if not card.cancel:
            card.use(self.current_player, self)
            self.current_player.trigger("card_used", card)
            for minion in self.delayed_minions:
                minion.activate_delayed()

            self.delayed_minions = []

    def remove_minion(self, minion, player):
        player.minions.remove(minion)
        self.trigger("minion_removed", minion, player)