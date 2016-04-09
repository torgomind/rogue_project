# Notes:
# Up to section "Using Items"
# http://www.roguebasin.com/index.php?title=Complete_Roguelike_Tutorial,_using_python%2Blibtcod,_part_8
# BGRA/ARGB conversion: 0xAARRGGBB @ http://www.binaryhexconverter.com/decimal-to-hex-converter

#import
import PyBearLibTerminal as terminal
import libtcodpy as libtcod
import math
import textwrap

#size of window
SCREEN_WIDTH = 80
SCREEN_HEIGHT = 50

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

#dungeon gen settings
ROOM_MAX_SIZE = 10
ROOM_MIN_SIZE = 6
MAX_ROOMS = 30
MAX_ROOM_MONSTERS = 3
MAX_ROOM_ITEMS = 2

#spell values
HEAL_AMOUNT = 4

MAP_WIDTH = 80
MAP_HEIGHT = 43

FOV_ALGO = 0  #default FOV algorithm
FOV_LIGHT_WALLS = True  #light walls or not
TORCH_RADIUS = 10

tile_dark_wall = 14
tile_light_wall = 13
tile_dark_ground = 0
tile_light_ground = 1

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
    def __init__(self, x, y, char, name, blocks=False, fighter=None, ai=None, item=None):
        self.x = x
        self.y = y
        self.char = char
        self.name = name
        self.blocks = blocks

        self.fighter = fighter
        if self.fighter:
            self.fighter.owner = self

        self.ai = ai
        if self.ai:
            self.ai.owner = self

        self.item = item
        if self.item: #let the item know its owner
            self.item.owner = self

    def move(self, dx, dy):
        #move by the given amount
        if not is_blocked(self.x + dx, self.y + dy):
            self.x += dx
            self.y += dy

    def move_towards(self, target_x, target_y):
        #vector from this object to the target, and distance
        dx = target_x - self.x
        dy = target_y - self.y
        distance = math.sqrt(dx ** 2 + dy ** 2)

        #normalize it to length 1 (preserving direction), then round it and
        #convert to integer so the movement is restricted to the map grid
        dx = int(round(dx / distance))
        dy = int(round(dy / distance))
        self.move(dx, dy)

    def distance_to(self, other):
        #return the distance to another object
        dx = other.x - self.x
        dy = other.y - self.y
        return math.sqrt(dx ** 2 + dy ** 2)

    def send_to_back(self):
        #make this object be drawn first, so all others appear above it if they're in the same tile.
        global objects
        objects.remove(self)
        objects.insert(0, self)

    def draw(self):
        #set the color and then draw the character that represents this object at its position
        if libtcod.map_is_in_fov(fov_map, self.x, self.y):
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

class Fighter:
    def __init__(self, hp, defense, power, death_function=None):
        self.max_hp = hp
        self.hp = hp
        self.defense = defense
        self.power = power
        self.death_function = death_function

    def attack(self, target):
        #a simple formula for attack damage
        damage = self.power - target.fighter.defense

        if damage > 0:
            #make the target take some damage
            message(self.owner.name.capitalize() + ' attacks ' + target.name + ' for ' + str(damage) + ' hit points.')
            target.fighter.take_damage(damage)
        else:
            message(self.owner.name.capitalize() + ' attacks ' + target.name + ' but it has no effect!')

    def take_damage(self, damage):
        #apply damage if possible
        if damage > 0:
            self.hp -= damage

            #check for death. if there's a death function, call it
            if self.hp <= 0:
                function = self.death_function
                if function is not None:
                    function(self.owner)

class BasicMonster:
    #AI for a basic monster.
    def take_turn(self):
        #a basic monster takes its turn. if you can see it, it can see you
        monster = self.owner
        if libtcod.map_is_in_fov(fov_map, monster.x, monster.y):

            #move towards player if far away
            if monster.distance_to(player) >= 2:
                monster.move_towards(player.x, player.y)

            #close enough, attack! (if the player is still alive.)
            elif player.fighter.hp > 0:
                monster.fighter.attack(player)

class Item:
    #an item that can be picked up and used.
    def __init__(self, use_function=None):
        self.use_function = use_function

    def pick_up(self):
        #add to the player's inventory and remove from the map
        if len(inventory) >= 26:
            message('Your inventory is full, cannot pick up ' + self.owner.name + '.', 4294901760)
        else:
            inventory.append(self.owner)
            objects.remove(self.owner)
            message('You picked up a ' + self.owner.name + '!', 4278255360)

    def use(self):
        #just call the "use_function" if it is defined
        if self.use_function is None:
            message('The ' + self.owner.name + ' cannot be used.')
        else:
            if self.use_function() != 'cancelled':
                inventory.remove(self.owner)  #destroy after use, unless it was cancelled for some reason

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
    global map, player

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

def place_objects(room):
    #choose random number of monsters
    num_monsters = libtcod.random_get_int(0, 0, MAX_ROOM_MONSTERS)

    for i in range(num_monsters):
        #choose random spot for this monster
        x = libtcod.random_get_int(0, room.x1+1, room.x2-1)
        y = libtcod.random_get_int(0, room.y1+1, room.y2-1)

        #only place it if the tile is not blocked
        if not is_blocked(x, y):
            if libtcod.random_get_int(0, 0, 100) < 80:  #80% chance of getting an orc
                #create an orc
                fighter_component = Fighter(hp=10, defense=0, power=3, death_function=monster_death)
                ai_component = BasicMonster()

                monster = Object(x, y, 'o', 'orc', blocks=True, fighter=fighter_component, ai=ai_component)
            else:
                #create a troll
                fighter_component = Fighter(hp=16, defense=1, power=4, death_function=monster_death)
                ai_component = BasicMonster()

                monster = Object(x, y, 'T', 'troll', blocks=True, fighter=fighter_component, ai=ai_component)

            objects.append(monster)

    #choose random number of items
    num_items = libtcod.random_get_int(0, 0, MAX_ROOM_ITEMS)

    for i in range(num_items):
        #choose random spot for this item
        x = libtcod.random_get_int(0, room.x1+1, room.x2-1)
        y = libtcod.random_get_int(0, room.y1+1, room.y2-1)

        #only place it if the tile is not blocked
        if not is_blocked(x, y):
            #create a healing potion
            item_component = Item(use_function=cast_heal)

            item = Object(x, y, '!', 'healing potion', item=item_component)

            objects.append(item)
            item.send_to_back()  #items appear below other objects

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

def render_all():
    global fov_map, color_dark_wall, color_light_wall
    global color_dark_ground, color_light_ground
    global fov_recompute

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

    #show the player's stats
    render_bar(1, 1, BAR_WIDTH, 'HP', player.fighter.hp, player.fighter.max_hp, 4294917951, 4286513152)

    #display names of objects under the mouse
    #still on layer 6 ***** (text layer)
    terminal.print_(1, PANEL_Y, get_names_under_mouse())

def get_names_under_mouse():
    global mouse
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

def message(new_msg, color = "#FFFFFF"):
    #split the message if necessary, among multiple lines
    new_msg_lines = textwrap.wrap(new_msg, MSG_WIDTH)

    for line in new_msg_lines:
        #if the buffer is full, remove the first line to make room for the new one
        if len(game_msgs) == MSG_HEIGHT:
            del game_msgs[0]

        #add the new line as a tuple, with the text and the color
        game_msgs.append( (line, color) )

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

def menu(header, options, width):
    if len(options) > 26: raise ValueError('Cannot have a menu with more than 26 options.')
    #calculate total height for the header (after auto-wrap) and one line per option
    #header_height = libtcod.console_get_height_rect(con, 0, 0, width, SCREEN_HEIGHT, header)!!!
    '''
    if len(header) < width:
        header_height = 1
    else:
        header_height = int(math.ceil(float(len(header)) / float(width)))
    '''
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
    key = terminal.read() #!!! this might not halt the operations

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
        options = [item.name for item in inventory]

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

            if key == terminal.TK_BACKSPACE:
                for item in objects:
                    if item.item:
                        print item.blocks

            return 'didnt-take-turn'


    return 'didnt-take-turn'

def player_death(player):
    #the game ended!
    global game_state
    message('You died!', 4294901760)
    game_state = 'dead'

    #for added effect, transform the player into a corpse!
    player.char = '%'

def monster_death(monster):
    #transform it into a nasty corpse! it doesn't block, can't be
    #attacked and doesn't move
    message(monster.name.capitalize() + ' is dead!', 4294934272)
    monster.char = '%'
    monster.blocks = False
    monster.fighter = None
    monster.ai = None
    monster.name = 'remains of ' + monster.name
    monster.send_to_back()

def cast_heal():
    #heal the player
    if player.fighter.hp == player.fighter.max_hp:
        message('You are already at full health.', libtcod.red)
        return 'cancelled'

    message('Your wounds start to feel better!', libtcod.light_violet)
    player.fighter.heal(HEAL_AMOUNT)

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
terminal.set("window: size=80x50; window.title='hello world'; font: tilesets/NEW16_4.png, size=16x16; input: filter=[keyboard, mouse_left]")

#create player object
fighter_component = Fighter(hp=30, defense=2, power=5, death_function=player_death)
player = Object(0, 0, 17, 'player', blocks=True, fighter=fighter_component)

#player = Object(0, 0, 17, 'player', blocks=True)
#npc = Object(SCREEN_WIDTH/2 - 5, SCREEN_HEIGHT/2, 12)
objects = [player]

make_map()

#create the DOV map, according to generated map
fov_map = libtcod.map_new(MAP_WIDTH, MAP_HEIGHT)
for y in range(MAP_HEIGHT):
    for x in range(MAP_WIDTH):
        libtcod.map_set_properties(fov_map, x, y, not map[x][y].block_sight, not map[x][y].blocked)


fov_recompute = True
game_state = 'playing'
player_action = None

#create inventory list
inventory = []
#create the list of game messages and their colors, starts empty
game_msgs = []
#a warm welcoming message!
message('Welcome stranger! Prepare to perish in the Tombs of the Ancient Kings.', "#FF0000")

#############################
# Main Loop                 #
#############################

while True:

    render_all()

    #terminal.layer(5)
    #terminal.put(10, 10, 20) #place individual tile
    terminal.refresh()

    for object in objects:
        object.clear()

    player_action = handle_keys()
    if player_action == 'exit':
        terminal.close()
        break

    #let monsters take their turn
    if game_state == 'playing' and player_action != 'didnt-take-turn':
        for object in objects:
            if object.ai:
                object.ai.take_turn()

