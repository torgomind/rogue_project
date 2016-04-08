#-------------------------#
#   Notes:                #
#-------------------------#

# note: render_all after mouse input/kb
# note: animations for fireball/blizzard/lightningbolt
# note: kb controls for aimed weapons
# note: monster smell range goes way up after sighting
# note: 'send_to_back()' in objects[] = drawn first (appears below all else)
#
# NOTE !!! ~ this will be a good learning experience with the debugger. you're up to pt.13, ~ bonus round!
#   'character progression'. game crashes on new game (sometimes) something about fighter.xp

#-------------------------#
#   Globals/Imports:      #
#-------------------------#

import libtcodpy as libtcod
import math
import textwrap
import time
import shelve

#actual size of the window
SCREEN_WIDTH = 80
SCREEN_HEIGHT = 50

#size of the map
MAP_WIDTH = 80
MAP_HEIGHT = 43

#Dungeon gen parameters
ROOM_MAX_SIZE = 10
ROOM_MIN_SIZE = 6
MAX_ROOMS = 30
HEAL_AMOUNT = 4
LIGHTNING_DAMAGE = 20
LIGHTNING_RANGE = 5
CONFUSE_NUM_TURNS = 10
CONFUSE_RANGE = 8
BLIZZARD_RANGE = 8
BLIZZARD_DAMAGE = 6
FIREBALL_RADIUS = 3
FIREBALL_DAMAGE = 12
MONSTER_SMELL_RANGE = 30

#Player attributes
LEVEL_UP_BASE = 200 #200
LEVEL_UP_FACTOR = 150 #150

#FOV
FOV_ALGO = 0 #default fov algorithm
FOV_LIGHT_WALLS = True
TORCH_RADIUS = 10

LIMIT_FPS = 20  #20 frames-per-second maximum

color_dark_wall = libtcod.Color(103, 110, 103)
color_light_wall = libtcod.Color(145, 155, 140)
color_dark_ground = libtcod.Color(33, 26, 38)
color_light_ground = libtcod.Color(85, 69, 100)

#GUI, sizes relevant for current console size
BAR_WIDTH = 20
PANEL_HEIGHT = 7
PANEL_Y = SCREEN_HEIGHT - PANEL_HEIGHT
MSG_X = BAR_WIDTH + 2
MSG_WIDTH = SCREEN_WIDTH - BAR_WIDTH - 2
MSG_HEIGHT = PANEL_HEIGHT - 1
INVENTORY_WIDTH = 50
LEVEL_SCREEN_WIDTH = 40
CHARACTER_SCREEN_WIDTH = 30



class Tile:
    #a tile of the map and its properties
    def __init__(self, blocked, block_sight = None):
        self.blocked = blocked
        self.explored = False

        #by default, if a tile is blocked, it also blocks sight
        if block_sight is None: block_sight = blocked
        self.block_sight = block_sight

class Rect:
    #a rectangle on the map. used to characterize a room.
    def __init__(self, x, y, w, h):
        self.x1 = x
        self.y1 = y
        self.x2 = x + w
        self.y2 = y + h
    def center(self):
        center_x = (self.x1 + self.x2)/2
        center_y = (self.y1 + self.y2)/2
        return(center_x, center_y)
    def intersect(self, other):
        #returns true if this rectangle intersects with another one
        #not allowed to touch, not allowed to overlap
        return (self.x1 <= other.x2 and self.x2 >= other.x1 and
                self.y1 <= other.y2 and self.y2 >= other.y1)

class Object:
    #this is a generic object: the player, a monster, an item, the stairs...
    #it's always represented by a character on screen.
    def __init__(self, x, y, char, name, color, blocks=False, always_visible=False, fighter=None, ai=None, item=None, equipment=None):
        self.x = x
        self.y = y
        self.char = char
        self.color = color
        self.name = name
        self.blocks = blocks
        self.always_visible = always_visible

        self.fighter = fighter
        if self.fighter: #let the fighter know who owns it
            self.fighter.owner = self

        self.ai = ai
        if self.ai: #let the AI component know who owns it
            self.ai.owner = self

        self.item = item
        if self.item: #let item know owner
            self.item.owner = self

        self.equipment = equipment
        if self.equipment: #let it know owner
            self.equipment.owner = self
            self.item = Item()
            self.item.owner = self


    def move(self, dx, dy):
        #move by the given amount, if the destination is not blocked
        if not is_blocked(self.x + dx, self.y + dy):
            self.x += dx
            self.y += dy

    def move_towards(self, target_x, target_y):
        # enemies only
        # vector from this object to the target, and distance
        dx = target_x - self.x
        dy = target_y - self.y
        distance = math.sqrt(dx**2 + dy**2)
        # normalise it to length one (get unit vector) then round it and convert
        # to integer to restrict movement to grid
        dx = int(round(dx/distance))
        dy = int(round(dy/distance))
        #wall slide (there's prob a better way to code this..)
        if not is_blocked(self.x + dx, self.y + dy):
            self.move(dx, dy) #original code stopped here
            return

        dx = target_x - self.x
        dy = target_y - self.y

        #get direction of x or y; avoid div/0 (ie: 1 or -1 or 0)
        if dx:
            dir_x = int(dx/math.sqrt(dx**2))
        else:
            dir_x = 0
        if dy:
            dir_y = int(dy/math.sqrt(dy**2))
        else:
            dir_y = 0

        #follow player along wall, avoid div/zero
        if math.sqrt(dx**2) > math.sqrt(dy**2): # if dist-x bigger than dist-y,
            if is_blocked(self.x+dir_x,self.y): # if horiz is blocked
                self.move(0,dir_y) #move vertical
            else:
                self.move(dir_x,0) #move horizontal
        else: # if dist-y > dist-x
            if is_blocked(self.x,self.y+dir_y): # if vert is blocked
                self.move(dir_x,0) #move horiz
            else:
                self.move(0,dir_y) #move vert

    def distance_to(self, other):
        #return the distance to another object
        dx = other.x - self.x
        dy = other.y - self.y
        return math.sqrt(dx**2 + dy**2)

    def distance(self, x, y):
        #return distance between object and input co-ords
        return math.sqrt((self.x - x)**2 + (self.y - y)**2)

    def draw(self):
            if ( libtcod.map_is_in_fov(fov_map, self.x, self.y) or
                (self.always_visible and map[self.x][self.y].explored) ):
                #set the color and then draw the character that represents this object at its position
                libtcod.console_set_default_foreground(con, self.color)
                libtcod.console_put_char(con, self.x, self.y, self.char, libtcod.BKGND_NONE)

    def clear(self):
        #erase the character that represents this object
        libtcod.console_put_char(con, self.x, self.y, ' ', libtcod.BKGND_NONE)

    def send_to_back(self):
        #make this object drawn first, so all others appear above it (if on same tile)
        #only for objects list, not inventory
        global objects
        objects.remove(self)
        objects.insert(0, self)

class Equipment:
    #an object that can be equipped, yielding bonuses. automatically add the Item component
    def __init__(self, slot, power_bonus=0, defense_bonus=0, max_hp_bonus=0):
        self.power_bonus = power_bonus
        self.defense_bonus = defense_bonus
        self.max_hp_bonus = max_hp_bonus

        self.slot = slot
        self.is_equipped = False

    def toggle_equip(self): #toggle equip/dequip status
        if self.is_equipped:
            self.dequip()
        else:
            self.equip()

    def equip(self):
        #if the slot is already being used, dequip whatever is there first
        old_equipment = get_equipped_in_slot(self.slot)
        if old_equipment is not None:
            old_equipment.dequip()
        #equip object and show message about it
        self.is_equipped = True
        message('Equipped ' + self.owner.name + ' on ' + self.slot + '.', libtcod.light_green)

    def dequip(self):
        #dequip object and show message about it
        if not self.is_equipped: return     #same as 'return None'
        self.is_equipped = False
        message('Dequipped ' + self.owner.name + ' from ' + self.slot + '.', libtcod.light_yellow)

def get_equipped_in_slot(slot): #returns the equipment in a slot, or None if slot is empty
    for obj in inventory:
        if obj.equipment and obj.equipment.slot == slot and obj.equipment.is_equipped:
            return obj.equipment
    return None

def get_all_equipped(obj): #returns list of equipped items
    if obj == player:
        equipped_list = []
        for item in inventory:
            if item.equipment and item.equipment.is_equipped:
                equipped_list.append(item.equipment)
        return equipped_list
    else:
        return [] #other objects have no equipment

def place_objects(room):
    #this is where we decide the chance of each monster/item appearing (in a room)

    #maximum number of monsters per room
    max_monsters = from_dungeon_level([[2,1],[3,4],[5,6]])
    #chance of each monster
    monster_chances = {}
    monster_chances['snake'] = 45
    monster_chances['slime'] = from_dungeon_level([[20,2],[40,3],[60,5]])
    monster_chances['snailman'] = from_dungeon_level([[5,2],[20,4],[30,6]])

    #max number of items per room
    max_items = from_dungeon_level([[1,1],[2,3],[3,5],[4,7]]) #1 : [1,1]
    #chance of each item (by default they have chance=0 at level 1, then it rises)
    item_chances = {}
    item_chances['heal'] = 35  #healing potion always shows up, even if all other items have 0 chance
    item_chances['blizzard'] = from_dungeon_level([[3,1],[15, 2]])
    item_chances['lightning'] = from_dungeon_level([[25, 4]])
    item_chances['fireball'] =  from_dungeon_level([[25, 6]])
    item_chances['confuse'] =   from_dungeon_level([[3,1],[10, 2]])
    item_chances['sword'] = from_dungeon_level([[5,1],[10,2],[15,3]])
    item_chances['shield'] = from_dungeon_level([[5,1],[10,2],[15,3]])


    #choose random number of monsters
    num_monsters = libtcod.random_get_int(0, 0, max_monsters)
    for i in range(num_monsters):
        #choose random position for this monster
        x = libtcod.random_get_int(0, room.x1 + 1, room.x2 -1) # problem? (fixed)
        y = libtcod.random_get_int(0, room.y1 + 1, room.y2 -1) # as above
        if not is_blocked(x, y):
            choice = random_choice(monster_chances)
            if choice == 'snailman': #30% chance of an orc
                #create an snailman
                fighter_component = Fighter(hp=10, defense=1, power=9, xp=100, death_function=monster_death)
                ai_component = BasicMonster()
                monster = Object(x, y, '$', 'snailman', libtcod.desaturated_green, blocks=True, fighter=fighter_component, ai=ai_component)
            elif choice == 'slime': #30% chance of an orc
                #create an slime
                fighter_component = Fighter(hp=6, defense=1, power=4, xp=55, death_function=monster_death)
                ai_component = BasicMonster()
                monster = Object(x, y, 236, 'slime', libtcod.desaturated_green, blocks=True, fighter=fighter_component, ai=ai_component)
            else:   #40% chance
                #create a snake
                fighter_component = Fighter(hp=2, defense=0, power=6, xp=35, death_function=monster_death)
                ai_component = BasicMonster()
                monster = Object(x, y, 'S', 'snake', libtcod.darker_green, blocks=True, fighter=fighter_component, ai=ai_component)
            objects.append(monster)

    #choose random number of items
    num_items = libtcod.random_get_int(0, 0, max_items)
    for i in range(num_items):
        #choose random position for item
        x = libtcod.random_get_int(0, room.x1+1, room.x2-1)
        y = libtcod.random_get_int(0, room.y1+1, room.y2-1)
        #only place if tile is not blocked
        if not is_blocked(x, y):
            choice = random_choice(item_chances)
            if choice == 'heal':
                #create healing potion
                item_component = Item(use_function=cast_heal)
                item = Object(x, y, '!', 'healing potion', libtcod.violet, item=item_component, always_visible=True)
            elif choice == 'lightning':
                #create lightning scroll
                item_component = Item(use_function=cast_lightning)
                item = Object(x, y, '#', 'scroll of lightning bolt', libtcod.light_yellow, item=item_component, always_visible=True)
            elif choice == 'confusion':
                #create 'confuse monster' scroll
                item_component = Item(use_function=cast_confuse)
                item = Object(x, y, '#', 'scroll of confusion', libtcod.light_yellow, item=item_component, always_visible=True)
            elif choice == 'blizzard':
                #create 'blizzard' scroll
                item_component = Item(use_function=cast_blizzard)
                item = Object(x, y, '#', 'scroll of blizzard', libtcod.light_yellow, item=item_component, always_visible=True)
            elif choice == 'sword':
                #create a sword
                equipment_component = Equipment(slot='right hand', power_bonus=3)
                item = Object(x, y, '/', 'sword of might', libtcod.silver, equipment=equipment_component)
            elif choice == 'shield':
                #create a shield
                equipment_component = Equipment(slot='left hand', defense_bonus=1)
                item = Object(x, y, '[', 'shield', libtcod.darker_orange, equipment=equipment_component)
            else:
                #create 'fireball' scroll
                item_component = Item(use_function=cast_fireball)
                item = Object(x, y, '#', 'scroll of fireball', libtcod.light_yellow, item=item_component, always_visible=True)
            objects.append(item)
            item.send_to_back() #items appear below other items
            item.always_visible = True #items are visible even out of FOV, if in explored area

def random_choice(option_dict):
    chances = option_dict.values()
    strings = option_dict.keys()
    #choose one option from a list of chances, returning its index
    #the dice will land on some number between 1 and the sum of the chances
    dice = libtcod.random_get_int(0, 1, sum(chances))
    #go through all chances, keeping the sum so far
    running_sum = 0
    choice = 0
    for w in chances:
        running_sum += w
        #see if the dice landed in the part that corresponds to this choice
        if dice <= running_sum:
            break
        choice += 1
    return strings[choice]

def from_dungeon_level(table):
    #returns a value that depends on that level. the table specifies what value occurs after each level, default is 0
    for (value, level) in reversed(table):
        if dungeon_level >= level:
            return value
    return 0

class Item:
    # this is a component for Object class
    def __init__(self, use_function=None):
        self.use_function = use_function

    def use(self):
        if self.owner.equipment:
            self.owner.equipment.toggle_equip()
            return
        #just call the 'use function' if it is defined:
        # USE_FUNCTION is called!! even though it's part of if statement.
        if self.use_function is None:
            message('The ' + self.owner.name + ' cannot be used.')
        else:
            if self.use_function() != 'cancelled':
                inventory.remove(self.owner) #destroy after use, unless it was cancelled for some reason

    #an item that can be picked up and used
    def pick_up(self):
        #add to the player's inventory and remove from the map
        if len(inventory) >= 26:
            message('Your inventory is full, you cannot pick up ' + self.owner.name + '.', libtcod.red)
        else:
            inventory.append(self.owner)
            objects.remove(self.owner)
            message('You have picked up a ' + self.owner.name + '!', libtcod.green)

            #special case: automatically equip, if the corresponding equipment slot is unused
            equipment = self.owner.equipment
            if equipment and get_equipped_in_slot(equipment.slot) is None:
                equipment.equip()

    def drop(self):
        #special case: if the object has the Equipment component, dequip it before dropping
        if self.owner.equipment:
            self.owner.equipment.dequip

        #add to the map and remove from the player's inventory. also, place it at the player's co-ords
        objects.append(self.owner)
        inventory.remove(self.owner)
        self.owner.x = player.x
        self.owner.y = player.y
        message('You dropped a ' + self.owner.name + '.', libtcod.yellow)

def cast_heal():
    #heal the player
    if player.fighter.hp == player.fighter.max_hp:
        message('You are already at full health.', libtcod.red)
        return 'cancelled'
    message('Your wounds start to feel better!', libtcod.light_violet)
    player.fighter.heal(HEAL_AMOUNT)

def cast_lightning():
    #find the closest enemy (inside a maximum range) and damage it
    monster = closest_monster(LIGHTNING_RANGE)
    if monster is None: #no enemy found within max range
        message('No enemy is close enough to strike.', libtcod.red)
        return 'cancelled'
    #zap it!
    message('A lightning bolt strikes the ' + monster.name + ' with a loud crack! The damage is ' +
            str(LIGHTNING_DAMAGE) + ' hit points.', libtcod.light_blue)
    monster.fighter.take_damage(LIGHTNING_DAMAGE)

def cast_confuse():
    # (can do 'closest enemy' original script, see pt9)
    #ask the player for a target to confuse
    message('Left-click an enemy to confuse it, or right-click to cancel', libtcod.light_cyan)
    monster = target_monster(CONFUSE_RANGE)
    if monster is None: return 'cancelled'
    #replace the monster's AI with a 'confused' one; after some turns it will restore the original AI
    old_ai = monster.ai
    monster.ai = ConfusedMonster(old_ai)
    monster.ai.owner = monster #!! - tell component who owns it
    message('The eyes of the ' + monster.name + ' look vacant, he begins to stumble around!', libtcod.light_green)

def cast_blizzard():
    #find all monsters inside max range
    close_enemies = []
    closest_dist = BLIZZARD_RANGE + 1

    for object in objects:
        if object.fighter and not object == player and libtcod.map_is_in_fov(fov_map, object.x, object.y):
            #calculate distance between monster and player
            dist = player.distance_to(object)
            if dist < closest_dist:
                close_enemies.append(object)
    if len(close_enemies) == 0:
        message('No enemy is close enough to cast.', libtcod.red)
        return 'cancelled'
    #kill them!
    for monster in close_enemies:
        damage = int(libtcod.random_get_float(0, 0, 1)*BLIZZARD_DAMAGE)
        if damage:
            message('The frosty beam zaps the ' + monster.name + ' for ' + str(damage) + ' hp!', libtcod.light_green)
        else:
            message('The frosty beam misses the ' + monster.name + '!', libtcod.red)
        monster.fighter.take_damage(damage)

def cast_fireball():
    #ask the player for a target tile to throw fireball at
    message('Left-click a target tile for the fireball, or right-click to cancel', libtcod.light_cyan)
    (x, y) = target_tile()
    if x is None: return 'cancelled'
    message('The fireball explores, burning everything within ' + str(FIREBALL_RADIUS) + ' tiles!')
    for obj in objects: #damage every fighter in range, including the player
        if (obj.distance(x, y) <= FIREBALL_RADIUS) and obj.fighter: #within radius of l-click & is_a_fighter
            message('The ' + obj.name + ' gets burned for ' + str(FIREBALL_DAMAGE) + ' hp.', libtcod.orange)
            obj.fighter.take_damage(FIREBALL_DAMAGE)

def fireball_animation():
    pass

#Components (fighter and monster) linked to Class:Object
class Fighter:
    #combat-related properties and methods (monster, player, NPC).
    def __init__(self, hp, defense, power, xp, death_function=None):
        self.base_max_hp = hp
        self.hp = hp
        self.base_defense = defense
        self.base_power = power
        self.xp = xp
        self.death_function = death_function

    @property
    def power(self): #return actual power, by summing the bonuses from all equipped items
        bonus = sum(equipment.power_bonus for equipment in get_all_equipped(self.owner))
        return self.base_power + bonus

    @property
    def defense(self):
        bonus = sum(equipment.defense_bonus for equipment in get_all_equipped(self.owner))
        return self.base_defense + bonus

    @property
    def max_hp(self):  #return actual max_hp, by summing up the bonuses from all equipped items
        bonus = sum(equipment.max_hp_bonus for equipment in get_all_equipped(self.owner))
        return self.base_max_hp + bonus

    def take_damage(self, damage):
        #apply damage if possible
        if damage > 0:
            self.hp -= damage
        #check for death. if there's a death function, call it
        if self.hp <= 0:
            function = self.death_function
            if function is not None:
                function(self.owner)
            if self.owner != player:
                player.fighter.xp += self.xp

    def attack(self, target):
        #a simple formula for attack damage
        ran_hit = libtcod.random_get_float(0, 0, 1)
        ran_def = libtcod.random_get_float(0, 0, 1)
        if libtcod.random_get_float(0, 0, 100) > 90:
            ran_hit = 2
            message(self.owner.name.capitalize() + ' PERFORMS A CRITICAL HIT!', self.owner.color)
        damage = int(ran_hit * self.power - ran_def * target.fighter.defense)
        if damage > 0:
            #print self.owner.name.capitalize() + ' attacks ' + target.name + ' for ' + str(damage) + ' hit points.'
            message(self.owner.name.capitalize() + ' attacks ' + target.name + ' for ' + str(damage) + ' hit points.',
                self.owner.color)
            target.fighter.take_damage(damage)
        else:
            #print self.owner.name.capitalize() + ' attacks ' + target.name + ' but has no effect.'
            message(self.owner.name.capitalize() + ' attacks ' + target.name + ' but has no effect.', libtcod.light_blue)

    def heal(self, amount):
        #heal by given amount, without going over maximum
        self.hp += amount
        if self.hp > self.max_hp:
            self.hp = self.max_hp

class BasicMonster:
    def __init__(self, has_seen_player=False):
        self.has_seen_player = has_seen_player
    #AI routine for a basic monster !!AI (for object)
    def take_turn(self):
        #basic mosnter takes turn. if you can see it, it can see you.
        monster = self.owner
        if libtcod.map_is_in_fov(fov_map, monster.x, monster.y):
            self.has_seen_player = True
            #move towards the player if far away
            if monster.distance_to(player) >= 2:
                monster.move_towards(player.x, player.y)
            #close enough to attack (if player is alive still)
            elif player.fighter.hp > 0:
                monster.fighter.attack(player)
                #print 'The attack of the ' + monster.name + ' bounces on your shiny carapace.'
        elif (self.owner.distance_to(player) <= MONSTER_SMELL_RANGE) and self.has_seen_player:
            monster.move_towards(player.x, player.y)

class ConfusedMonster:
    #AI for a temporarily confused monster (reverts to previous AI after a while).
    def __init__(self, old_ai, num_turns=CONFUSE_NUM_TURNS):
        self.old_ai = old_ai
        self.num_turns = num_turns

    def take_turn(self): #becomes new AI, so it is called repeatedly
        if self.num_turns > 0: #still confused
            #move a random direction and decrease the number of turns confused
            self.owner.move(libtcod.random_get_int(0, -1, 1), libtcod.random_get_int(0, -1, 1))
            self.num_turns -= 1
        else: #restore previous AI (this one will be deleted because it's no longer referenced)
            self.owner.ai = self.old_ai
            message('The ' + self.owner.name + ' is no longer confused.', libtcod.red)


def monster_death(monster):
    #transform into nasty corpse! no block, cannot be attacked, doesn't move
    #print monster.name.capitalize() + ' is dead!'
    message(monster.name.capitalize() + ' is dead! You again ' + str(monster.fighter.xp) + 'xp.', libtcod.red)
    monster.char = '%'
    monster.color = libtcod.dark_red
    monster.blocks = False
    monster.fighter = None
    monster.ai = None
    monster.name = 'remains of ' + monster.name
    monster.send_to_back()

def closest_monster(max_range):
    #find closest enemy, up to a max range, and in the player's FOV
    closest_enemy = None
    closest_dist = max_range + 1 #start with (slightly more than) max range

    for object in objects:
        if object.fighter and not object == player and libtcod.map_is_in_fov(fov_map, object.x, object.y):
            #calculate distance between this object and player
            dist = player.distance_to(object)
            if dist < closest_dist: #it's closer so remember it
                closest_enemy = object
                closest_dist = dist
    return closest_enemy

def player_death(player):
    #game over!
    global game_state
    #print "You died!"
    message("You died!", libtcod.darkest_purple)
    game_state = 'dead'

    #transform player into a corpse
    player.char = '%'
    player.color=libtcod.dark_red

def player_move_or_attack(dx, dy):
    global fov_recompute

    #the coordinates the player is moving to/attacking
    x = player.x + dx
    y = player.y + dy

    #try to find an attackable object there
    target = None
    for object in objects:
        if object.x == x and object.y == y and object.fighter:
            target = object
            break

    #attack if target found, move otherwise
    if target is not None:
        #print 'The ' + target.name + ' laughs at your puny attack technique!'
        player.fighter.attack(target)
    else:
        player.move(dx, dy)
        fov_recompute = True

def check_level_up():
    #see if the player's experience is enough to level up
    level_up_xp = LEVEL_UP_BASE + player.level * LEVEL_UP_FACTOR
    if player.fighter.xp >= level_up_xp:
        #it is! level up
        player.level += 1
        player.fighter.xp -= level_up_xp
        message('Your battle skills have improved! You reached level ' + str(player.level) + '!', libtcod.yellow)
        choice = None
        while choice == None:
            choice = menu('Level up! Choose a stat to raise:\n',
                          ['Constitution (+20 HP, from ' + str(player.fighter.max_hp) + ')',
                'Strength (+1 attack, from ' + str(player.fighter.power) + ')',
                'Agility (+1 defense, from ' + str(player.fighter.defense) + ')'], LEVEL_SCREEN_WIDTH)
        if choice == 0:
            player.fighter.base_max_hp += 20
            player.fighter.hp += 20
        elif choice == 1:
            player.fighter.base_power += 1
        elif choice == 2:
            player.fighter.base_defense += 1


def is_blocked(x, y):
    #tests if a map tile itself is blocked (like a wall)
    if map[x][y].blocked:
        return True
    #now check for any blocking objects
    for object in objects:
        if object.blocks and object.x == x and object.y == y:
            return True
    return False

def create_room(room):
    global map
    #go through the tiles in the rectangle and make them passable
    for x in range(room.x1 + 1, room.x2):
        for y in range(room.y1 + 1, room.y2):
            map[x][y].blocked = False
            map[x][y].block_sight = False

def create_h_tunnel(x1, x2, y):
    global map
    #horizontal tunnel. min() and max() are used in case x1>x2
    for x in range(min(x1, x2), max(x1, x2) + 1):
        map[x][y].blocked = False
        map[x][y].block_sight = False

def create_v_tunnel(y1, y2, x):
    global map
    #vertical tunnel
    for y in range(min(y1, y2), max(y1, y2) + 1):
        map[x][y].blocked = False
        map[x][y].block_sight = False

def make_map():
    global map, player, objects, stairs

    #list of objects with just the player
    objects = [player]

    #fill map with "blocked" tiles
    map = [[ Tile(True)
        for y in range(MAP_HEIGHT) ]
            for x in range(MAP_WIDTH) ]

    #random gen rooms (w/o carving them)
    rooms = []
    num_rooms = 0
    for r in range(MAX_ROOMS):
        #random width and height
        w = libtcod.random_get_int(0, ROOM_MIN_SIZE, ROOM_MAX_SIZE)
        h = libtcod.random_get_int(0, ROOM_MIN_SIZE, ROOM_MAX_SIZE)
        #random position without going out of the boundaries of the map
        x = libtcod.random_get_int(0, 0, MAP_WIDTH - w - 1)
        y = libtcod.random_get_int(0, 0, MAP_HEIGHT - h - 1)
        #;Rect' class makes rectangles easier to work with
        new_room = Rect(x, y, w, h)
        #run through the rooms and see if they intersect with this one
        failed = False
        for other_room in rooms:
            if new_room.intersect(other_room):
                failed = True
                break
        if not failed:
            #this means there are not intersections, so this room is valid
            #'paint' it to the map's tiles/ CARVE the room:
            create_room(new_room)
            #!#place monsters in room
            #!#place_objects(new_room)
            #center coords of the new room will be useful later
            (new_x, new_y) = new_room.center()

            if num_rooms == 0:
                #this s the first room, where the player starts
                player.x = new_x
                player.y = new_y
            else:
                #!# place monsters in rooms after (no monsters in room0)
                place_objects(new_room)
                #all rooms after first
                #connect it to the previous room with a tunnel
                (prev_x, prev_y) = rooms[num_rooms-1].center()

                #draw a coin
                if libtcod.random_get_int(0, 0, 1) == 1:
                    #first move horizontal, then vertical
                    create_h_tunnel(prev_x, new_x, prev_y)
                    create_v_tunnel(prev_y, new_y, new_x)
                else:
                    #first vertical, then horizontal
                    create_v_tunnel(prev_y, new_y, prev_x)
                    create_h_tunnel(prev_x, new_x, new_y)
            #finally, append the new room to the list
            rooms.append(new_room)
            num_rooms += 1
    #create stairs at the center of the last room
    stairs = Object(new_x, new_y, '>', 'stairs', libtcod.white, always_visible=True)
    objects.append(stairs)
    stairs.send_to_back() #so it's drawn below monsters

def next_level():
    global dungeon_level
    #advance to the next level
    message('You take a moment to rest and recover your stength.', libtcod.light_violet)
    player.fighter.heal(player.fighter.max_hp/2)
    message('After a rare moment of respite, you descend deeper into the horrid caverns.', libtcod.light_violet)
    dungeon_level += 1
    make_map() #recreate a fresh level
    initialize_fov()

def get_names_under_mouse():
    global mouse

    #return a string with the names of all objects under cursor
    (x, y) = (mouse.cx, mouse.cy)

    #create a list with the names of all objects at the mouse's coords and in FOV
    names = [obj.name for obj in objects
             if obj.x == x and obj.y == y and libtcod.map_is_in_fov(fov_map, obj.x, obj.y)]
    names = ', '.join(names) #joins names, separated by commas
    return names.capitalize()

def target_tile(max_range=None):
    #return the position of a tile left-clicked in the player's FOV (optionally in a range), or (None,None) if r-click
    global key, mouse
    while True:
        #render the screen. this erases the inventory and shows the names of objects under the mouse
        libtcod.console_flush()
        libtcod.sys_check_for_event(libtcod.EVENT_KEY_PRESS | libtcod.EVENT_MOUSE, key, mouse)
        render_all()
        (x, y) = (mouse.cx, mouse.cy)
        #3 requirements for shot to succeed~
        if ( mouse.lbutton_pressed and libtcod.map_is_in_fov(fov_map, x, y) and
            (max_range is None or player.distance(x,y) <= max_range)):
            return(x, y)
        if mouse.rbutton_pressed or key.vk == libtcod.KEY_ESCAPE:
            return (None, None) #cancel if the player right-clicked or pressed escape

def target_monster(max_range=None):
    #returns a clicked monster inside FOV up to a range, or None if right-clicked
    while True:
        (x, y) = target_tile(max_range)
        if x is None: #player cancelled
            return None

        #return the first clicked monster, otherwise continue looping
        for obj in objects:
            if obj.x == x and obj.y == y and obj.fighter and obj != player:
                return obj # #t

def render_bar(x, y, total_width, name, value, maximum, bar_color, back_color):
    #render a bar (hp, xp, etc.) first calculate the width of the bar
    bar_width = int(float(value) / maximum * total_width)

    #render the background first
    libtcod.console_set_default_background(panel, back_color)
    libtcod.console_rect(panel, x, y, total_width, 1, False, libtcod.BKGND_SCREEN)
    #now render the bar on top
    libtcod.console_set_default_background(panel, bar_color)
    if bar_width > 0:
        libtcod.console_rect(panel, x, y, bar_width, 1, False, libtcod.BKGND_SCREEN)
    #finally, overlayed: some centered text with values/name
    libtcod.console_set_default_foreground(panel, libtcod.white)
    libtcod.console_print_ex(panel, x + total_width/2, y, libtcod.BKGND_NONE, libtcod.CENTER,
                             name + ': ' + '/' + str(maximum))

def message(new_msg, color = libtcod.white):
    global game_msgs
    #split the message if necessary, among multiple lines
    new_msg_lines = textwrap.wrap(new_msg, MSG_WIDTH)

    for line in new_msg_lines:
        #if the buffer is full, remove the first line and make room for the new one
        if len(game_msgs) == MSG_HEIGHT:
            del game_msgs[0]
        #add new line as tuple, with text + color
        game_msgs.append( (line, color) )

def msgbox(text, width=50):
    menu(text, [], width) #use menu() as a sort of 'message box'

def render_all():
    global fov_map, color_dark_wall, color_light_wall
    global color_dark_ground, color_light_ground
    global fov_recompute, game_msgs

    if fov_recompute:
        #recompute FOV if needed (the player moved or something)
        fov_recompute = False
        libtcod.map_compute_fov(fov_map, player.x, player.y, TORCH_RADIUS, FOV_LIGHT_WALLS, FOV_ALGO)

        #go through all tiles, and set their background color according to the FOV
        for y in range(MAP_HEIGHT):
            for x in range(MAP_WIDTH):
                visible = libtcod.map_is_in_fov(fov_map, x, y)
                wall = map[x][y].block_sight
                if not visible:
                    #if it's not visible right now, the player can only see it if it's explored
                    if map[x][y].explored:
                        #it's out of the player's FOV
                        if wall:
                            libtcod.console_set_char_background(con, x, y, color_dark_wall, libtcod.BKGND_SET)
                        else:
                            libtcod.console_set_char_background(con, x, y, color_dark_ground, libtcod.BKGND_SET)
                else:
                    #it's visible
                    if wall:
                        libtcod.console_set_char_background(con, x, y, color_light_wall, libtcod.BKGND_SET )
                    else:
                        libtcod.console_set_char_background(con, x, y, color_light_ground, libtcod.BKGND_SET )
                    map[x][y].explored = True

    #draw all objects in the list
    for object in objects:
        object.draw()
    player.draw()

    #blit the contents of "con" to the root console
    libtcod.console_blit(con, 0, 0, SCREEN_WIDTH, SCREEN_HEIGHT, 0, 0, 0)

    # Prepare to render GUI (health) panel
    libtcod.console_set_default_background(panel, libtcod.black)
    libtcod.console_clear(panel)
    # Print game messages, one at a time
    y = 1
    for (line, color) in game_msgs:
        libtcod.console_set_default_foreground(panel, color)
        libtcod.console_print_ex(panel, MSG_X, y, libtcod.BKGND_NONE, libtcod.LEFT, line)
        y += 1
    #show player's stats
    render_bar( 1, 4, BAR_WIDTH, 'HP', player.fighter.hp, player.fighter.max_hp, libtcod.light_red, libtcod.darker_red)

    #show xp
    level_up_xp = LEVEL_UP_BASE + player.level * LEVEL_UP_FACTOR
    render_bar( 1, 3, BAR_WIDTH, 'XP', player.fighter.xp, level_up_xp, libtcod.light_green, libtcod.darker_green)

    #show game title and dungeon level
    libtcod.console_set_default_foreground(panel, libtcod.light_blue)
    libtcod.console_print_ex(panel, 1, 1, libtcod.BKGND_NONE, libtcod.LEFT, '  S N A I L M A N ')
    libtcod.console_set_default_foreground(panel, libtcod.white)
    libtcod.console_print_ex(panel, 1, 5, libtcod.BKGND_NONE, libtcod.LEFT, 'DUNGEON LVL: ' + str(dungeon_level))

    #show dungeon level
    libtcod.console_print_ex(con, 1, 1, libtcod.BKGND_NONE, libtcod.LEFT, 'LVL:' + str(dungeon_level)) #was none

    #display names of objects under cursor
    libtcod.console_set_default_foreground(panel, libtcod.light_gray)
    libtcod.console_print_ex(panel, 1, 0, libtcod.BKGND_NONE, libtcod.LEFT, get_names_under_mouse())

    #blit contents of panel to console
    libtcod.console_blit(panel, 0, 0, SCREEN_WIDTH, PANEL_HEIGHT, 0, 0, PANEL_Y)

def menu(header, options, width):
    if len(options) > 26: raise ValueError('Cannot have a menu with more than 26 options.')

    #calculate total height for the header (after auto-wrap) and one line per option
    header_height = libtcod.console_get_height_rect(con, 0, 0, width, SCREEN_HEIGHT, header)
    if header == '':
        header_height = 0
    height = len(options) + header_height

    #create an off-screen console that represents the menu's window
    window = libtcod.console_new(width, height)

    #print the header, with auto-wrap
    libtcod.console_set_default_foreground(window, libtcod.white)
    libtcod.console_print_rect_ex(window, 0, 0, width, height, libtcod.BKGND_NONE, libtcod.LEFT, header)
    #print all the options
    y = header_height
    letter_index = ord('a')
    for option_text in options:
        text = '(' + chr(letter_index) + ') ' + option_text
        libtcod.console_print_ex(window, 0, y, libtcod.BKGND_NONE, libtcod.LEFT, text)
        y += 1
        letter_index += 1
    #blit the contents of 'window' to the root console
    x = SCREEN_WIDTH/2 - width/2
    y = SCREEN_HEIGHT/2 - height/2
    libtcod.console_blit(window, 0, 0, width, height, 0, x, y, 1.0, 0.7)
    time.sleep(0.1)
    libtcod.console_flush()

    key = libtcod.console_wait_for_keypress(True)
    #special case: alt+ENTER = toggle fullscreen
    if key.vk == libtcod.KEY_ENTER and key.lalt:
        libtcod.console_set_fullscreen(not libtcod.console_is_fullscreen())
    #convert ASCII code to an index; if it corresponds to an option, return it
    index = key.c - ord('a')
    if index >= 0 and index < len(options): return index
    return None

def inventory_menu(header):

    if len(inventory) == 0:
        options = ['Inventory is empty.']
    else:
        options = []
        for item in inventory:
            text = item.name
            #show additional info, in case it's equipped
            if item.equipment and item.equipment.is_equipped:
                text = text + ' (on ' + item.equipment.slot + ')'
            options.append(text)

        #options = [item.name for item in inventory]
    index = menu(header, options, INVENTORY_WIDTH)
    #if an item was chosen, return it
    if index is None or len(inventory) == 0: return None
    return inventory[index].item




def handle_keys():
    global fov_recompute, game_state, key
    #key = libtcod.console_check_for_keypress()  #real-time
    #key = libtcod.console_wait_for_keypress(True)  #turn-based

    if key.vk == libtcod.KEY_ENTER and (key.lalt or key.ralt):
        #Alt+Enter: toggle fullscreen
        libtcod.console_set_fullscreen(not libtcod.console_is_fullscreen())

    elif key.vk == libtcod.KEY_ESCAPE:
        return 'exit'  #exit game

    if game_state == 'playing':
        #movement keys
        if key.vk == libtcod.KEY_KP8:
            player_move_or_attack(0, -1)
        elif key.vk == libtcod.KEY_KP2:
            player_move_or_attack(0, 1)
        elif key.vk == libtcod.KEY_KP4:
            player_move_or_attack(-1, 0)
        elif key.vk == libtcod.KEY_KP6:
            player_move_or_attack(1, 0)
        elif key.vk == libtcod.KEY_KP1:
            player_move_or_attack(-1, 1)
        elif key.vk == libtcod.KEY_KP3:
            player_move_or_attack(1, 1)
        elif key.vk == libtcod.KEY_KP7:
            player_move_or_attack(-1, -1)
        elif key.vk == libtcod.KEY_KP9:
            player_move_or_attack(1, -1)
        #[debug key section]
        elif key.vk == libtcod.KEY_BACKSPACE:
            debug()
        #[/debug key section]
        elif key.vk == libtcod.KEY_KP5:
            pass
        else:
            #test for other keys
            key_char = chr(key.c)
            if key_char == 'g':
                #pick up item
                for object in objects:  #look for an item in the player's title
                    if object.x == player.x and object.y == player.y and object.item:
                        object.item.pick_up()
                        break
            if key_char == 'd':
                chosen_item = inventory_menu('Press the key next to an item to drop it, or any other to cancel.\n')
                if chosen_item is not None:
                    chosen_item.drop()
            if key_char == 'i':
                #show inventory; if item is selected, use it
                chosen_item = inventory_menu('Press the key next to an item to use it, or any other to cancel.\n')
                if chosen_item is not None:
                    chosen_item.use()
            if key_char == '>':
                #go down stairs, if player is on them
                if stairs.x == player.x and stairs.y == player.y:
                    next_level()
            if key_char == 'c':
                #show character info
                level_up_xp = LEVEL_UP_BASE + player.level * LEVEL_UP_FACTOR
                msgbox('Character Information\n\nLevel: ' + str(player.level) +
                       '\nExperience: ' + str(player.fighter.xp) + ' / ' + str(level_up_xp) +
                       '\n\nMaximum HP: ' + str(player.fighter.max_hp) +
                    '\nAttack: ' + str(player.fighter.power) + '\nDefense: ' + str(player.fighter.defense), CHARACTER_SCREEN_WIDTH)
            return 'didnt-take-turn'

#for debug purposes:
def debug():
    for object in objects:  #look for an item in the player's title
        if object.equipment:
            object.item.pick_up()

#-------------------------#
#   Core Functions:       #
#-------------------------#

def new_game():
    global player, inventory, game_msgs, game_state, dungeon_level
    #create object representing the player
    fighter_component = Fighter(hp=30, defense=2, power=3, xp=0, death_function=player_death)
    player = Object(0, 0, '@', 'player', libtcod.dark_chartreuse, blocks=True, fighter=fighter_component)

    print "players xp is:"
    print player.fighter.xp

    #set player starting level
    player.level = 1
    #set dungeon level
    dungeon_level = 1
    #generate map (at this point it's not drawn to the screen)
    make_map()
    initialize_fov()
    game_state = 'playing'
    inventory = []
    #Gui Messages (msg + colour) stored as tuple, starts empty
    game_msgs = []
    #welcome message
    message('Welcome foul stranger to the Tomb of Despair! Prepare to do noble battle with the hordes of snakes '
        'and blobs! And prepare for the ultimate sacrifice, to dent your axe with the blood of elves!', libtcod.white)
    #starting equipment: a dagger
    equipment_component = Equipment(slot='right hand', power_bonus=2)
    obj = Object(0, 0, '-', 'dagger', libtcod.sky, equipment=equipment_component)
    inventory.append(obj)
    equipment_component.equip()
    obj.always_visible = True

def initialize_fov():
    global fov_recompute, fov_map
    fov_recompute = True
    #FOV calculcations
    fov_map = libtcod.map_new(MAP_WIDTH, MAP_HEIGHT)
    for y in range(MAP_HEIGHT):
        for x in range(MAP_WIDTH):
            libtcod.map_set_properties(fov_map, x, y, not map[x][y].block_sight, not map[x][y].blocked)
    libtcod.console_clear(con) #unexplored areas start black (default bg color)

def play_game():
    global key, mouse
    #game states
    player_action = None
    mouse = libtcod.Mouse()
    key = libtcod.Key()

    #main loop:
    while not libtcod.console_is_window_closed():
        #mouse/key input
        libtcod.sys_check_for_event(libtcod.EVENT_KEY_PRESS | libtcod.EVENT_MOUSE, key, mouse)
        #libtcod.sys_wait_for_event(libtcod.EVENT_KEY_PRESS | libtcod.EVENT_MOUSE, key, mouse)

        #render the screen
        render_all()

        #check if player has levelled up
        check_level_up()

        libtcod.console_flush()

        #erase all objects at their old locations, before they move
        for object in objects:
            object.clear()

        #handle keys and exit game if needed
        player_action = handle_keys()
        if player_action == 'exit':
            save_game() #!#
            break

        #let monsters take their turn
        if game_state == 'playing' and player_action != 'didnt-take-turn':
            for object in objects:
                if object.ai:
                    object.ai.take_turn()

def save_game():
    #open a new empty shelf (possibly overwriting an old one) to write game data [import shelve]
    # Shelve Flags: https://docs.python.org/3/library/dbm.html
    file = shelve.open('savegame', 'n') #flag=n ~ create new empty database
    file['map'] = map
    file['objects'] = objects
    file['player_index'] = objects.index(player)
    file['inventory'] = inventory
    file['game_msgs'] = game_msgs
    file['game_state'] = game_state
    file['stairs_index'] = objects.index(stairs)
    file['dungeon_level'] = dungeon_level
    file.close()

def load_game():
    #open the previously saved shelve and load the game data
    global map, objects, player, inventory, game_msgs, game_state, stairs, dungeon_level

    file = shelve.open('savegame','r') # flag=r ~ open existing database
    map = file['map']
    objects = file['objects']
    player = objects[file['player_index']]  #get index of player in objects list and access it
    inventory = file['inventory']
    game_msgs = file['game_msgs']
    game_state = file['game_state']
    stairs = objects[file['stairs_index']]
    dungeon_level = file['dungeon_level']
    file.close()

    initialize_fov()


#-------------------------#
#   Core Init:            #
#-------------------------#

libtcod.console_set_custom_font('terminal16x16_gs_ro.png', libtcod.FONT_TYPE_GREYSCALE | libtcod.FONT_LAYOUT_ASCII_INROW)
#libtcod.console_set_custom_font('Aesomatica_16x16.png', libtcod.FONT_TYPE_GREYSCALE | libtcod.FONT_LAYOUT_ASCII_INROW)
libtcod.console_init_root(SCREEN_WIDTH, SCREEN_HEIGHT, 'rogue test', False)
libtcod.sys_set_fps(LIMIT_FPS)
con = libtcod.console_new(MAP_WIDTH, MAP_HEIGHT)
panel = libtcod.console_new(SCREEN_WIDTH, PANEL_HEIGHT)

#-------------------------#
#   Run Game:             #
#-------------------------#


def intro_text():
    #show the game's title and some credits
    txt = []
    txt.append('.________.______  .______  .___ .___    ._____.___ ._______.______  ')
    txt.append('|    ___/:      \ :      \ : __||   |   :         |: .____/:      \ ')
    txt.append('|___    \|       ||   .   || : ||   |   |   \  /  || : _/\ |       |')
    txt.append('|       /|   |   ||   :   ||   ||   |/\ |   |\/   ||   /  \|   |   |')
    txt.append('|__:___/ |___|   ||___|   ||   ||   /  \|___| |   ||_.: __/|___|   |')
    txt.append('   :         |___|    |___||___||______/      |___|   :/       |___|')
    libtcod.console_set_default_foreground(0, libtcod.lighter_blue)
    #libtcod.console_print_ex(0, 15, 1, libtcod.BKGND_NONE, libtcod.CENTER,
    #        'TOMBS OF THE ANCIENT KINGS')
    y = 0
    for line in txt:
        #my_color = libtcod.Color(255-42*y, 255-30*y, 255)
        my_color = libtcod.Color(42*y, 30*y, 255)
        libtcod.console_set_default_foreground(0, my_color)
        libtcod.console_print_ex(0, 5, y+3, libtcod.BKGND_NONE, libtcod.LEFT, line)
        y += 1

def main_menu():
    img = libtcod.image_load('leng.png')

    while not libtcod.console_is_window_closed():
        #show the background image, at twice the regular console resolution
        libtcod.image_blit_2x(img, 0, 0, 0)

        #show the game's title and some credits
        intro_text()

        #show options and wait for player decision
        choice = menu('', ['New Game', 'Continue Last Game','Save & Quit'], 24)

        if choice == 0: #new game
            new_game()
            play_game()
        if choice == 1: #load last game
            try:
                load_game()
            except:
                #time.sleep(0.1)
                msgbox('\n No saved game to load. \n', 24)
                continue
            play_game()
        elif choice == 2: #quit
            break

main_menu()
