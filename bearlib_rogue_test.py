# Notes:
# Up to section "Using Items"
# http://www.roguebasin.com/index.php?title=Complete_Roguelike_Tutorial,_using_python%2Blibtcod,_part_8
# BGRA/ARGB conversion: 0xAARRGGBB @ http://www.binaryhexconverter.com/decimal-to-hex-converter

#import
import PyBearLibTerminal as terminal
import libtcodpy as libtcod
import math
import textwrap
import shelve

#size of window
SCREEN_WIDTH = 80
SCREEN_HEIGHT = 50

#size of map
MAP_WIDTH = 80
MAP_HEIGHT = 43

#dungeon gen settings
ROOM_MAX_SIZE = 10
ROOM_MIN_SIZE = 6
MAX_ROOMS = 30
MAX_ROOM_MONSTERS = 0
MAX_ROOM_ITEMS = 2
MONSTER_SMELL_RANGE = 30

#spell values
HEAL_AMOUNT = 4
LIGHTNING_DAMAGE = 20
LIGHTNING_RANGE = 5
CONFUSE_NUM_TURNS = 10
CONFUSE_RANGE = 8
BLIZZARD_RANGE = 8
BLIZZARD_DAMAGE = 6
FIREBALL_RADIUS = 3
FIREBALL_DAMAGE = 12

#Player xp attributes
LEVEL_UP_BASE = 200 #200
LEVEL_UP_FACTOR = 150 #150

#FOV settings
FOV_ALGO = 0  #default FOV algorithm
FOV_LIGHT_WALLS = True  #light walls or not
TORCH_RADIUS = 10

tile_dark_wall = 14
tile_light_wall = 13
tile_dark_ground = 0
tile_light_ground = 1

#GUI settings
BAR_WIDTH = 20
PANEL_HEIGHT = 7
PANEL_Y = SCREEN_HEIGHT - PANEL_HEIGHT
MSG_X = BAR_WIDTH + 2
MSG_WIDTH = SCREEN_WIDTH - BAR_WIDTH - 2
MSG_HEIGHT = PANEL_HEIGHT - 1
BAR_CHAR = 20
INVENTORY_WIDTH = 50
MENU_BACKGROUND_COLOR = 3716001477
LEVEL_SCREEN_WIDTH = 40
CHARACTER_SCREEN_WIDTH = 30

class Tile:
    #a tile of the map and its properties
    def __init__(self, blocked, block_sight = None):
        self.blocked = blocked
        #all tiles start unexplored
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
        center_x = (self.x1 + self.x2) / 2
        center_y = (self.y1 + self.y2) / 2
        return (center_x, center_y)

    def intersect(self, other):
        #returns true if this rectangle intersects with another one
        return (self.x1 <= other.x2 and self.x2 >= other.x1 and
                self.y1 <= other.y2 and self.y2 >= other.y1)

class Object:
    #this is a generic object: the player, a monster, an item, the stairs...
    #it's always represented by a character on screen.
    def __init__(self, x, y, char, name, blocks=False, always_visible=False, fighter=None, ai=None, item=None, equipment=None):
        self.x = x
        self.y = y
        self.char = char
        self.name = name
        self.blocks = blocks
        self.always_visible = always_visible

        self.fighter = fighter
        if self.fighter:
            self.fighter.owner = self

        self.ai = ai
        if self.ai:
            self.ai.owner = self

        self.item = item
        if self.item: #let the item know its owner
            self.item.owner = self

        self.equipment = equipment
        if self.equipment: #let it know self
            self.equipment.owner = self
            self.item = Item()
            self.item.owner = self

    def move(self, dx, dy):
        #move by the given amount
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
        return math.sqrt(dx ** 2 + dy ** 2)

    def distance(self, x, y):
        #return the distance to some coordinates
        return math.sqrt((x - self.x) ** 2 + (y - self.y) ** 2)

    def draw(self):
        #set the color and then draw the character that represents this object at its position
        if (libtcod.map_is_in_fov(fov_map, self.x, self.y) or
            (self.always_visible and map[self.x][self.y].explored)):
            #set color and then draw character at location
            if self.fighter:
                terminal.layer(4)
            else:
                terminal.layer(3)
            terminal.color("#FFFFFF")
            terminal.put(self.x, self.y, self.char)

    def clear(self):
        #erase the character that represents this object
        if self.fighter:
            terminal.layer(4)
        else:
            terminal.layer(3)
        terminal.put(self.x, self.y, ' ')

    def send_to_back(self):
        #make this object be drawn first, so all others appear above it if they're in the same tile.
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
        message('Equipped ' + self.owner.name + ' on ' + self.slot + '.', 4282384191)

    def dequip(self):
        #dequip object and show message about it
        if not self.is_equipped: return     #same as 'return None'
        self.is_equipped = False
        message('Dequipped ' + self.owner.name + ' from ' + self.slot + '.', 4294967103)

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
    num_monsters = libtcod.random_get_int(0, 0, MAX_ROOM_MONSTERS)
    for i in range(num_monsters):
        #choose random spot for this monster
        x = libtcod.random_get_int(0, room.x1+1, room.x2-1)
        y = libtcod.random_get_int(0, room.y1+1, room.y2-1)
        #only place it if the tile is not blocked 160, 162, etc
        # monster = Object(x, y, 160, 'slime', blocks=True, fighter=fighter_component, ai=ai_component)
        if not is_blocked(x, y):
            choice = random_choice(monster_chances)
            if choice == 'snailman': #30% chance of an orc
                #create an snailman
                fighter_component = Fighter(hp=10, defense=1, power=9, xp=100, death_function=monster_death)
                ai_component = BasicMonster()
                monster = Object(x, y, 160, 'snailman', blocks=True, fighter=fighter_component, ai=ai_component)
            elif choice == 'slime': #30% chance of an orc
                #create an slime
                fighter_component = Fighter(hp=6, defense=1, power=4, xp=55, death_function=monster_death)
                ai_component = BasicMonster()
                monster = Object(x, y, 162, 'slime', blocks=True, fighter=fighter_component, ai=ai_component)
            else:   #40% chance
                #create a snake
                fighter_component = Fighter(hp=2, defense=0, power=6, xp=35, death_function=monster_death)
                ai_component = BasicMonster()
                monster = Object(x, y, 161, 'snake', blocks=True, fighter=fighter_component, ai=ai_component)
            objects.append(monster)

    #choose random number of items
    num_items = libtcod.random_get_int(0, 0, MAX_ROOM_ITEMS)
    for i in range(num_items):
        #choose random spot for this item
        x = libtcod.random_get_int(0, room.x1+1, room.x2-1)
        y = libtcod.random_get_int(0, room.y1+1, room.y2-1)

        #only place it if the tile is not blocked scoll:21, potion: 24
        if not is_blocked(x, y):
            choice = random_choice(item_chances)
            if choice == 'heal':
                #create healing potion
                item_component = Item(use_function=cast_heal)
                item = Object(x, y, 24, 'healing potion', item=item_component, always_visible=True)
            elif choice == 'lightning':
                #create lightning scroll
                item_component = Item(use_function=cast_lightning)
                item = Object(x, y, 21, 'scroll of lightning bolt', item=item_component, always_visible=True)
            elif choice == 'confusion':
                #create 'confuse monster' scroll
                item_component = Item(use_function=cast_confuse)
                item = Object(x, y, 21, 'scroll of confusion', item=item_component, always_visible=True)
            elif choice == 'blizzard':
                #create 'blizzard' scroll
                item_component = Item(use_function=cast_blizzard)
                item = Object(x, y, 21, 'scroll of blizzard', item=item_component, always_visible=True)
            elif choice == 'sword':
                #create a sword
                equipment_component = Equipment(slot='right hand', power_bonus=3)
                item = Object(x, y, '/', 'sword of might', equipment=equipment_component)
            elif choice == 'shield':
                #create a shield
                equipment_component = Equipment(slot='left hand', defense_bonus=1)
                item = Object(x, y, '[', 'shield', equipment=equipment_component)
            else:
                #create 'fireball' scroll
                item_component = Item(use_function=cast_fireball)
                item = Object(x, y, 21, 'scroll of fireball', item=item_component, always_visible=True)
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
    #an item that can be picked up and used.
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

    def pick_up(self):
        #add to the player's inventory and remove from the map full: 4294901760, you picked 4278255360)
        if len(inventory) >= 26:
            message('Your inventory is full, you cannot pick up ' + self.owner.name + '.', 4294901760)
        else:
            inventory.append(self.owner)
            objects.remove(self.owner)
            message('You have picked up a ' + self.owner.name + '!', 4278255360)

            #special case: automatically equip, if the corresponding equipment slot is unused
            equipment = self.owner.equipment
            if equipment and get_equipped_in_slot(equipment.slot) is None:
                equipment.equip()

    def drop(self):
        #special case: if the object has the Equipment component, dequip it before dropping
        if self.owner.equipment:
            self.owner.equipment.dequip
        #add to the map and remove from the player's inventory. also, place it at the player's coordinates
        objects.append(self.owner)
        inventory.remove(self.owner)
        self.owner.x = player.x
        self.owner.y = player.y
        message('You dropped a ' + self.owner.name + '.', 4294967040)

def cast_heal():
    #heal the player
    if player.fighter.hp == player.fighter.max_hp:
        message('You are already at full health.', 4294901760)
        return 'cancelled'

    message('Your wounds start to feel better!', 4286513407)
    player.fighter.heal(HEAL_AMOUNT)

def cast_lightning():
    #find closest enemy (inside a maximum range) and damage it
    monster = closest_monster(LIGHTNING_RANGE)
    if monster is None:  #no enemy found within maximum range
        message('No enemy is close enough to strike.', 4294901760)
        return 'cancelled'

    #zap it!
    message('A lighting bolt strikes the ' + monster.name + ' with a loud crack! The damage is '
        + str(LIGHTNING_DAMAGE) + ' hit points.', 4282335231)
    monster.fighter.take_damage(LIGHTNING_DAMAGE)

def cast_confuse():
    #ask the player for a target to confuse
    message('Left-click an enemy to confuse it, or right-click to cancel.', 4282384383)
    monster = target_monster(CONFUSE_RANGE)
    if monster is None: return 'cancelled'

    #replace the monster's AI with a "confused" one; after some turns it will restore the old AI
    old_ai = monster.ai
    monster.ai = ConfusedMonster(old_ai)
    monster.ai.owner = monster  #tell the new component who owns it
    message('The eyes of the ' + monster.name + ' look vacant, as he starts to stumble around!', 4282384191)

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
        message('No enemy is close enough to cast.', 4294901760)
        return 'cancelled'
    #kill them!
    for monster in close_enemies:
        damage = int(libtcod.random_get_float(0, 0, 1)*BLIZZARD_DAMAGE)
        if damage:
            message('The frosty beam zaps the ' + monster.name + ' for ' + str(damage) + ' hp!', 4282384191)
        else:
            message('The frosty beam misses the ' + monster.name + '!', libtcod.red)
        monster.fighter.take_damage(damage)

def cast_fireball():
    #ask the player for a target tile to throw a fireball at
    message('Left-click a target tile for the fireball, or right-click to cancel.', 4282384383)
    (x, y) = target_tile()
    if x is None: return 'cancelled'
    message('The fireball explodes, burning everything within ' + str(FIREBALL_RADIUS) + ' tiles!', 4294934272)

    for obj in objects:  #damage every fighter in range, including the player
        if obj.distance(x, y) <= FIREBALL_RADIUS and obj.fighter:
            message('The ' + obj.name + ' gets burned for ' + str(FIREBALL_DAMAGE) + ' hp.', 4294934272)
            obj.fighter.take_damage(FIREBALL_DAMAGE)

class Fighter:
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
        #random-rolled attack damage, with crits
        ran_hit = libtcod.random_get_float(0, 0, 1)
        ran_def = libtcod.random_get_float(0, 0, 1)
        if libtcod.random_get_float(0, 0, 100) > 90:
            ran_hit = 2
            message(self.owner.name.capitalize() + ' PERFORMS A CRITICAL HIT!', 4294901887)
        damage = int(ran_hit * self.power - ran_def * target.fighter.defense)
        if damage > 0:
            #print self.owner.name.capitalize() + ' attacks ' + target.name + ' for ' + str(damage) + ' hit points.'
            message(self.owner.name.capitalize() + ' attacks ' + target.name + ' for ' + str(damage) + ' hit points.',
                4286578559)
            target.fighter.take_damage(damage)
        else:
            #print self.owner.name.capitalize() + ' attacks ' + target.name + ' but has no effect.'
            message(self.owner.name.capitalize() + ' attacks ' + target.name + ' but has no effect.', 4282335231)

    def heal(self, amount):
        #heal by the given amount, without going over the maximum
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

    def take_turn(self):
        if self.num_turns > 0:  #still confused...
            #move in a random direction, and decrease the number of turns confused
            self.owner.move(libtcod.random_get_int(0, -1, 1), libtcod.random_get_int(0, -1, 1))
            self.num_turns -= 1

        else:  #restore the previous AI (this one will be deleted because it's not referenced anymore)
            self.owner.ai = self.old_ai
            message('The ' + self.owner.name + ' is no longer confused!', 4294901760)

def monster_death(monster):
    #transform it into a nasty corpse! it doesn't block, can't be
    #attacked and doesn't move
    message(monster.name.capitalize() + ' is dead! You again ' + str(monster.fighter.xp) + 'xp.', 4294901760)
    monster.char = 22
    monster.blocks = False
    monster.fighter = None
    monster.ai = None
    monster.name = 'remains of ' + monster.name
    monster.send_to_back()
    #clearing monster sprite from its layer, since corpse is not 'fighter' type
    terminal.layer(4)
    terminal.clear_area(monster.x, monster.y, 1, 1)

def closest_monster(max_range):
    #find closest enemy, up to a maximum range, and in the player's FOV
    closest_enemy = None
    closest_dist = max_range + 1  #start with (slightly more than) maximum range

    for object in objects:
        if object.fighter and not object == player and libtcod.map_is_in_fov(fov_map, object.x, object.y):
            #calculate distance between this object and the player
            dist = player.distance_to(object)
            if dist < closest_dist:  #it's closer, so remember it
                closest_enemy = object
                closest_dist = dist
    return closest_enemy

def player_death(player):
    #the game ended!
    global game_state
    message('You died!', 4294901760)
    game_state = 'dead'

    #for added effect, transform the player into a corpse!
    player.char = 22

def player_move_or_attack(dx, dy):
    global fov_recompute
    #the coordinates the player is moving to/attacking
    x = player.x + dx
    y = player.y + dy
    #try to find an attackable object there
    target = None
    for object in objects:
        if object.fighter and object.x == x and object.y == y:
            target = object
            break
    #attack if target found, move otherwise
    if target is not None:
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
        message('Your battle skills have improved! You reached level ' + str(player.level) + '!', 4294967040)
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
    #first test the map tile
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
    global map, objects, stairs

    #the list of objects with just the player
    objects = [player]

    #fill map with "blocked" tiles
    map = [[ Tile(True)
        for y in range(MAP_HEIGHT) ]
            for x in range(MAP_WIDTH) ]

    rooms = []
    num_rooms = 0

    for r in range(MAX_ROOMS):
        #random width and height
        w = libtcod.random_get_int(0, ROOM_MIN_SIZE, ROOM_MAX_SIZE)
        h = libtcod.random_get_int(0, ROOM_MIN_SIZE, ROOM_MAX_SIZE)
        #random position without going out of the boundaries of the map
        x = libtcod.random_get_int(0, 0, MAP_WIDTH - w - 1)
        y = libtcod.random_get_int(0, 0, MAP_HEIGHT - h - 1)
        #"Rect" class makes rectangles easier to work with
        new_room = Rect(x, y, w, h)
        #run through the other rooms and see if they intersect with this one
        failed = False
        for other_room in rooms:
            if new_room.intersect(other_room):
                failed = True
                break

        if not failed:
            #this means there are no intersections, so this room is valid
            #"paint" it to the map's tiles
            create_room(new_room)

            #add some contents to this room, such as monsters
            #place_objects(new_room) **moved**

            #center coordinates of new room, will be useful later
            (new_x, new_y) = new_room.center()
            if num_rooms == 0:
                #this is the first room, where the player starts at
                player.x = new_x
                player.y = new_y
            else:
                #all rooms after the first:

                #monsters only in later rooms
                place_objects(new_room)
                #connect it to the previous room with a tunnel
                #center coordinates of previous room
                (prev_x, prev_y) = rooms[num_rooms-1].center()
                #draw a coin (random number that is either 0 or 1)
                if libtcod.random_get_int(0, 0, 1) == 1:
                    #first move horizontally, then vertically
                    create_h_tunnel(prev_x, new_x, prev_y)
                    create_v_tunnel(prev_y, new_y, new_x)
                else:
                    #first move vertically, then horizontally
                    create_v_tunnel(prev_y, new_y, prev_x)
                    create_h_tunnel(prev_x, new_x, new_y)

            #finally, append the new room to the list
            rooms.append(new_room)
            num_rooms += 1

    #create stairs at the center of the last room
    stairs = Object(new_x, new_y, 7, 'stairs', always_visible=True)
    objects.append(stairs)
    stairs.send_to_back()  #so it's drawn below the monsters

def next_level():
    #advance to the next level
    global dungeon_level
    terminal.clear()
    message('You take a moment to rest, and recover your strength.', 4288626687)
    player.fighter.heal(player.fighter.max_hp / 2)  #heal the player by 50%

    dungeon_level += 1
    message('After a rare moment of peace, you descend deeper into the horrid caverns.', 4294901760)
    make_map()  #create a fresh new level!
    initialize_fov()

def get_names_under_mouse():
    #global mouse
    #mouse = terminal.read()
    #if mouse == terminal.TK_MOUSE_MOVE:
    #    print terminal.state

    #return a string with the names of all objects under the mouse
    (x, y) = (terminal.state(terminal.TK_MOUSE_X), terminal.state(terminal.TK_MOUSE_Y)) #!!

    #create a list with the names of all objects at the mouse's coordinates and in FOV
    names = [obj.name for obj in objects
        if obj.x == x and obj.y == y and libtcod.map_is_in_fov(fov_map, obj.x, obj.y)]

    names = ', '.join(names)  #join the names, separated by commas
    return names.capitalize()

def target_tile(max_range=None):
    #return the position of a tile left-clicked in player's FOV (optionally in a range), or (None,None) if right-clicked.
    global key, mouse
    while True:
        #render the screen. this erases the inventory and shows the names of objects under the mouse.
        render_all()
        terminal.refresh()
        key = terminal.read() #temporary halt of operation, wait for keypress/click

        #render_all()
        (x, y) = (terminal.state(terminal.TK_MOUSE_X), terminal.state(terminal.TK_MOUSE_Y))

        #if mouse.rbutton_pressed or key.vk == libtcod.KEY_ESCAPE:
        if key == terminal.TK_ESCAPE or key == terminal.TK_MOUSE_RIGHT:
            return (None, None)  #cancel if the player right-clicked or pressed Escape

        #accept the target if the player clicked in FOV, and in case a range is specified, if it's in that range
        #if (mouse.lbutton_pressed and libtcod.map_is_in_fov(fov_map, x, y) and
        if (key == terminal.TK_MOUSE_LEFT and libtcod.map_is_in_fov(fov_map, x, y) and
            (max_range is None or player.distance(x, y) <= max_range)):
            return (x, y)

def target_monster(max_range=None):
    #returns a clicked monster inside FOV up to a range, or None if right-clicked
    while True:
        (x, y) = target_tile(max_range)
        if x is None:  #player cancelled
            return None

        #return the first clicked monster, otherwise continue looping
        for obj in objects:
            if obj.x == x and obj.y == y and obj.fighter and obj != player:
                return obj

def render_bar(x, y, total_width, name, value, maximum, bar_color, back_color):
    #adjust: move panel to desired location (bottom of console)
    y = y + PANEL_Y
    #set console to GUI layer
    terminal.layer(5)
    #render a bar (HP, experience, etc). first calculate the width of the bar
    bar_width = int(float(value) / maximum * total_width)
    #set total-width back bar color
    terminal.color(back_color)
    #terminal: draw a row of given length
    a = 0
    for b in range(total_width):
        terminal.put(x + a, y, BAR_CHAR)
        a += 1
    #now render the bar on top
    #set bar itself color
    terminal.color(bar_color)
    #libtcod.console_set_default_background(panel, bar_color)
    if bar_width > 0:
        a = 0
        for b in range(bar_width):
            terminal.put(x + a, y, BAR_CHAR)
            a += 1
    #finally, some centered text with the values
    #first clear previous text, then draw new text, centred.
    terminal.color("#FFFFFF")
    terminal.layer(6)
    terminal.clear_area(x, y, total_width, 1)
    bar_center = len(name + ': ' + str(value) + '/' + str(maximum))/2
    terminal.print_(x + total_width/2 - bar_center, y, name + ': ' + str(value) + '/' + str(maximum))

def message(new_msg, color = "#FFFFFF"):
    #split the message if necessary, among multiple lines
    new_msg_lines = textwrap.wrap(new_msg, MSG_WIDTH)

    for line in new_msg_lines:
        #if the buffer is full, remove the first line to make room for the new one
        if len(game_msgs) == MSG_HEIGHT:
            del game_msgs[0]

        #add the new line as a tuple, with the text and the color
        game_msgs.append( (line, color) )

def msgbox(text, width=50):
    menu(text, [], width) #use menu() as a sort of "message box"

def render_all():
    global fov_map, color_dark_wall, color_light_wall
    global color_dark_ground, color_light_ground
    global fov_recompute, game_msgs

    if fov_recompute:
        #recompute FOV if needed (the player moved or something)
        fov_recompute = False
        libtcod.map_compute_fov(fov_map, player.x, player.y, TORCH_RADIUS, FOV_LIGHT_WALLS, FOV_ALGO)
        terminal.color("#FFFFFF")
        #go through all tiles, and set their background color according to the FOV
        for y in range(MAP_HEIGHT):
            for x in range(MAP_WIDTH):
                visible = libtcod.map_is_in_fov(fov_map, x, y)
                wall = map[x][y].block_sight
                if not visible:
                    #if it's not visible right now, the player can only see it if it's explored
                    terminal.layer(2)
                    if map[x][y].explored:
                        if wall:
                            terminal.put(x, y, tile_dark_wall)
                        else:
                            terminal.put(x, y, tile_dark_ground)
                else:
                    #it's visible
                    if wall:
                        terminal.put(x, y, tile_light_wall)
                    else:
                        terminal.put(x, y, tile_light_ground)
                    #since it's visible, explore it
                    map[x][y].explored = True

    #draw all objects in the list, except the player. we want it to
    for object in objects:
        object.draw()

    #prepare to render the GUI text
    terminal.layer(6)
    terminal.clear_area(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT)
    #print the game messages, one line at a time
    y = 1
    for (line, color) in game_msgs:
        terminal.color(color)
        terminal.print_(MSG_X, y+PANEL_Y, line)
        y += 1

    #show the player's hp
    render_bar(1, 3, BAR_WIDTH, 'HP', player.fighter.hp, player.fighter.max_hp, 4294917951, 4286513152)

    #show xp
    level_up_xp = LEVEL_UP_BASE + player.level * LEVEL_UP_FACTOR
    render_bar( 1, 4, BAR_WIDTH, 'XP', player.fighter.xp, level_up_xp, 4282384191, 4278222592)

    #print dungeon level
    terminal.layer(6)
    terminal.color(4282335231)
    terminal.print_(1,PANEL_Y +1,'  S N A I L M A N ')
    terminal.color(4294967295)
    terminal.print_(1,PANEL_Y + 5, 'Dungeon level ' + str(dungeon_level))

    #display names of objects under the mouse
    #still on layer 6 ***** (text layer)
    terminal.print_(1, PANEL_Y, get_names_under_mouse())

def menu(header, options, width):
    if len(options) > 26: raise ValueError('Cannot have a menu with more than 26 options.')
    #calculate total height for the header (after auto-wrap) and one line per option
    #header_height = libtcod.console_get_height_rect(con, 0, 0, width, SCREEN_HEIGHT, header)!!!

    header_height = len(textwrap.wrap(header, width))
    height = len(options) + header_height
    #set co-ords of menu
    menu_x = SCREEN_WIDTH/2 - width/2
    menu_y = SCREEN_HEIGHT/2 - height/2

    #paint menu background
    terminal.layer(5)
    terminal.color(MENU_BACKGROUND_COLOR) #menu
    for y_bg in range(height):
        for x_bg in range(width):
            terminal.put(menu_x + x_bg, menu_y + y_bg, 20)


    #print the header, with auto-wrap
    terminal.layer(6)
    terminal.color('#FFFFFF')
    y = 0
    for line in textwrap.wrap(header, width):
        terminal.print_(menu_x, menu_y + y, line)
        y += 1

    #position of options, below header (y)
    y = menu_y + header_height
    letter_index = ord('a')

    #print all the options
    for option_text in options:
        text = '(' + chr(letter_index) + ') ' + option_text
        #libtcod.console_print_ex(window, 0, y, libtcod.BKGND_NONE, libtcod.LEFT, text)
        terminal.print_(menu_x, y, text)
        y += 1
        letter_index += 1
    #present the root console to the player and wait for a key-press

    terminal.refresh()
    key = terminal.read() #temporary halt of operation, wait for keypress/click

    #clear the menu from screen
    terminal.layer(5)
    terminal.clear_area(menu_x, menu_y, width, height)

    if terminal.state(terminal.TK_CHAR): #!! maybe no if statement here?
        #convert the ASCII code to an index; if it corresponds to an option, return it
        index = terminal.state(terminal.TK_CHAR) - ord('a')
        if index >= 0 and index < len(options): return index
        return None

def inventory_menu(header):
    #show a menu with each item of the inventory as an option
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
    #global fov_recompute
    # Read keyboard input
    global key
    key = terminal.read()
    if key == terminal.TK_ESCAPE:
        # Close terminal
        return 'exit'
    if game_state == 'playing':
        #??? it was 'exit()'
        a = 'player moved'
        if key == terminal.TK_KP_2:
            player_move_or_attack(0, 1)
            return a
        elif key == terminal.TK_KP_8:
            player_move_or_attack(0, -1)
            return a
        elif key == terminal.TK_KP_6:
            player_move_or_attack(1, 0)
            return a
        elif key == terminal.TK_KP_4:
            player_move_or_attack(-1, 0)
            return a
        elif key == terminal.TK_KP_7:
            player_move_or_attack(-1, -1)
            return a
        elif key == terminal.TK_KP_9:
            player_move_or_attack(1, -1)
            return a
        elif key == terminal.TK_KP_1:
            player_move_or_attack(-1, 1)
            return a
        elif key == terminal.TK_KP_3:
            player_move_or_attack(1, 1)
            return a
        elif key == terminal.TK_KP_5:
            return a
        else: #test for other keys
            if key == terminal.TK_G:
                #pick up an item
                for object in objects:  #look for an item in the player's tile
                    if object.x == player.x and object.y == player.y and object.item:
                        object.item.pick_up()
                        break

            if key == terminal.TK_I:
                #show the inventory; if an item is selected, use it
                chosen_item = inventory_menu('Press the key next to an item to use it, or any other to cancel.\n')
                if chosen_item is not None:
                    chosen_item.use()

            if key == terminal.TK_D:
                #show the inventory; if an item is selected, drop it
                chosen_item = inventory_menu('Press the key next to an item to drop it, or any other to cancel.\n')
                if chosen_item is not None:
                    chosen_item.drop()

            if key == terminal.TK_C:
                #show character info
                level_up_xp = LEVEL_UP_BASE + player.level * LEVEL_UP_FACTOR
                msgbox('Character Information\n\nLevel: ' + str(player.level) +
                       '\nExperience: ' + str(player.fighter.xp) + ' / ' + str(level_up_xp) +
                       '\n\nMaximum HP: ' + str(player.fighter.max_hp) +
                    '\nAttack: ' + str(player.fighter.power) + '\nDefense: ' + str(player.fighter.defense), CHARACTER_SCREEN_WIDTH)

            if key == terminal.TK_SHIFT:
                key = terminal.read()
                if key == terminal.TK_PERIOD:
                    print 'done'
                #go down stairs, if the player is on them
                if stairs.x == player.x and stairs.y == player.y:
                    next_level()

            if key == terminal.TK_BACKSPACE:
                debug()

            return 'didnt-take-turn'


    return 'didnt-take-turn'


def save_game():
    #open a new empty shelve (possibly overwriting an old one) to write the game data
    file = shelve.open('savegame', 'n')
    file['map'] = map
    file['objects'] = objects
    file['player_index'] = objects.index(player)  #index of player in objects list
    file['stairs_index'] = objects.index(stairs)  #same for the stairs
    file['inventory'] = inventory
    file['game_msgs'] = game_msgs
    file['game_state'] = game_state
    file['dungeon_level'] = dungeon_level
    file.close()

def load_game():
    #open the previously saved shelve and load the game data
    global map, objects, player, stairs, inventory, game_msgs, game_state, dungeon_level

    file = shelve.open('savegame', 'r')
    map = file['map']
    objects = file['objects']
    player = objects[file['player_index']]  #get index of player in objects list and access it
    stairs = objects[file['stairs_index']]  #same for the stairs
    inventory = file['inventory']
    game_msgs = file['game_msgs']
    game_state = file['game_state']
    dungeon_level = file['dungeon_level']
    file.close()
    terminal.clear()
    initialize_fov()

def new_game():
    global player, inventory, game_msgs, game_state, dungeon_level
    #create player object
    fighter_component = Fighter(hp=30, defense=2, power=5, xp=0, death_function=player_death)
    player = Object(0, 0, 17, 'player', blocks=True, fighter=fighter_component)

    #set player starting level
    player.level = 1

    #generate map
    dungeon_level = 1
    make_map()
    initialize_fov()

    game_state = 'playing'
    #create inventory list
    inventory = []
    #create the list of game messages and their colors, starts empty
    game_msgs = []
    #a warm welcoming message!
    message('Welcome foul stranger to the Tomb of Despair! Prepare to do noble battle with the hordes of snakes '
        'and blobs! And prepare for the ultimate sacrifice, to dent your axe with the blood of elves!', "#FF0000")
    #starting equipment: a dagger
    equipment_component = Equipment(slot='right hand', power_bonus=2)
    obj = Object(0, 0, '?', 'dagger', equipment=equipment_component)
    inventory.append(obj)
    equipment_component.equip()
    obj.always_visible = True


def initialize_fov():
    global fov_recompute, fov_map
    fov_recompute = True
    #create the DOV map, according to generated map
    fov_map = libtcod.map_new(MAP_WIDTH, MAP_HEIGHT)
    for y in range(MAP_HEIGHT):
        for x in range(MAP_WIDTH):
            libtcod.map_set_properties(fov_map, x, y, not map[x][y].block_sight, not map[x][y].blocked)

def play_game():
    player_action = None

    #main loop
    while True:
        render_all()
        check_level_up()

        #terminal.layer(5)
        #terminal.put(10, 10, 24) #place individual tile slime: 160:, troll=162: .
        terminal.refresh()

        for object in objects:
            object.clear()

        player_action = handle_keys()
        if player_action == 'exit':
            save_game()
            break

        #let monsters take their turn
        if game_state == 'playing' and player_action != 'didnt-take-turn':
            for object in objects:
                if object.ai:
                    object.ai.take_turn()

def main_menu():

    while True:
        terminal.clear()
        for y in range(50):
            for x in range(80):
                terminal.color(1678238975 - x)
                terminal.put(x, y, 20)

        terminal.refresh()

        #show the game's title and some credits
        terminal.layer(6)
        terminal.color(4294967103)
        terminal.print_(SCREEN_WIDTH/2 - 13, SCREEN_HEIGHT/2-4, 'TOMBS OF THE ANCIENT KINGS')
        terminal.print_(SCREEN_WIDTH/2, SCREEN_HEIGHT-2, 'By Tommy Z')

        #show options and wait for player's choice
        choice = menu('', ['Play a new game', 'Continue last game', 'Save & Quit'], 24)

        if choice == 0:  #new game
            terminal.clear()
            new_game()
            play_game()
        if choice == 1:  #load last game
            try:
                load_game()
            except:
                msgbox('\n No saved game to load.\n', 24)
                continue
            play_game()
        elif choice == 2:  #quit
            terminal.close()
            break


def debug():
    terminal.put(10, 10, 133) #
    terminal.print_(11, 10, ': dark wall') # dark wall
    terminal.put(10, 11, 130) #
    terminal.print_(11, 11, ': light wall') # light wall
    terminal.put(10, 12, 136) #
    terminal.print_(11, 12, ': dark ground') # dark ground
    terminal.put(10, 13, 137) #
    terminal.print_(11, 13, ': light ground') # light ground
    #terminal.layer(2)
    terminal.put(10, 10, 389)



#############################
# Initialisation            #
#############################

terminal.open()

# !! set this \/ for ng
terminal.set("window: size=80x50; window.title='hello world'; font: tilesets/NEW16_4.png, size=16x16; input: filter=[keyboard, mouse_left]")


#############################
# Main Loop                 #
#############################

main_menu()
#new_game()
#play_game()

