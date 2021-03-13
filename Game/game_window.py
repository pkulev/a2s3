#thou shall be file where I do everything related to game rendering
#effectively "Main", ye

import logging
from direct.showbase.ShowBase import ShowBase
from panda3d.core import WindowProperties
from direct.gui.OnscreenText import OnscreenText, TextNode
from time import time
from Game import entity_2D, map_loader, config, assets_loader

log = logging.getLogger(__name__)

ENTITY_LAYER = config.ENTITY_LAYER
MAX_ENEMY_COUNT = config.MAX_ENEMY_COUNT
ENEMY_SPAWN_TIME = config.ENEMY_SPAWN_TIME
DEAD_CLEANUP_TIME = 5
#pause between calls to per-node's damage function. Making it anyhow lower will
#reintroduce the bug with multiple damage calls occuring during single frame
COLLISION_CHECK_PAUSE = 0.2
DEFAULT_SCORE_VALUE = 0
DEFAULT_SCORE_MULTIPLIER = 1
MAX_SCORE_MULTIPLIER = 5 #maybe just make it MULTIPLIER_INCREASE_STEP*10 ?
MULTIPLIER_INCREASE_STEP = 0.5

class Main(ShowBase):
    def __init__(self):
        log.debug("Setting up the window")
        ShowBase.__init__(self)

        #disabling mouse to dont mess with camera
        self.disable_mouse()

        log.debug("Loading assets")
        config.ASSETS = assets_loader.load_assets()
        self.assets = config.ASSETS

        log.debug("Configuring game's window")
        #setting up resolution
        screen_info = base.pipe.getDisplayInformation()
        #this is ugly, but it works, for now
        #basically we are ensuring that custom window's resolution isnt bigger
        #than screen size. And if yes - using default resolution instead

        #idk why, but these require at least something to display max available window size
        max_res = (screen_info.getDisplayModeWidth(0),
                   screen_info.getDisplayModeHeight(0))

        for cr, mr in zip(config.WINDOW_SIZE, max_res):
            if cr > mr:
                log.warning("Requested resolution is bigger than screen size, "
                            "will use defaults instead")
                resolution = config.DEFAULT_WINDOW_SIZE
                break
            else:
                resolution = config.WINDOW_SIZE

        window_settings = WindowProperties()
        window_settings.set_size(resolution)

        #ensuring that window cant be resized by dragging its borders around
        window_settings.set_fixed_size(True)
        #toggling fullscreen/windowed mode
        window_settings.set_fullscreen(config.FULLSCREEN)
        #setting window's title
        window_settings.set_title(config.GAME_NAME)
        #applying settings to our window
        self.win.request_properties(window_settings)
        log.debug(f"Resolution has been set to {resolution}")

        #change background color to black
        self.win.set_clear_color((0,0,0,1))

        log.debug("Generating the map")
        map_loader.flat_map_generator(self.assets['sprites']['floor'],
                                      size = config.MAP_SIZE)
        #taking advantage of enemies not colliding with map borders and spawning
        #them outside of the map's corners. Idk about the numbers and if they should
        #be related to sprite size in anyway. Basically anything will do for now
        #later we will add some "fog of war"-like effect above map's borders, so
        #enemies spawning on these positions will seem more natural
        self.enemy_spawnpoints = [((config.MAP_SIZE[0]/2)+32, (config.MAP_SIZE[1]/2)+32),
                                  ((-config.MAP_SIZE[0]/2)-32, (-config.MAP_SIZE[1]/2)-32),
                                  ((config.MAP_SIZE[0]/2)+32, (-config.MAP_SIZE[1]/2)-32),
                                  ((-config.MAP_SIZE[0]/2)-32, (config.MAP_SIZE[1]/2)+32)]

        log.debug("Initializing player")
        #character's position should always render on ENTITY_LAYER
        #setting this lower may cause glitches, as below lies the FLOOR_LAYER
        #hitbox is adjusted to match our current sprites. In case of change - will
        #need to tweak it manually
        self.player = entity_2D.Player("player", position = (0, 0, ENTITY_LAYER),
                                       hitbox_size = 6)

        log.debug("Initializing enemy spawner")
        self.enemy_spawn_timer = ENEMY_SPAWN_TIME

        #these will be our dictionaries to store enemies and projectiles to reffer to
        self.enemies = []
        self.projectiles = []
        #and this is amount of time, per which dead objects get removed from these
        self.cleanup_timer = DEAD_CLEANUP_TIME

        #variable for enemy spawner to make debugging process easier. Basically,
        #its meant to increase with each new enemy and never reset until game over.
        #this can also be potentially used for some highscore stats
        self.enemy_id = 0

        log.debug("Initializing collision processors")
        self.cTrav = config.CTRAV
        self.pusher = config.PUSHER
        #avoiding the issue with entities falling under the floor on some collisions
        self.pusher.set_horizontal(True)

        #this way we are basically naming the events we want to track, so these
        #will be possible to handle via self.accept and do the stuff accordingly
        #"in" is what happens when one object start colliding with another
        #"again" is if object continue to collide with another
        #"out" is when objects stop colliding
        self.pusher.addInPattern('%fn-into-%in')
        self.pusher.addAgainPattern('%fn-again-%in')
        #we dont need this one there
        #self.pusher.addOutPattern('%fn-out-%in')

        #showing all collisions on the scene (e.g visible to render)
        #this is better than manually doing collision.show() for each object
        if config.SHOW_COLLISIONS:
            self.cTrav.show_collisions(render)

        #because in our current version we need to deal damage to player on collide
        #regardless who started collided with whom - tracking all these events to
        #run function that deals damage to player. I have no idea why, but passing
        #things arguments to "damage target" function directly, like we did with
        #controls, didnt work. So we are using kind of "proxy function" to do that
        self.accept('player-into-enemy', self.damage_player)
        self.accept('enemy-into-player', self.damage_player)
        self.accept('player-again-enemy', self.damage_player)
        self.accept('enemy-again-player', self.damage_player)

        #also tracking collisions of enemy with player's attack projectile
        self.accept('attack-into-enemy', self.damage_enemy)
        self.accept('enemy-into-attack', self.damage_enemy)
        self.accept('attack-again-enemy', self.damage_enemy)
        self.accept('enemy-again-attack', self.damage_enemy)

        #this will set camera to be right above card.
        #changing first value will rotate the floor
        #changing second - change the angle from which we see floor
        #the last one is zoom. Negative values flip the screen
        #maybe I should add ability to change camera's angle, at some point?
        self.camera.set_pos(0, 700, 500)
        self.camera.look_at(0, 0, 0)
        #making camera always follow character
        self.camera.reparent_to(self.player.object)

        log.debug(f"Setting up background music")
        #setting volume like that, so it should apply to all music tracks
        music_mgr = base.musicManager
        music_mgr.set_volume(config.MUSIC_VOLUME)
        #same goes for sfx manager, which is a separate thing
        sfx_mgr = base.sfxManagerList[0]
        sfx_mgr.set_volume(config.SFX_VOLUME)
        menu_theme = self.assets['music']['menu_theme']
        menu_theme.set_loop(True)
        menu_theme.play()

        log.debug(f"Initializing UI")
        #turning on fps meter, in case its enabled in settings
        base.setFrameRateMeter(config.FPS_METER)
        #create white-colored text with player's hp above player's head
        #TODO: move it to top left, add some image on background
        self.player_hp_ui = OnscreenText(text = f"{self.player.stats['hp']}",
                                         pos = (0, 0.01),
                                         scale = 0.05,
                                         fg = (1,1,1,1),
                                         mayChange = True)

        #score is, well, a thing that increase each time you hit/kill enemy.
        #in future there may be ability to spend it on some powerups, but for
        #now its only there for future leaderboards
        self.score = 0
        self.score_ui = OnscreenText(text = f"Score: {self.score}",
                                     pos = (-1.7, 0.9),
                                     #alignment side may look non-obvious, depending
                                     #on position and text it applies to
                                     align = TextNode.ALeft,
                                     scale = 0.05,
                                     fg = (1,1,1,1),
                                     mayChange = True)

        #score multiplier is a thing, that, well, increase amount of score gained
        #for each action. For now, the idea is following: for each 10 hits to enemy
        #without taking damage, you increase it by MULTIPLIER_INCREASE_STEP. Getting
        #damage resets it to default value (which is 1). It may be good idea to
        #make it instead increase if player is using different skills in order
        #to kill enemies (and not repeating autoattack). But for now thats about it
        self.score_multiplier = 1
        #as said above - when below reaches 9 (coz count from 0), multiplier increase
        self.multiplier_increase_counter = 0
        #visually it should be below score itself... I think?
        self.score_multiplier_ui = OnscreenText(text = f"Multiplier: {self.score_multiplier}",
                                                pos = (-1.7, 0.85),
                                                align = TextNode.ALeft,
                                                scale = 0.05,
                                                fg = (1,1,1,1),
                                                mayChange = True)

        #its variable and not len of enemy list, coz it doesnt clean up right away
        self.enemy_amount = 0
        #this one should be displayed on right... I think?
        self.enemy_amount_ui = OnscreenText(text = f"Enemies Left: {self.enemy_amount}",
                                            pos = (1.7, 0.85),
                                            align = TextNode.ARight,
                                            scale = 0.05,
                                            fg = (1,1,1,1),
                                            mayChange = True)

        log.debug(f"Initializing controls handler")
        #task manager is function that runs on background each frame and execute
        #whatever functions are attached to it
        self.task_mgr.add(self.spawn_enemies, "enemy spawner")
        self.task_mgr.add(self.remove_dead, "remove dead")

        #dictionary that stores default state of keys
        self.controls_status = {"move_up": False, "move_down": False,
                                "move_left": False, "move_right": False, "attack": False}

        #.accept() is method that track panda's events and perform certain functions
        #once these occur. "-up" prefix means key has been released
        self.accept(config.CONTROLS['move_up'],
                    self.change_key_state, ["move_up", True])
        self.accept(f"{config.CONTROLS['move_up']}-up",
                    self.change_key_state, ["move_up", False])
        self.accept(config.CONTROLS['move_down'],
                    self.change_key_state, ["move_down", True])
        self.accept(f"{config.CONTROLS['move_down']}-up",
                    self.change_key_state, ["move_down", False])
        self.accept(config.CONTROLS['move_left'],
                    self.change_key_state, ["move_left", True])
        self.accept(f"{config.CONTROLS['move_left']}-up",
                    self.change_key_state, ["move_left", False])
        self.accept(config.CONTROLS['move_right'],
                    self.change_key_state, ["move_right", True])
        self.accept(f"{config.CONTROLS['move_right']}-up",
                    self.change_key_state, ["move_right", False])
        self.accept(config.CONTROLS['attack'],
                    self.change_key_state, ["attack", True])
        self.accept(f"{config.CONTROLS['attack']}-up",
                    self.change_key_state, ["attack", False])

    def change_key_state(self, key_name, key_status):
        '''Receive str(key_name) and bool(key_status).
        Change key_status of related key in self.controls_status'''
        self.controls_status[key_name] = key_status
        log.debug(f"{key_name} has been set to {key_status}")

    def spawn_enemies(self, event):
        '''If amount of enemies is less than MAX_ENEMY_COUNT: spawns enemy each
        ENEMY_SPAWN_TIME seconds. Meant to be ran as taskmanager routine'''
        #safety check to dont spawn more enemies if player is dead
        if not self.player.object:
            return event.cont

        #this clock runs on background and updates each frame
        #e.g 'dt' will always be the amount of time passed since last frame
        #and no, "from time import sleep" wont fit for this - game will freeze
        #because in its core, task manager isnt like multithreading but async
        dt = globalClock.get_dt()

        #similar method can also be used for skill cooldowns, probably anims stuff
        self.enemy_spawn_timer -= dt
        if self.enemy_spawn_timer <= 0:
            log.debug("Checking if we can spawn enemy")
            self.enemy_spawn_timer = ENEMY_SPAWN_TIME
            if self.enemy_amount < MAX_ENEMY_COUNT:
                log.debug("Initializing enemy")
                #determining the distance to player from each spawnpoint and
                #spawning enemies on the farest. Depending on map type, it may be
                #not best behavior. But for now it will do, as it solves the issue
                #with enemies spawning on top of player if player is sitting at
                #map's very corner. #TODO: add more "pick spawnpoint" variations
                player_position = self.player.object.get_pos()

                spawns = []
                for spawnpoint in self.enemy_spawnpoints:
                    spawn = *spawnpoint, ENTITY_LAYER
                    vec_to_player = player_position - spawn
                    vec_length = vec_to_player.length()
                    spawns.append((vec_length, spawn))

                #sort spawns by the very first number in tuple (which is lengh)
                spawns.sort()

                #picking up the spawn from last list's entry (e.g the farest from player)
                spawn_position = spawns[-1][1]
                log.debug(f"Spawning enemy on {spawn_position}")
                enemy = entity_2D.Enemy("enemy", position = spawn_position,
                                        hitbox_size = 12)
                enemy.id = self.enemy_id
                enemy.object.set_python_tag("id", enemy.id)
                self.enemy_id += 1
                self.update_enemy_counter(1)
                self.enemies.append(enemy)
                log.debug(f"There are currently {self.enemy_amount} enemies on screen")

        return event.cont

    def remove_dead(self, event):
        '''Designed to run as taskmanager routine. Each self.cleanup_timer secs,
        remove all dead enemies and projectiles from related lists'''
        #shutdown the task if player has died, coz there is no point
        if self.player.dead:
            return

        dt = globalClock.get_dt()
        self.cleanup_timer -= dt
        if self.cleanup_timer > 0:
            return event.cont

        self.cleanup_timer = DEAD_CLEANUP_TIME
        log.debug(f"Cleaning up dead entities from memory")
        for entity in self.enemies:
            if entity.dead:
                self.enemies.remove(entity)

        for entity in self.projectiles:
            if entity.dead:
                self.projectiles.remove(entity)

        return event.cont

    def damage_player(self, entry):
        '''Deals damage to player when it collides with some object that should
        hurt. Intended to be used from self.accept event handler'''
        hit = entry.get_from_node_path()
        tar = entry.get_into_node_path()

        #log.debug(f"{hit} collides with {tar}")

        #we are using "get_net_python_tag" over just "get_tag", coz this one will
        #search for whole tree, instead of just selected node. And since the node
        #we get via methods above is not the same as node we want - this is kind
        #of what we should use
        hit_name = hit.get_net_python_tag("name")
        tar_name = tar.get_net_python_tag("name")

        #workaround for "None Type" exception that rarely occurs if one of colliding
        #nodes has died the very second it needs to be used in another collision
        if not hit_name or not tar_name:
            log.warning("One of targets is dead, no damage will be calculated")
            return

        #bcuz we will damage player anyway - ensuring that object used as damage
        #source is not the player but whatever else it collides with
        if hit_name == "enemy":
            dmg_source = hit
            target = tar
        else:
            dmg_source = tar
            target = hit

        #this is a workaround for issue caused by multiple collisions occuring
        #at single frame, so damage check function cant keep up with it. Basically,
        #we allow new target's collisions to only trigger damage function each
        #0.2 seconds. It may be good idea to abandon this thing in future in favor
        #of something like collisionhandlerqueue, but for now it works
        tct = target.get_net_python_tag("last_collision_time")
        x = time()
        if x - tct < COLLISION_CHECK_PAUSE:
            return

        target.set_python_tag("last_collision_time", x)

        ds = dmg_source.get_net_python_tag("stats")
        dmg = ds['dmg']
        dmgfunc = target.get_net_python_tag("get_damage")
        dmgfunc(dmg)

    def damage_enemy(self, entry):
        #nasty placeholder to make enemy receive damage from collision with player's
        #projectile. Will need to rework it and merge with "damage_player" into
        #something like "damage_target" or idk
        hit = entry.get_from_node_path()
        tar = entry.get_into_node_path()

        #log.debug(f"{hit} collides with {tar}")

        hit_name = hit.get_net_python_tag("name")
        tar_name = tar.get_net_python_tag("name")

        if not hit_name or not tar_name:
            log.warning("One of targets is dead, no damage will be calculated")
            return

        if hit_name == "attack":
            dmg_source = hit
            target = tar
        else:
            dmg_source = tar
            target = hit

        tct = target.get_net_python_tag("last_collision_time")
        x = time()
        if x - tct < COLLISION_CHECK_PAUSE:
            return

        target.set_python_tag("last_collision_time", x)

        dmg = dmg_source.get_net_python_tag("damage")
        dmgfunc = target.get_net_python_tag("get_damage")

        target_name = target.get_net_python_tag('name')
        target_id = target.get_net_python_tag('id')
        log.debug(f"Attempting to deal damage to {target_name} ({target_id})")
        dmgfunc(dmg)

    def update_score(self, amount):
        '''Update score variable and displayed score amount by int(amount * self.score_multiplier)'''
        increase = amount*self.score_multiplier
        self.score += int(increase)
        self.score_ui.setText(f"Score: {self.score}")
        log.debug(f"Increased score to {self.score}")

    def increase_score_multiplier(self):
        '''If self.score_multiplier is less than MAX_SCORE_MULTIPLIER - increase
        self.multiplier_increase_counter by 1. If it reaches 9 - increase
        self.score_multiplier by MULTIPLIER_INCREASE_STEP'''
        if self.score_multiplier >= MAX_SCORE_MULTIPLIER:
            log.debug("Already have max score multiplier, wont increase")
            return

        self.multiplier_increase_counter += 1
        if self.multiplier_increase_counter < 10:
            return

        self.multiplier_increase_counter = 0
        self.score_multiplier += MULTIPLIER_INCREASE_STEP
        self.score_multiplier_ui.setText(f"Multiplier: {self.score_multiplier}")
        log.debug(f"Increased score multiplier to {self.score_multiplier}")

    def reset_score_multiplier(self):
        '''Reset score multiplayer to defaults'''
        self.score_multiplier = DEFAULT_SCORE_MULTIPLIER
        self.multiplier_increase_counter = 0
        self.score_multiplier_ui.setText(f"Multiplier: {self.score_multiplier}")
        log.debug(f"Reset score multiplier to {self.score_multiplier}")

    def update_enemy_counter(self, amount):
        '''Update self.enemy_amount by int amount. By default its +'''
        self.enemy_amount += amount
        self.enemy_amount_ui.setText(f"Enemies Left: {self.enemy_amount}")
        log.debug(f"Enemy amount has been set to {self.enemy_amount}")
