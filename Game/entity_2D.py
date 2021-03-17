import logging
from panda3d.core import (CardMaker, TextureStage, CollisionSphere, CollisionNode,
                          Texture, BitMask32, Point3, Plane, Vec2)
from Game import config

log = logging.getLogger(__name__)

#module where I specify character and other 2d objects

STATS = config.STATS
SKILLS = config.SKILLS
ANIMS = config.ANIMS
DEFAULT_SPRITE_SIZE = config.DEFAULT_SPRITE_SIZE
DEFAULT_ANIMATIONS_SPEED = 0.1

ENEMY_COLLISION_MASK = config.ENEMY_COLLISION_MASK
#ENEMY_PROJECTILE_COLLISION_MASK = config.ENEMY_PROJECTILE_COLLISION_MASK
PLAYER_COLLISION_MASK = config.PLAYER_COLLISION_MASK
PLAYER_PROJECTILE_COLLISION_MASK = config.PLAYER_PROJECTILE_COLLISION_MASK

HIT_SCORE = 10
KILL_SCORE = 15

#maybe move this to some other module? idk
#also it would be good idea to make spritesheets not on per-character, but on
#per-image base. But this would require some standard sprite size to be set
def cut_spritesheet(spritesheet, size):
    '''Receive str(path to spritesheet) and tuple of sprite size = (x, y). Based
    on sprite size and size of spritesheet, make list of offsets for each sprite
    on the sheet, which can later be used to select, some particular sprite to use.
    Then returns said list to function that requested it'''

    #todo: move this thing to assets loader

    #for now, this has 2 limitations:
    # 1. Spritesheet HAS TO DIVIDE TO PROVIDED SPRITE SIZE WITHOUT REMAINDER. If
    #it doesnt cut to perfect sprites, you will get strange results during using
    #some of these sprites.
    # 2. There should be EVEN amount of sprite rows and columns. Otherwise - see
    #above. This is because of limitation of set_tex_offset() and set_tex_scale()
    #functions, both of which operate with floats between 0 and 1 to determine the
    #position. And, as you can guess - you cant divide 1 to odd number perfectly.
    #I assume, its possible to fix both of these. But right now I have no idea how
    #As for first - maybe cut garbage data with PNMimage module, before processing?

    log.debug(f"Attempting to cut spritesheet into sprites of {size} size")
    size_x, size_y = size

    #Determining amount of sprites in each row
    spritesheet_x = spritesheet.get_orig_file_x_size()
    spritesheet_y = spritesheet.get_orig_file_y_size()

    sprite_columns = int(spritesheet_x / size_x)
    sprite_rows = int(spritesheet_y / size_y)
    log.debug(f"Our sheet has {sprite_columns}x{sprite_rows} sprites")

    #idk if these should be flipped - its 3 am
    #this may backfire on values bigger than one... but it should never happen
    horizontal_offset_step = 1/sprite_columns
    vertical_offset_step = 1/sprite_rows
    log.debug(f"Offset steps are {horizontal_offset_step, vertical_offset_step}")

    offsets = []

    #dont ask questions, "it just works".
    #Basically, the thing is: originally, I did the following:
    #for row in range(0, sprite_rows):
    #BUT, this made offsets list start from bottom layer to top, which worked but
    #broke the whole "from top left to bottom right" style of image processing.
    #So I went for this "kinda hacky" solution. It works on 2x2 sheet, idk about
    #anything bigger than that
    for row in range(sprite_rows-1, -1, -1):
        log.debug(f"Processing row {row}")
        #workaround to add negative values without breaking the order. This wont
        #work if texture wrap mode isnt set to mirror. But otherwise it does
        row_dict = []
        mirrored_dict = []
        for column in range(0, sprite_columns):
            log.debug(f"Processing column {column}")
            horizontal_offset = column * horizontal_offset_step
            vertical_offset = row * vertical_offset_step
            log.debug(f"Got offsets: {horizontal_offset, vertical_offset}")
            row_dict.append((horizontal_offset, vertical_offset))
            #adding +1, coz of how texture wrap mode works
            mirrored_dict.append((1+horizontal_offset, vertical_offset))
        #reversing the order of items in mirrored dict, because otherwise it
        #would count items from right side of mirrored image to left
        mirrored_dict.reverse()
        offsets.extend(row_dict)
        offsets.extend(mirrored_dict)
    log.debug(f"Spritesheet contain following offsets: {offsets}")

    #maybe rename it into something more convenient?
    sprites = {}
    sprites['offset_steps'] = (horizontal_offset_step, vertical_offset_step)
    sprites['offsets'] = offsets

    log.debug(f"Got following data: {sprites}, returning")

    return sprites

class Entity2D:
    '''
    Main class, dedicated to creation of collideable 2D objects.
    '''
    def __init__(self, name, spritesheet = None, sprite_size = None,
                 hitbox_size = None, collision_mask = None, position = None,
                 animations_speed = None):
        log.debug(f"Initializing {name} object")

        if not animations_speed:
            animations_speed = DEFAULT_ANIMATIONS_SPEED
        self.animations_timer = animations_speed
        self.animations_speed = animations_speed

        if not sprite_size:
            sprite_size = DEFAULT_SPRITE_SIZE

        if not spritesheet:
            #I cant link assets above, coz their default value is None
            texture = base.assets.sprite[name]
        else:
            texture = base.assets.sprite[spritesheet]

        size_x, size_y = sprite_size
        log.debug(f"{name}'s size has been set to {size_x}x{size_y}")

        #the magic that allows textures to be mirrored. With that thing being
        #there, its possible to use values in range 1-2 to get versions of sprites
        #that will face the opposite direction, removing the requirement to draw
        #them with hands. Without thing thing being there, 0 and 1 will be threated
        #as same coordinates, coz "out of box" texture wrap mode is "repeat"
        texture.set_wrap_u(Texture.WM_mirror)
        texture.set_wrap_v(Texture.WM_mirror)
        sprite_data = cut_spritesheet(texture, sprite_size)

        horizontal_scale, vertical_scale = sprite_data['offset_steps']
        offsets = sprite_data['offsets']

        entity_frame = CardMaker(name)
        #setting frame's size. Say, for 32x32 sprite all of these need to be 16
        entity_frame.set_frame(-(size_x/2), (size_x/2), -(size_y/2), (size_y/2))

        entity_object = render.attach_new_node(entity_frame.generate())
        entity_object.set_texture(texture)

        #okay, this does the magic
        #basically, to show the very first sprite of 2 in row, we set tex scale
        #to half (coz half is our normal char's size). If we will need to use it
        #with sprites other than first - then we also should adjust offset accordingly
        #entity_object.set_tex_offset(TextureStage.getDefault(), 0.5, 0)
        #entity_object.set_tex_scale(TextureStage.getDefault(), 0.5, 1)
        entity_object.set_tex_scale(TextureStage.getDefault(),
                                    horizontal_scale, vertical_scale)

        #now, to use the stuff from cut_spritesheet function.
        #lets say, we need to use second sprite from sheet. Just do:
        #entity_object.set_tex_offset(TextureStage.getDefault(), *offsets[1])
        #but, by default, offset should be always set to 0. In case our object
        #has just one sprite. Or something like that
        default_sprite = 0
        entity_object.set_tex_offset(TextureStage.getDefault(),
                                     *offsets[default_sprite])

        #enable support for alpha channel. This is a float, e.g making it non-100%
        #will require values between 0 and 1
        entity_object.set_transparency(1)

        #if no position has been received - wont set it up
        if position:
            entity_object.set_pos(*position)

        #setting character's collisions
        entity_collider = CollisionNode(name)

        #if no collision mask has been received - using defaults
        if collision_mask:
            entity_collider.set_from_collide_mask(BitMask32(collision_mask))
            entity_collider.set_into_collide_mask(BitMask32(collision_mask))

        #TODO: move this to be under character's legs
        #right now its centered on character's center
        if hitbox_size:
            self.hitbox_size = hitbox_size
        else:
            #coz its sphere and not oval - it doesnt matter if we use x or y
            #but, for sake of convenience - we are going for size_y
            self.hitbox_size = (size_y/2)

        entity_collider.add_solid(CollisionSphere(0, 0, 0, self.hitbox_size))
        entity_collision = entity_object.attach_new_node(entity_collider)

        #this will explode if its not, but I dont have a default right now
        if name in ANIMS:
            entity_anims = ANIMS[name]

        self.name = name
        self.object = entity_object
        self.collision = entity_collision
        self.sprites = offsets
        #setting this to None may cause crashes on few rare cases, but going
        #for "idle_right" wont work for projectiles... So I technically add it
        #there for anims updater, but its meant to be overwritten at 100% cases
        self.current_animation = None
        #this will always be 0, so regardless of consistency I will live it be
        self.current_frame = default_sprite
        self.animations = entity_anims
        #death status, that may be usefull during cleanup
        self.dead = False

        #attaching python tags to object node, so these will be accessible during
        #collision events and similar stuff
        self.object.set_python_tag("name", self.name)

        #I thought to put ctrav there, but for whatever reason it glitched projectile
        #to fly into left wall. So I moved it to Creature subclass

        #debug function to show collisions all time
        #self.collision.show()

        #do_method_later wont work there, coz its indeed based on frames
        base.task_mgr.add(self.update_anims, "update entity's animations")

    def update_anims(self, event):
        '''Meant to run as taskmanager routine. Update entity's animation's frame
        each self.animations_speed seconds'''
        #safety check to dont do anything if custom anim isnt set or entity is
        #already dead. #Will maybe remove death statement later (coz gibs), idk
        if self.dead or not self.current_animation:
            return event.cont

        #ensuring that whatever below only runs if enough time has passed
        dt = globalClock.get_dt()
        self.animations_timer -= dt
        if self.animations_timer > 0:
            return event.cont

        #log.debug("Updating anims")
        #resetting anims timer, so countdown above will start again
        self.animations_timer = self.animations_speed

        if self.current_frame < self.animations[self.current_animation][1]:
            self.current_frame += 1
        else:
            self.current_frame = self.animations[self.current_animation][0]

        self.object.set_tex_offset(TextureStage.getDefault(),
                                   *self.sprites[self.current_frame])

        return event.cont

    def change_animation(self, action):
        '''Receive the name of new action. If current entity's animation is not
        it - then change entity's animation to match that action'''
        if self.current_animation != action:
            log.debug(f"Changing animation of {self.name} to {action}")
            self.current_frame = self.animations[action][0]
            self.current_animation = action

    def die(self):
        self.collision.remove_node()
        #idk if cleaning up tags will make sense if node will be removed anyway
        #left it there for future reference
        # python_tags = self.object.get_python_tags().copy()
        # for item in python_tags:
            # self.object.clear_python_tag(item)
        # del python_tags
        #it may be good idea for creatures to dont remove the node on death, but
        #play some death animation and then leave gibs on floor for a while. #TODO
        self.object.remove_node()
        self.dead = True
        log.debug(f"{self.name} is now dead")

class Creature(Entity2D):
    '''Subclass of Entity2D, dedicated to generation of player and enemies'''
    def __init__(self, name, spritesheet = None, sprite_size = None,
                 hitbox_size = None, collision_mask = None, position = None,
                 animations_speed = None):
        #Initializing all the stuff from parent class'es init to be done
        super().__init__(name, spritesheet, sprite_size, hitbox_size,
                         collision_mask, position, animations_speed)
        #attempting to find stats of entity with name {name} in STATS
        #if not found - will fallback to STATS['default']
        if name in STATS:
            entity_stats = STATS[name]
        else:
            entity_stats = STATS['default']
        log.debug(f"Set {name}'s stats to be {entity_stats}")

        #this is probably not the best way, but whatever - temporary solution
        #also this will crash if there are no skills, but that shouldnt happen
        entity_skills = {}
        for item in entity_stats['skills']:
            if item in SKILLS:
                entity_skills[item] = SKILLS[item].copy()

        self.direction = 'right'
        self.current_animation = f'idle_{self.direction}'
        #its .copy() coz otherwise we will link to dictionary itself, which will
        #cause any change to stats of one enemy to affect every other enemy
        self.stats = entity_stats.copy()
        self.skills = entity_skills

        #list with timed status effects. When any of these reach 0 - they get ignored
        self.status_effects = {}

        self.object.set_python_tag("stats", self.stats)
        self.object.set_python_tag("get_damage", self.get_damage)

        #attaching our object's collisions to pusher and traverser
        #TODO: this way enemies will collide with walls too. Idk how to solve it
        #yet, without attaching walls to pusher (which will break them)
        #config.PUSHER.add_collider(self.collision, self.object)
        #config.CTRAV.add_collider(self.collision, config.PUSHER)
        base.pusher.add_collider(self.collision, self.object)
        base.cTrav.add_collider(self.collision, base.pusher)

        #billboard is effect to ensure that object always face camera the same
        #e.g this is the key to achieve that "2.5D style" I aim for
        self.object.set_billboard_point_eye()

        base.task_mgr.add(self.status_effects_handler, "status effects handler")

        #used to avoid issue with getting multiple damage func calls per frame
        #see game_window's damage functions
        self.last_collision_time = 0
        self.object.set_python_tag("last_collision_time", self.last_collision_time)

    def status_effects_handler(self, event):
        '''Meant to run as taskmanager routine. Each frame, reduce lengh of active
        status effects. When it reaches 0 - remove status effect'''
        if not self.status_effects:
            return event.cont

        #removing the task from being called again if target is already dead
        if self.dead:
            return

        dt = globalClock.get_dt()
        #copying to avoid causing issues by changing dic size during for loop
        se = self.status_effects.copy()
        for effect in se:
            self.status_effects[effect] -= dt
            if self.status_effects[effect] <= 0:
                del self.status_effects[effect]
                log.debug(f"{effect} effect has expired on {self.name}")

        return event.cont

    def get_damage(self, amount = None):
        '''Whatever stuff procs when target is about to get hurt'''
        if not amount:
            amount = 0

        #not getting any damage in case we are invulnerable
        if 'immortal' in self.status_effects:
            return

        self.stats['hp'] -= amount
        log.debug(f"{self.name} has received {amount} damage "
                  f"and is now on {self.stats['hp']} hp")

        if self.stats['hp'] <= 0:
            self.die()
            return

        #attempt to stun target for 0.5 seconds on taking damage. #TODO: make
        #configurable from skill's stats
        try:
            self.status_effects['stun'] += 0.5
        except KeyError:
            self.status_effects['stun'] = 0.5

        #this is placeholder. May need to track target's name in future to play
        #different damage sounds
        base.assets.sfx['damage'].play()

        self.change_animation(f"hurt_{self.direction}")

    def die(self):
        death_sound = f"{self.name}_death"
        #playing different sounds, depending if target has its own death sound or not
        try:
            base.assets.sfx[death_sound].play()
        except KeyError:
            log.warning(f"{self.name} has no custom death sound, using fallback")
            base.assets.sfx['default_death'].play()

        super().die()

class Player(Creature):
    '''Subclass of Creature, dedicated to creation of player'''
    def __init__(self, name, spritesheet = None, sprite_size = None,
                 hitbox_size = None, collision_mask = None, position = None,
                 animations_speed = None):
        collision_mask = PLAYER_COLLISION_MASK
        super().__init__(name, spritesheet, sprite_size, hitbox_size,
                         collision_mask, position, animations_speed)

        base.task_mgr.add(self.controls_handler, "controls handler")
        #the thing to track mouse position relatively to map. See attack handling
        #It probably could be better to move this thing to map func/class instead?
        #TODO
        self.ground_plane = Plane((0,0,1), (0,0,0))

    def controls_handler(self, event):
        '''
        Intended to be used as part of task manager routine. Automatically receive
        event from task manager, checks if buttons are pressed and log it. Then
        return event back to task manager, so it keeps running in loop
        '''
        #safety check to ensure that player isnt dead, otherwise it will crash
        if self.dead:
            return event.cont

        #manipulating cooldowns on player's skills. It may be good idea to move
        #it to separate routine and check cooldowns of all entities on screen
        dt = globalClock.get_dt()

        #this seem to work reasonably decent. Not to jinx tho
        skills = self.skills
        for skill in skills:
            if skills[skill]['used']:
                skills[skill]['cur_cd'] -= dt
                if skills[skill]['cur_cd'] <= 0:
                    log.debug(f"Player's {skills[skill]['name']} has been recharged")
                    skills[skill]['used'] = False
                    skills[skill]['cur_cd'] = skills[skill]['def_cd']

        if 'stun' in self.status_effects:
            return event.cont

        #idk if I need to export this to variable or call directly
        #in case it will backfire - turn this var into direct dictionary calls
        mov_speed = self.stats['mov_spd']

        #change the direction character face, based on mouse pointer position
        #this may need some tweaking if I will decide to add gamepad support
        #basically, the idea is the following: since camera is centered right
        #above our character, our char is the center of screen. Meaning positive
        #x will mean pointer is facing right and negative: pointer is facing left.
        #And thus char should do the same. This is kind of hack and will also
        #need tweaking if more sprites will be added. But for now it works
        #hint: this can also be used together with move buttons. E.g mouse change
        #the direction head/eyes face and keys change body. But that will depend
        #on amount of animations I would obtain. For now, lets leave it like that
        mouse_watcher = base.mouseWatcherNode
        #ensuring that mouse pointer is part of game's window right now
        if mouse_watcher.has_mouse():
            mouse_x = mouse_watcher.get_mouse_x()
            if mouse_x > 0:
                self.direction = 'right'
            else:
                self.direction = 'left'

        #saving action to apply to our animation. Default is idle
        action = 'idle'

        #In future, these speed values may be affected by some items
        player_object = self.object
        if base.level.controls_status["move_up"]:
            player_object.set_pos(player_object.get_pos() + (0, -mov_speed, 0))
            action = "move"
        if base.level.controls_status["move_down"]:
            player_object.set_pos(player_object.get_pos() + (0, mov_speed, 0))
            action = "move"
        if base.level.controls_status["move_left"]:
            player_object.set_pos(player_object.get_pos() + (mov_speed, 0, 0))
            action = "move"
        if base.level.controls_status["move_right"]:
            player_object.set_pos(player_object.get_pos() + (-mov_speed, 0, 0))
            action = "move"

        #this is placeholder - its janky and spawns right above the player. #TODO
        if base.level.controls_status["attack"] and not skills['atk_0']['used']:
            skills['atk_0']['used'] = True

            #make player impossible to move on cast. It make controls a bit janky,
            #but remove that issue when player moving to some direction can catch
            #its own projectile. I may reconsider the way it works in future
            #self.status_effects['stun'] = skills['atk_0']['def_cd']/4
            self.status_effects['stun'] = 0.1

            #long story short, what happens there: we are getting mouse pointer's
            #position, then trying to translate it to the ground via plane.
            #this could probably be done faster and better, but for now it works
            mouse_pos = mouse_watcher.get_mouse()

            mouse_pos_3d = Point3()
            near = Point3()
            far = Point3()

            base.camLens.extrude(mouse_pos, near, far)
            self.ground_plane.intersects_line(mouse_pos_3d,
                                         render.get_relative_point(base.camera, near),
                                         render.get_relative_point(base.camera, far))

            hit_vector = mouse_pos_3d - player_object.get_pos()
            hit_vector.normalize()

            hit_vector_x, hit_vector_y = hit_vector.get_xy()
            #y has to be flipped if billboard_effect is active. Otherwise x has
            #to be flipped. Idk why its this way, probs coz first cam's num is 0
            #hit_vector_2D = hit_vector_x, -hit_vector_y
            hit_vector_2D = -hit_vector_x, hit_vector_y

            y_vec = Vec2(0, 1)
            angle = y_vec.signed_angle_deg(hit_vector_2D)

            pos_diff = DEFAULT_SPRITE_SIZE[0]/2
            #this is a bit awkward with billboard effect, coz slashing below
            #make projectile go into the ground. I should do something about it
            #TODO
            proj_pos = player_object.get_pos() + hit_vector*pos_diff
            attack = Projectile("attack",
                                position = proj_pos,
                                #position = player_object.get_pos(),
                                direction = proj_pos,
                                #object_size = (1.2, 1.2, 1.2),
                                damage = self.stats['dmg'])

            #rotating projectile around 2d axis to match the shooting angle
            attack.object.set_r(angle)
            base.level.projectiles.append(attack)

        #this is kinda awkward coz its tied to cooldown and may look weird. I
        #may do something about that later... Like add "skill_cast_time" or idk
        if skills['atk_0']['used']:
            action = "attack"

        self.change_animation(f"{action}_{self.direction}")

        #it works a bit weird, but if we wont return .cont of task we received,
        #then task will run just once and then stop, which we dont want
        return event.cont

    def get_damage(self, amount = None):
        #giving player invinsibility frames on received damage
        #these shouldnt stack... I think? May backfire in future, idk
        super().get_damage(amount)
        #this check is there to avoid stacking up immortality
        if not 'immortal' in self.status_effects:
            #this is a bit longer than stun lengh, to let player escape
            self.status_effects['immortal'] = 0.7
        #updating the value on player's hp gui
        base.level.player_hp_ui.setText(f"{self.stats['hp']}")
        base.level.reset_score_multiplier()

    def die(self):
        #disable hud on death. This is not the most optimal thing, since it stays
        #there on background, just in hidden form. But for now it will do
        base.level.player_hud.hide()
        position = self.object.get_pos()
        #reparenting camera, to avoid crash on removal of player's node.
        #This may be unnecessary if we will implement gibs handler
        base.camera.reparent_to(render)
        super().die()

        #kinda nasty way to update the score part of death screen
        base.level.high_score.setText(f"Your score is {base.level.score}")
        base.level.death_screen.show()

class Enemy(Creature):
    '''Subclass of Creature, dedicated to creation of enemies'''
    def __init__(self, name, spritesheet = None, sprite_size = None,
                 hitbox_size = None, collision_mask = None, position = None,
                 animations_speed = None):
        collision_mask = ENEMY_COLLISION_MASK
        super().__init__(name, spritesheet, sprite_size, hitbox_size,
                         collision_mask, position, animations_speed)

        base.task_mgr.add(self.ai_movement_handler, "controls handler")

        #id variable that will be set from game_window. Placed it there to avoid
        #possible crashes and to remind that its a thing that exists
        self.id = None

    def ai_movement_handler(self, event):
        '''This is but nasty hack to make enemies follow character. TODO: remake
        and move to its own module'''
        #TODO: maybe make it possible to chase not for just player?
        #TODO: not all enemies need to behave this way. e.g, for example, we can
        #only affect enemies that have their ['ai'] set to ['chaser']...
        #or something among these lines, will see in future

        #disable this handler if the enemy or player are dead. Without it, game
        #will crash the very next second after one of these events occur
        if self.dead or base.level.player.dead:
            return

        if 'stun' in self.status_effects:
            return event.cont

        player_position = base.level.player.object.get_pos()
        mov_speed = self.stats['mov_spd']

        enemy_position = self.object.get_pos()
        vector_to_player = player_position - enemy_position
        distance_to_player = vector_to_player.length()
        #normalizing vector is the key to avoid "flickering" effect, as its
        #basically ignores whatever minor difference in placement there are
        #I dont know how it works, lol
        vector_to_player.normalize()

        new_pos = enemy_position + (vector_to_player*mov_speed)
        pos_diff = enemy_position - new_pos

        action = 'idle'

        #it may be good idea to also track camera angle, if I will decide
        #to implement camera controls, at some point or another
        if pos_diff[0] > 0:
            self.direction = 'right'
        else:
            self.direction = 'left'

        #this thing basically makes enemy move till it hit player, than play
        #attack animation. May backfire if player's sprite size is not equal
        #to player's hitbox
        if distance_to_player > DEFAULT_SPRITE_SIZE[0]*2:
            action = 'move'
        else:
            action = 'attack'

        self.object.set_pos(new_pos)
        self.change_animation(f'{action}_{self.direction}')

        return event.cont

    def get_damage(self, amount = None):
        super().get_damage(amount)
        #increasing score, based on HIT_SCORE value. It may be good idea to, instead,
        #increase it based on amount of damage received. But thats #TODO in future
        base.level.increase_score_multiplier()
        base.level.update_score(HIT_SCORE)

    def die(self):
        super().die()
        #for now this increase score based on HIT_SCORE+KILL_SCORE.
        #I dont think its a trouble, but may tweak at some point
        base.level.update_score(KILL_SCORE)
        #reduce enemy counter
        base.level.update_enemy_counter(-1)

class Projectile(Entity2D):
    '''Subclass of Entity2D, dedicated to creation of collideable effects'''
    def __init__(self, name, direction, damage = 0, object_size = None,
                 spritesheet = None, sprite_size = None, hitbox_size = None,
                 collision_mask = None, position = None, animations_speed = None):
        #for now we are only adding these to player, so no need for other masks
        #todo: split this thing into 2 subclasses: for player's and enemy's stuff
        collision_mask = PLAYER_PROJECTILE_COLLISION_MASK
        super().__init__(name, spritesheet, sprite_size, hitbox_size,
                         collision_mask, position, animations_speed)

        self.damage = damage
        self.object.set_python_tag("damage", self.damage)
        self.current_animation = 'default'
        #todo: make this configurable from dictionary, idk
        self.lifetime = 0.1
        self.dead = False

        #Idk about numbers. These work if caster is player, but what s about enemies?
        one, two, _ = direction
        self.object.look_at(one, two, 1)

        if object_size:
            self.object.set_scale(object_size)

        #schedulging projectile to die in self.lifetime seconds after spawn
        #I've heard this is not the best way to do that, coz do_method_later does
        #things based on frames and not real time. But for now it will do
        base.task_mgr.do_method_later(self.lifetime, self.die, "remove projectile")

    def die(self, event):
        super().die()
        return
