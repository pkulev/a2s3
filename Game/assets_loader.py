## a2s3 - action arena game, written in python + panda3d
## Copyright (c) 2021 moonburnt
##
## This program is free software: you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation, either version 3 of the License, or
## (at your option) any later version.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with this program. If not, see https://www.gnu.org/licenses/gpl-3.0.txt

#module where I specify functions related to loading game assets into memory

from os import listdir
from os.path import isfile, isdir, basename, join, splitext
from panda3d.core import SamplerState
import logging

log = logging.getLogger(__name__)

GAME_DIR = '.'
ASSETS_DIR = join(GAME_DIR, 'Assets')
SPRITE_DIR = join(ASSETS_DIR, 'Sprites')
MUSIC_DIR = join(ASSETS_DIR, 'BGM')
SFX_DIR = join(ASSETS_DIR, 'SFX')

class AssetsLoader:
    def __init__(self):
        #this will load all the default assets into memory. With reworked loader,
        #it should conceptually be possible to load custom stuff on top of these
        #in future. E.g for modding and such purposes
        self.music = {}
        self.sfx = {}
        self.sprite = {}

        self.load_all()

    def get_files(self, pathtodir):
        '''
        Receives str(path to directory with files), returns list(files in directory)
        '''
        files = []

        log.debug(f"Attempting to parse directory {pathtodir}")
        directory_content = listdir(pathtodir)
        log.debug(f"Uncategorized content inside is: {directory_content}")

        for item in directory_content:
            log.debug(f"Processing {item}")
            itempath = join(pathtodir, item)
            if isdir(itempath):
                log.debug(f"{itempath} leads to directory, attempting "
                           "to process its content")
                files += self.get_files(itempath)
            else:
                #assuming that everything that isnt directory is file
                log.debug(f"{itempath} leads to file, adding to list")
                files.append(itempath)

        log.debug(f"Got following files in total: {files}")
        return files

    def load_music(self, pathtodir):
        '''Receive str(path to directory with music). Tries to load up all files
        from specified directory and all subdirs as music files and, then, update
        self.music dictionary with them. In case there are multiple entries with
        very same names - older ones will get overwritten'''
        files = self.get_files(pathtodir)

        data = {}
        for item in files:
            name_of_file = basename(item)
            name_without_extension = splitext(name_of_file)[0]
            data[name_without_extension] = loader.load_music(item)

        log.debug("Updating music storage")
        self.music = self.music | data

    def load_sfx(self, pathtodir):
        '''Receive str(path to directory with sfx). Tries to load up all files
        from specified directory and all subdirs as sfx files and, then, update
        self.sfx dictionary with them. In case there are multiple entries with
        very same names - older ones will get overwritten'''
        files = self.get_files(pathtodir)

        data = {}
        for item in files:
            name_of_file = basename(item)
            name_without_extension = splitext(name_of_file)[0]
            data[name_without_extension] = loader.load_sfx(item)

        log.debug("Updating sfx storage")
        self.sfx = self.sfx | data

    def load_sprite(self, pathtodir):
        '''Receive str(path to directory with sprites). Tries to load up all files
        from specified directory and all subdirs as sprite files and, then, update
        self.sprite dictionary with them. Also apply sampler state filter to all
        sprites, so they wont look blurry in-game. In case there are multiple
        entries with very same names - older ones will get overwritten'''
        files = self.get_files(pathtodir)

        data = {}
        for item in files:
            name_of_file = basename(item)
            name_without_extension = splitext(name_of_file)[0]
            sprite = loader.load_texture(item)
            sprite.set_magfilter(SamplerState.FT_nearest)
            sprite.set_minfilter(SamplerState.FT_nearest)
            data[name_without_extension] = sprite

        log.debug("Updating sprite storage")
        self.sprite = self.sprite | data

    def load_all(self):
        '''Load all assets from default paths'''
        self.load_music(MUSIC_DIR)
        self.load_sfx(SFX_DIR)
        self.load_sprite(SPRITE_DIR)

    def reset(self):
        '''Reset assets dictionaries to empty state'''
        self.music = {}
        self.sfx = {}
        self.sprite = {}

    def reload(self):
        '''Reset assets dictionaries to be empty, then load defaults'''
        self.reset()
        self.load_all()
