#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
# Copyright 2016-2018   Martin Sinn                         m.sinn@gmx.de
# Copyright 2016-       Christian Straßburg           c.strassburg@gmx.de
# Copyright 2012-2013   Marcus Popp                        marcus@popp.mx
#########################################################################
#  This file is part of SmartHomeNG.
#
#  SmartHomeNG is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  SmartHomeNG is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with SmartHomeNG. If not, see <http://www.gnu.org/licenses/>.
#########################################################################


import datetime
import dateutil.parser
import logging
import os
import re
import pickle
import threading
import math
import json

from lib.plugin import Plugins
from lib.shtime import Shtime

import lib.utils
from lib.constants import (ITEM_DEFAULTS, FOO, KEY_ENFORCE_UPDATES, KEY_CACHE, KEY_CYCLE, KEY_CRONTAB, KEY_EVAL,
                           KEY_EVAL_TRIGGER, KEY_TRIGGER, KEY_CONDITION, KEY_NAME, KEY_TYPE, KEY_VALUE, KEY_INITVALUE, PLUGIN_PARSE_ITEM,
                           KEY_AUTOTIMER, KEY_ON_UPDATE, KEY_ON_CHANGE, KEY_LOG_CHANGE, KEY_THRESHOLD, CACHE_FORMAT, CACHE_JSON, CACHE_PICKLE,
                           KEY_ATTRIB_COMPAT, ATTRIB_COMPAT_V12, ATTRIB_COMPAT_LATEST)


ATTRIB_COMPAT_DEFAULT_FALLBACK = ATTRIB_COMPAT_V12
ATTRIB_COMPAT_DEFAULT = ''


logger = logging.getLogger(__name__)


_items_instance = None    # Pointer to the initialized instance of the Items class (for use by static methods)



class Items():
    """
    Items loader class. Item-methods from bin/smarthome.py are moved here.
    
    :param smarthome: Instance of the smarthome master-object
    :param configxxx: Basename of the xxx configuration file
    :type samrthome: object
    :type configxxx: str
    """

    __items = []
    __item_dict = {}

    _children = []         # List of top level items


    def __init__(self, smarthome):
        self._sh = smarthome

        global _items_instance
        if _items_instance is not None:
            import inspect
            curframe = inspect.currentframe()
            calframe = inspect.getouterframes(curframe, 4)
            logger.critical("A second 'items' object has been created. There should only be ONE instance of class 'Items'!!! Called from: {} ({})".format(calframe[1][1], calframe[1][3]))

        _items_instance = self


    def load_itemdefinitions(self, env_dir, items_dir):
    
        item_conf = None
        item_conf = lib.config.parse_itemsdir(env_dir, item_conf)
        item_conf = lib.config.parse_itemsdir(items_dir, item_conf, addfilenames=True)
        
        for attr, value in item_conf.items():
            if isinstance(value, dict):
                child_path = attr
                try:
#                              (smarthome, parent, path, config):
                    child = Item(self._sh, self, child_path, value)
                except Exception as e:
                    logger.error("load_itemdefinitions: Item {}: problem creating: ()".format(child_path, e))
                else:
                    vars(self)[attr] = child
                    vars(self._sh)[attr] = child
                    self.add_item(child_path, child)
                    self._children.append(child)
        del(item_conf)  # clean up

        for item in self.return_items():
            item._init_prerun()
        for item in self.return_items():
            item._init_run()
#        self.item_count = len(self.__items)
#        self._sh.item_count = self.item_count()



    # aus bin/smarthome.py
#    def __iter__(self):
#        for child in self.__children:
#            yield child
    def get_toplevel_items(self):
        for child in self._children:
            yield child

    # aus lib.logic.py
#    def __iter__(self):
#        for logic in self._logics:
#            yield logic


    # ------------------------------------------------------------------------------------
    #   Following (static) methods of the class Items implement the API for Items in shNG
    # ------------------------------------------------------------------------------------

    @staticmethod
    def get_instance():
        """
        Returns the instance of the Items class, to be used to access the items-api
        
        Use it the following way to access the api:
        
        .. code-block:: python

            from lib.item import Items
            items = Items.get_instance()
            
            # to access a method (eg. return_items()):
            items.return_items()

        
        :return: items instance
        :rtype: object of None
        """
        return _items_instance




    def add_item(self, path, item):
        """
        Function to to add an item to the dictionary of items.
        If the path does not exist, it is created

        :param path: Path of the item
        :param item: The item itself
        :type path: str
        :type item: object
        """

        if path not in self.__items:
            self.__items.append(path)
        self.__item_dict[path] = item


    def return_item(self, string):
        """
        Function to return the item for a given path

        :param string: Path of the item to return
        :type string: str

        :return: Item
        :rtype: object
        """

        if string in self.__items:
            return self.__item_dict[string]


    def return_items(self):
        """"
        Function to return a list with all items

        :return: List of all items
        :rtype: list
        """

        for item in self.__items:
            yield self.__item_dict[item]


    def match_items(self, regex):
        """
        Function to match items against a regular expresseion

        :param regex: Regular expression to match items against
        :type regex: str

        :return: List of matching items
        :rtype: list
        """

        regex, __, attr = regex.partition(':')
        regex = regex.replace('.', '\.').replace('*', '.*') + '$'
        regex = re.compile(regex)
        attr, __, val = attr.partition('[')
        val = val.rstrip(']')
        if attr != '' and val != '':
            return [self.__item_dict[item] for item in self.__items if regex.match(item) and attr in self.__item_dict[item].conf and ((type(self.__item_dict[item].conf[attr]) in [list,dict] and val in self.__item_dict[item].conf[attr]) or (val == self.__item_dict[item].conf[attr]))]
        elif attr != '':
            return [self.__item_dict[item] for item in self.__items if regex.match(item) and attr in self.__item_dict[item].conf]
        else:
            return [self.__item_dict[item] for item in self.__items if regex.match(item)]


    def find_items(self, conf):
        """"
        Function to find items that match the specified configuration

        :param conf: Configuration to look for
        :type conf: str

        :return: list of matching items
        :rtype: list
        """

        for item in self.__items:
            if conf in self.__item_dict[item].conf:
                yield self.__item_dict[item]


    def find_children(self, parent, conf):
        """
        Function to find children with the specified configuration

        :param parent: parent item on which to start the search
        :param conf: Configuration to look for
        :type parent: str
        :type conf: str

        :return: list or matching child-items
        :rtype: list
        """

        children = []
        for item in parent:
            if conf in item.conf:
                children.append(item)
            children += self.find_children(item, conf)
        return children


    def item_count(self):
        """
        Return the number of items
        """
        return len(self.__items)


    def stop(self, signum=None, frame=None):
        """
        Stop fading of all items
        """
        for item in self.__items:
            self.__item_dict[item]._fading = False





#####################################################################
# Item Class
#####################################################################


class Item():

    _itemname_prefix = 'items.'     # prefix for scheduler names

    def __init__(self, smarthome, parent, path, config):
        self._sh = smarthome
        self._use_conditional_triggers = False
        try:
            if self._sh._use_conditional_triggers.lower() == 'true':
                self._use_conditional_triggers = True
        except: pass

        self.plugins = Plugins.get_instance()
        self.shtime = Shtime.get_instance()

        self._filename = None
        self._autotimer = False
        self._cache = False
        self.cast = _cast_bool
        self.__changed_by = 'Init:None'
        self.__updated_by = 'Init:None'
        self.__children = []
        self.conf = {}
        self._crontab = None
        self._cycle = None
        self._enforce_updates = False
        self._eval = None				    # -> KEY_EVAL
        self._eval_trigger = False
        self._trigger = False
        self._trigger_condition_raw = []
        self._trigger_condition = None
        self._on_update = None				# -> KEY_ON_UPDATE eval expression
        self._on_change = None				# -> KEY_ON_CHANGE eval expression
        self._on_update_dest_var = None		# -> KEY_ON_UPDATE destination var
        self._on_change_dest_var = None		# -> KEY_ON_CHANGE destination var
        self._log_change = None
        self._log_change_logger = None
        self._fading = False
        self._items_to_trigger = []
        self.__last_change = self.shtime.now()
        self.__last_update = self.shtime.now()
        self._lock = threading.Condition()
        self.__logics_to_trigger = []
        self._name = path
        self.__prev_change = self.shtime.now()
        self.__prev_update = self.shtime.now()
        self.__methods_to_trigger = []
        self.__parent = parent
        self._path = path
        self._sh = smarthome
        self._threshold = False
        self._type = None
        self._value = None
        # history
        # TODO: create history Arrays for some values (value, last_change, last_update  (usage: multiklick,...)
        # self.__history = [None, None, None, None, None]
        #
        # def getValue(num):
        #    return (str(self.__history[(num - 1)]))
        #
        # def addValue(avalue):
        #    self.__history.append(avalue)
        #    if len(self.__history) > 5:
        #        self.__history.pop(0)
        #
        if hasattr(smarthome, '_item_change_log'):
            self._change_logger = logger.info
        else:
            self._change_logger = logger.debug
        #############################################################
        # Initialize attribute assignment compatibility
        #############################################################
        global ATTRIB_COMPAT_DEFAULT
        if ATTRIB_COMPAT_DEFAULT == '':
            if hasattr(smarthome, '_'+KEY_ATTRIB_COMPAT):
                config_attrib = getattr(smarthome,'_'+KEY_ATTRIB_COMPAT)
                if str(config_attrib) in [ATTRIB_COMPAT_V12, ATTRIB_COMPAT_LATEST]:
                    logger.info("Global configuration: '{}' = '{}'.".format(KEY_ATTRIB_COMPAT, str(config_attrib)))
                    ATTRIB_COMPAT_DEFAULT = config_attrib
                else:
                    logger.warning("Global configuration: '{}' has invalid value '{}'.".format(KEY_ATTRIB_COMPAT, str(config_attrib)))
            if ATTRIB_COMPAT_DEFAULT == '':
                ATTRIB_COMPAT_DEFAULT = ATTRIB_COMPAT_DEFAULT_FALLBACK
        #############################################################
        # Item Attributes
        #############################################################
        for attr, value in config.items():
            if not isinstance(value, dict):
                if attr in [KEY_CYCLE, KEY_NAME, KEY_TYPE, KEY_VALUE, KEY_INITVALUE]:
                    if attr == KEY_INITVALUE:
                        attr = KEY_VALUE
                    setattr(self, '_' + attr, value)
                elif attr in [KEY_EVAL]:
                    value = self.get_stringwithabsolutepathes(value, 'sh.', '(', KEY_EVAL)
                    setattr(self, '_' + attr, value)
                elif attr in [KEY_CACHE, KEY_ENFORCE_UPDATES]:  # cast to bool
                    try:
                        setattr(self, '_' + attr, _cast_bool(value))
                    except:
                        logger.warning("Item '{0}': problem parsing '{1}'.".format(self._path, attr))
                        continue
                elif attr in [KEY_CRONTAB]:  # cast to list
                    if isinstance(value, str):
                        value = [value, ]
                    setattr(self, '_' + attr, value)
                elif attr in [KEY_EVAL_TRIGGER] or (self._use_conditional_triggers and attr in [KEY_TRIGGER]):  # cast to list
                    if isinstance(value, str):
                        value = [value, ]
                    expandedvalue = []
                    for path in value:
                        expandedvalue.append(self.get_absolutepath(path, attr))
                    self._trigger = expandedvalue
                elif (attr in [KEY_CONDITION]) and self._use_conditional_triggers:  # cast to list
                    if isinstance(value, list):
                        cond_list = []
                        for cond in value:
                            cond_list.append(dict(cond))
                        self._trigger_condition = self._build_trigger_condition_eval(cond_list)
                        self._trigger_condition_raw = cond_list
                    else:
                        logger.warning("Item __init__: {}: Invalid trigger_condition specified! Must be a list".format(self._path))
                elif attr in [KEY_ON_CHANGE, KEY_ON_UPDATE]:
                    if isinstance(value, str):
                        value = [ value ]
                    val_list = []
                    dest_var_list = []
                    for val in value:
                        # seperate destination item (if it exists)
                        dest_item, val = self._split_destitem_from_value(val)
                        # expand relative item pathes
                        dest_item = self.get_absolutepath(dest_item, KEY_ON_CHANGE).strip()
#                        val = 'sh.'+dest_item+'( '+ self.get_stringwithabsolutepathes(val, 'sh.', '(', KEY_ON_CHANGE) +' )'
                        val = self.get_stringwithabsolutepathes(val, 'sh.', '(', KEY_ON_CHANGE)
#                        logger.warning("Item __init__: {}: for attr '{}', dest_item '{}', val '{}'".format(self._path, attr, dest_item, val))
                        val_list.append(val)
                        dest_var_list.append(dest_item)
                    setattr(self, '_' + attr, val_list)
                    setattr(self, '_' + attr + '_dest_var', dest_var_list)
                elif attr in [KEY_LOG_CHANGE]:
                    if value != '':
                        setattr(self, '_log_change', value)
                        self._log_change_logger = logging.getLogger('items.'+value)
                        # set level to make logger appear in internal list of loggers (if not configured by logging.yaml)
                        if self._log_change_logger.level == 0:
                            self._log_change_logger.setLevel('INFO')
                elif attr == KEY_AUTOTIMER:
                    time, value, compat = _split_duration_value_string(value)
                    timeitem = None
                    valueitem = None
                    if time.lower().startswith('sh.') and time.endswith('()'):
                        timeitem = self.get_absolutepath(time[3:-2], KEY_AUTOTIMER)
                        time = 0
                    if value.lower().startswith('sh.') and value.endswith('()'):
                        valueitem = self.get_absolutepath(value[3:-2], KEY_AUTOTIMER)
                        value = ''
                    value = self._castvalue_to_itemtype(value, compat)
                    self._autotimer = [ (self._cast_duration(time), value), compat, timeitem, valueitem]
                elif attr == KEY_THRESHOLD:
                    low, __, high = value.rpartition(':')
                    if not low:
                        low = high
                    self._threshold = True
                    self.__th_crossed = False
                    self.__th_low = float(low.strip())
                    self.__th_high = float(high.strip())
                    logger.debug("Item {}: set threshold => low: {} high: {}".format(self._path, self.__th_low, self.__th_high))
                elif attr == '_filename':
                    # name of file, which defines this item
                    setattr(self, attr, value)
                else:
                    # plugin specific attribute
                    if value == '..':
                        self.conf[attr] = self._get_attr_from_parent(attr)
                    elif value == '...':
                        self.conf[attr] = self._get_attr_from_grandparent(attr)
                    else:
                        self.conf[attr] = value
        #############################################################
        # Child Items
        #############################################################
        for attr, value in config.items():
            if isinstance(value, dict):
                child_path = self._path + '.' + attr
                try:
                    child = Item(smarthome, self, child_path, value)
                except Exception as e:
                    logger.exception("Item {}: problem creating: {}".format(child_path, e))
                else:
                    vars(self)[attr] = child
                    _items_instance.add_item(child_path, child)
                    self.__children.append(child)
        #############################################################
        # Cache
        #############################################################
        if self._cache:
            self._cache = self._sh._cache_dir + self._path
            try:
                self.__last_change, self._value = _cache_read(self._cache, self.shtime.tzinfo())
                self.__last_update = self.__last_change
                self.__prev_change = self.__last_change
                self.__prev_update = self.__last_change
                self.__changed_by = 'Cache:None'
                self.__updated_by = 'Cache:None'
            except Exception as e:
                logger.warning("Item {}: problem reading cache: {}".format(self._path, e))
        #############################################################
        # Type
        #############################################################
        #__defaults = {'num': 0, 'str': '', 'bool': False, 'list': [], 'dict': {}, 'foo': None, 'scene': 0}
        if self._type is None:
            self._type = FOO  # MSinn
        if self._type not in ITEM_DEFAULTS:
            logger.error("Item {}: type '{}' unknown. Please use one of: {}.".format(self._path, self._type, ', '.join(list(ITEM_DEFAULTS.keys()))))
            raise AttributeError
        self.cast = globals()['_cast_' + self._type]
        #############################################################
        # Value
        #############################################################
        if self._value is None:
            self._value = ITEM_DEFAULTS[self._type]
        try:
            self._value = self.cast(self._value)
        except:
            logger.error("Item {}: value {} does not match type {}.".format(self._path, self._value, self._type))
            raise
        self.__prev_value = self._value
        #############################################################
        # Cache write/init
        #############################################################
        if self._cache:
            if not os.path.isfile(self._cache):
                _cache_write(self._cache, self._value)
                logger.warning("Item {}: Created cache for item: {}".format(self._cache, self._cache))
        #############################################################
        # Crontab/Cycle
        #############################################################
        if self._crontab is not None or self._cycle is not None:
            cycle = self._cycle
            if cycle is not None:
                cycle = self._build_cycledict(cycle)
            self._sh.scheduler.add(self._itemname_prefix+self._path, self, cron=self._crontab, cycle=cycle)
        #############################################################
        # Plugins
        #############################################################
        for plugin in self.plugins.return_plugins():
            #plugin.xxx = []  # Empty reference list list of items
            if hasattr(plugin, PLUGIN_PARSE_ITEM):
                update = plugin.parse_item(self)
                if update:
                    try:
                        plugin._append_to_itemlist(self)
                    except:
                        pass
                    self.add_method_trigger(update)


    def _split_destitem_from_value(self, value):
        """
        For on_change and on_update: spit destination item from attribute value
        
        :param value: attribute value
        
        :return: dest_item, value
        :rtype: str, str
        """
        dest_item = ''
        # Check if assignment operator ('=') exists                   
        if value.find('=') != -1:
            # If delimiter exists, check if equal operator exists
            if value.find('==') != -1:
                # equal operator exists
                if value.find('=') < value.find('=='):
                    # assignment operator exists in front of equal operator
                    dest_item = value[:value.find('=')].strip()
                    value = value[value.find('=')+1:].strip()
            else:
                # if equal operator does not exist
                dest_item = value[:value.find('=')]
                value = value[value.find('=')+1:].strip()
        return dest_item, value


    def _castvalue_to_itemtype(self, value, compat):
        """
        casts the value to the type of the item, if backward compatibility 
        to version 1.2 (ATTRIB_COMPAT_V12) is not enabled
        
        If backward compatibility is enabled, the value is returned unchanged
        
        :param value: value to be casted
        :param compat: compatibility attribute
        :return: return casted valu3
        """
        # casting of value, if compat = latest
        if compat == ATTRIB_COMPAT_LATEST:
            if self._type != None:
                mycast = globals()['_cast_' + self._type]
                try:
                    value = mycast(value)
                except:
                    logger.warning("Item {}: Unable to cast '{}' to {}".format(self._path, str(value), self._type))
                    if isinstance(value, list):
                        value = []
                    elif isinstance(value, dict):
                        value = {}
                    else:
                        value = mycast('')
            else:
                logger.warning("Item {}: Unable to cast '{}' to {}".format(self._path, str(value), self._type))
        return value
        

    def _cast_duration(self, time): 
        """
        casts a time valuestring (e.g. '5m') to an duration integer
        used for autotimer, timer, cycle
    
        supported formats for time parameter:
        - seconds as integer (45)
        - seconds as a string ('45')
        - seconds as a string, traild by 's' ('45s')
        - minutes as a string, traild by 'm' ('5m'), is converted to seconds (300)
        
        :param time: string containing the duration
        :param itempath: item path as aditional information for logging
        :return: number of seconds as an integer
        """
        if isinstance(time, str):
            try:
                time = time.strip()
                if time.endswith('m'):
                    time = int(time.strip('m')) * 60
                elif time.endswith('s'):
                    time = int(time.strip('s'))
                else:
                    time = int(time)
            except Exception as e:
                logger.warning("Item {}: _cast_duration ({}) problem: {}".format(self._path, time, e))
                time = False
        elif isinstance(time, int):
            time = int(time)
        else:
            logger.warning("Item {}: _cast_duration ({}) problem: unable to convert to int".format(self._path, time))
            time = False
        return(time)
    

    def _build_cycledict(self, value):
        """
        builds a dict for a cycle parameter from a duration_value_string
        
        This dict is to be passed to the scheduler to circumvemt the parameter
        parsing within the scheduler, which can't to casting

        :param value: raw attribute string containing duration, value (and compatibility)
        :return: cycle-dict for a call to scheduler.add 
        """
        time, value, compat = _split_duration_value_string(value)
        time = self._cast_duration(time)
        value = self._castvalue_to_itemtype(value, compat)
        cycle = {time: value}
        return cycle
    

    def expand_relativepathes(self, attr, begintag, endtag):
        """
        converts a configuration attribute containing relative item pathes
        to absolute pathes
        
        The item's attribute can be of type str or list (of strings)
        
        The begintag and the endtag remain in the result string!

        :param attr: Name of the attribute
        :param begintag: string that signals the beginning of a relative path is following
        :param endtag: string that signals the end of a relative path
        
        """
        if attr in self.conf:
            if isinstance(self.conf[attr], str):
                if (begintag != '') and (endtag != ''):
                    self.conf[attr] = self.get_stringwithabsolutepathes(self.conf[attr], begintag, endtag, attr)
                elif (begintag == '') and (endtag == ''):
                    self.conf[attr] = self.get_absolutepath(self.conf[attr], attr)
            elif isinstance(self.conf[attr], list):
                logger.debug("expand_relativepathes(1): to expand={}".format(self.conf[attr]))
                new_attr = []
                for a in self.conf[attr]:
                    logger.debug("expand_relativepathes: vor : to expand={}".format(a))
                    if (begintag != '') and (endtag != ''):
                        a = self.get_stringwithabsolutepathes(a, begintag, endtag, attr)
                    elif (begintag == '') and (endtag == ''):
                        a = self.get_absolutepath(a, attr)
                    logger.debug("expand_relativepathes: nach: to expand={}".format(a))
                    new_attr.append(a)
                self.conf[attr] = new_attr
                logger.debug("expand_relativepathes(2): to expand={}".format(self.conf[attr]))
            else:
                logger.warning("expand_relativepathes: attr={} can not expand for type(self.conf[attr])={}".format(attr, type(self.conf[attr])))
        return
        

    def get_stringwithabsolutepathes(self, evalstr, begintag, endtag, attribute=''):
        """
        converts a string containing relative item pathes
        to a string with absolute item pathes
        
        The begintag and the endtag remain in the result string!

        :param evalstr: string with the statement that may contain relative item pathes
        :param begintag: string that signals the beginning of a relative path is following
        :param endtag: string that signals the end of a relative path
        :param attribute: string with the name of the item's attribute, which contains the relative path
        
        :return: string with the statement containing absolute item pathes
        """
        if evalstr.find(begintag+'.') == -1:
            return evalstr

#        logger.warning("{}.get_stringwithabsolutepathes('{}'): begintag = '{}', endtag = '{}'".format(self._path, evalstr, begintag, endtag))
        pref = ''
        rest = evalstr
        while (rest.find(begintag+'.') != -1):
            pref += rest[:rest.find(begintag+'.')+len(begintag)]
            rest = rest[rest.find(begintag+'.')+len(begintag):]
            rel = rest[:rest.find(endtag)]
            rest = rest[rest.find(endtag):]
            pref += self.get_absolutepath(rel, attribute)
            
        pref += rest
#        logger.warning("{}.get_stringwithabsolutepathes(): result = '{}'".format(self._path, pref))
        return pref


    def get_absolutepath(self, relativepath, attribute=''):
        """
        Builds an absolute item path relative to the current item

        :param relativepath: string with the relative item path
        :param attribute: string with the name of the item's attribute, which contains the relative path (for log entries)
        
        :return: string with the absolute item path
        """
        if (len(relativepath) == 0) or ((len(relativepath) > 0)  and (relativepath[0] != '.')):
            return relativepath
        relpath = relativepath.rstrip()
        rootpath = self._path

        while (len(relpath) > 0)  and (relpath[0] == '.'):
            relpath = relpath[1:]
            if (len(relpath) > 0)  and (relpath[0] == '.'):
                if rootpath.rfind('.') == -1:
                    if rootpath == '':
                        relpath = ''
                        logger.error("{}.get_absolutepath(): Relative path trying to access above root level on attribute '{}'".format(self._path, attribute))
                    else:
                        rootpath = ''
                else:
                    rootpath = rootpath[:rootpath.rfind('.')]

        if relpath != '':
            if rootpath != '':
                rootpath += '.' + relpath
            else:
                rootpath = relpath
        logger.info("{}.get_absolutepath('{}'): Result = '{}' (for attribute '{}')".format(self._path, relativepath, rootpath, attribute))
        if rootpath[-5:] == '.self':
            rootpath = rootpath.replace('.self', '')
        rootpath = rootpath.replace('.self.', '.')
        return rootpath


    def _get_attr_from_parent(self, attr):
        """
        Get value from parent

        :param attr: Get the value from this attribute of the parent item
        :return: value from attribute of parent item
        """
        pitem = self.return_parent()
        pattr_value = pitem.conf[attr]
        #        logger.warning("_get_attr_from_parent Item {}: for attr '{}'".format(self._path, attr))
        #        logger.warning("_get_attr_from_parent Item {}: for parent '{}', pattr_value '{}'".format(self._path, pitem._path, pattr_value))
        return pattr_value


    def _get_attr_from_grandparent(self, attr):
        """
        Get value from grandparent

        :param attr: Get the value from this attribute of the grandparent item
        :return: value from attribute of grandparent item
        """
        pitem = self.return_parent()
        gpitem = pitem.return_parent()
        gpattr_value = pitem.conf[attr]
#        logger.warning("_get_attr_from_parent Item {}: for attr '{}'".format(self._path, attr))
#        logger.warning("_get_attr_from_parent Item {}: for grandparent '{}', gpattr_value '{}'".format(self._path, gpitem._path, gpattr_value))
        return gpattr_value


    def _build_trigger_condition_eval(self, trigger_condition):
        """
        Build conditional eval expression from trigger_condition attribute

        :param trigger_condition: list of condition dicts
        :return:
        """
        wrk_eval = []
        for or_cond in trigger_condition:
            for ckey in or_cond:
                if ckey.lower() == 'value':
                    pass
                else:
                    and_cond = []
                    for cond in or_cond[ckey]:
                        wrk = cond
                        if (wrk.find('=') != -1) and (wrk.find('==') == -1) and \
                                (wrk.find('<=') == -1) and (wrk.find('>=') == -1) and \
                                (wrk.find('=<') == -1) and (wrk.find('=>') == -1):
                            wrk = wrk.replace('=', '==')

                        p = wrk.lower().find('true')
                        if p != -1:
                            wrk = wrk[:p]+'True'+wrk[p+4:]
                        p = wrk.lower().find('false')
                        if p != -1:
                            wrk = wrk[:p]+'False'+wrk[p+5:]

                        # expand relative item pathes
                        wrk = self.get_stringwithabsolutepathes(wrk, 'sh.', '(', KEY_CONDITION)

                        and_cond.append(wrk)

                    wrk = ') and ('.join(and_cond)
                    if len(or_cond[ckey]) > 1:
                        wrk = '(' + wrk + ')'
                    wrk_eval.append(wrk)

    #                wrk_eval.append(str(or_cond[ckey]))
                    result = ') or ('.join(wrk_eval)

        if len(trigger_condition) > 1:
            result = '(' + result + ')'

        return result


    def __call__(self, value=None, caller='Logic', source=None, dest=None):
        if value is None or self._type is None:
            return self._value
        if self._eval:
            args = {'value': value, 'caller': caller, 'source': source, 'dest': dest}
            self._sh.trigger(name=self._path + '-eval', obj=self.__run_eval, value=args, by=caller, source=source, dest=dest)
        else:
            self.__update(value, caller, source, dest)

    def __iter__(self):
        for child in self.__children:
            yield child

    def __setitem__(self, item, value):
        vars(self)[item] = value

    def __getitem__(self, item):
        return vars(self)[item]

    def __bool__(self):
        return bool(self._value)

    def __str__(self):
        return self._name

    def __repr__(self):
        return "Item: {}".format(self._path)


    def _init_prerun(self):
        """
        Build eval expressions from special functions and triggers before first run

        Called from load_itemdefinitions
        """
        if self._trigger:
            # Only if item has an eval_trigger
            _items = []
            for trigger in self._trigger:
                _items.extend(_items_instance.match_items(trigger))
            for item in _items:
                if item != self:  # prevent loop
                        item._items_to_trigger.append(self)
            if self._eval:
                # Build eval statement from trigger items (joined by given function)
                items = ['sh.' + x.id() + '()' for x in _items]
                if self._eval == 'and':
                    self._eval = ' and '.join(items)
                elif self._eval == 'or':
                    self._eval = ' or '.join(items)
                elif self._eval == 'sum':
                    self._eval = ' + '.join(items)
                elif self._eval == 'avg':
                    self._eval = '({0})/{1}'.format(' + '.join(items), len(items))
                elif self._eval == 'max':
                    self._eval = 'max({0})'.format(','.join(items))
                elif self._eval == 'min':
                    self._eval = 'min({0})'.format(','.join(items))


    def _init_run(self):
        """
        Run initial eval to set an initial value for the item

        Called from load_itemdefinitions
        """
        if self._trigger:
            # Only if item has an eval_trigger
            if self._eval:
                # Only if item has an eval expression
                self._sh.trigger(name=self._path, obj=self.__run_eval, by='Init', value={'value': self._value, 'caller': 'Init'})


    def __run_eval(self, value=None, caller='Eval', source=None, dest=None):
        """
        evaluate the 'eval' entry of the actual item
        """
        if self._eval:
            # Test if a conditional trigger is defined
            if self._trigger_condition is not None:
#                logger.warning("Item {}: Evaluating trigger condition {}".format(self._path, self._trigger_condition))
                try:
                    sh = self._sh
                    cond = eval(self._trigger_condition)
                    logger.warning("Item {}: Condition result '{}' evaluating trigger condition {}".format(self._path, cond, self._trigger_condition))
                except Exception as e:
                    logger.warning("Item {}: problem evaluating trigger condition {}: {}".format(self._path, self._trigger_condition, e))
                    return
            else:
                cond = True

            if cond == True:
    #            if self._path == 'wohnung.flur.szenen_helper':
    #                logger.info("__run_eval: item = {}, value = {}, self._eval = {}".format(self._path, value, self._eval))
                sh = self._sh  # noqa
                shtime = self.shtime
                try:
                    value = eval(self._eval)
                except Exception as e:
                    logger.warning("Item {}: problem evaluating {}: {}".format(self._path, self._eval, e))
                else:
                    if value is None:
                        logger.debug("Item {}: evaluating {} returns None".format(self._path, self._eval))
                    else:
                        if self._path == 'wohnung.flur.szenen_helper':
                            logger.info("__run_eval: item = {}, value = {}".format(self._path, value))
                        self.__update(value, caller, source, dest)


    # New for on_update / on_change
    def _run_on_xxx(self, path, value, on_dest, on_eval, attr='?'):
        """
        common method for __run_on_update and __run_on_change
        """
        if self._path == 'wohnung.flur.szenen_helper':
            logger.info("_run_on_xxx: item = {}, value = {}".format(self._path, value))
        sh = self._sh
        logger.info("Item {}: '{}' evaluating {} = {}".format(self._path, attr, on_dest, on_eval))
        try:
            dest_value = eval(on_eval)       # calculate to test if expression computes and see if it computes to None
        except Exception as e:
            logger.warning("Item {}: '{}' item-value='{}' problem evaluating {}: {}".format(self._path, attr, value, on_eval, e))
        else:
            if dest_value is not None:
                # expression computes and does not result in None
                if on_dest != '':
                    dest_item = _items_instance.return_item(on_dest)
                    if dest_item is not None:
                        dest_item.__update(dest_value, caller=attr, source=self._path)
                        logger.debug(" - : '{}' finally evaluating {} = {}, result={}".format(attr, on_dest, on_eval, dest_value))
                    else:
                        logger.error(" - : '{}' has not found dest_item {} = {}, result={}".format(attr, on_dest, on_eval, dest_value))
                else:
                    dummy = eval(on_eval)
                    logger.debug(" - : '{}' finally evaluating {}, result={}".format(attr, on_eval, dest_value))
            else:
                logger.debug(" - : '{}' {} not set (cause: eval=None)".format(attr, on_dest))
                pass
            
    
    def __run_on_update(self, value=None):
        """
        evaluate all 'on_update' entries of the actual item
        """
        if self._on_update:
            sh = self._sh  # noqa
#            logger.info("Item {}: 'on_update' evaluating {} = {}".format(self._path, self._on_update_dest_var, self._on_update))
            for on_update_dest, on_update_eval in zip(self._on_update_dest_var, self._on_update):
                self._run_on_xxx(self._path, value, on_update_dest, on_update_eval, 'on_update')


    def __run_on_change(self, value=None):
        """
        evaluate all 'on_change' entries of the actual item
        """
        if self._on_change:
            sh = self._sh  # noqa
#            logger.info("Item {}: 'on_change' evaluating lists {} = {}".format(self._path, self._on_change_dest_var, self._on_change))
            for on_change_dest, on_change_eval in zip(self._on_change_dest_var, self._on_change):
                self._run_on_xxx(self._path, value, on_change_dest, on_change_eval, 'on_change')


    def __trigger_logics(self):
        for logic in self.__logics_to_trigger:
            logic.trigger('Item', self._path, self._value)

    def __update(self, value, caller='Logic', source=None, dest=None):
        try:
            value = self.cast(value)
        except:
            try:
                logger.warning("Item {}: value {} does not match type {}. Via {} {}".format(self._path, value, self._type, caller, source))
            except:
                pass
            return
        self._lock.acquire()
        _changed = False
        self.__updated_by = "{0}:{1}".format(caller, source)
        if value != self._value:
            _changed = True
            self.__prev_value = self._value
            self._value = value
            self.__prev_change = self.__last_change
            self.__last_change = self.shtime.now()
            self.__changed_by = "{0}:{1}".format(caller, source)
            if caller != "fader":
                self._fading = False
                self._lock.notify_all()
                self._change_logger("Item {} = {} via {} {} {}".format(self._path, value, caller, source, dest))
                if self._log_change_logger is not None:
                    log_src = ''
                    if source is not None:
                        log_src += ' (' + source + ')'
                    log_dst = ''
                    if dest is not None:
                        log_dst += ', dest: ' + dest
                    self._log_change_logger.info("Item Change: {} = {}  -  caller: {}{}{}".format(self._path, value, caller, log_src, log_dst))
        self._lock.release()
        # ms: call run_on_update() from here
        self.__run_on_update(value)
        if _changed or self._enforce_updates or self._type == 'scene':
            self.__prev_update = self.__last_update
            self.__last_update = self.shtime.now()
            # ms: call run_on_change() from here
            self.__run_on_change(value)
            for method in self.__methods_to_trigger:
                try:
                    method(self, caller, source, dest)
                except Exception as e:
                    logger.exception("Item {}: problem running {}: {}".format(self._path, method, e))
            if self._threshold and self.__logics_to_trigger:
                if self.__th_crossed and self._value <= self.__th_low:  # cross lower bound
                    self.__th_crossed = False
                    self.__trigger_logics()
                elif not self.__th_crossed and self._value >= self.__th_high:  # cross upper bound
                    self.__th_crossed = True
                    self.__trigger_logics()
            elif self.__logics_to_trigger:
                self.__trigger_logics()
            for item in self._items_to_trigger:
                args = {'value': value, 'source': self._path}
                self._sh.trigger(name=item.id(), obj=item.__run_eval, value=args, by=caller, source=source, dest=dest)
        if _changed and self._cache and not self._fading:
            try:
                _cache_write(self._cache, self._value)
            except Exception as e:
                logger.warning("Item: {}: could update cache {}".format(self._path, e))
        if self._autotimer and caller != 'Autotimer' and not self._fading:

            _time, _value = self._autotimer[0]
            compat = self._autotimer[1]
            if self._autotimer[2]:
                try:
                    _time = eval('self._sh.'+self._autotimer[2]+'()')
                except:
                    logger.warning("Item '{}': Attribute 'autotimer': Item '{}' does not exist".format(self._path, self._autotimer[2]))
            if self._autotimer[3]:
                try:
                    _value = self._castvalue_to_itemtype(eval('self._sh.'+self._autotimer[3]+'()'), compat)
                except:
                    logger.warning("Item '{}': Attribute 'autotimer': Item '{}' does not exist".format(self._path, self._autotimer[3]))
            self._autotimer[0] = (_time, _value)     # for display of active/last timer configuration in backend

            next = self.shtime.now() + datetime.timedelta(seconds=_time)
            self._sh.scheduler.add(self._itemname_prefix+self.id() + '-Timer', self.__call__, value={'value': _value, 'caller': 'Autotimer'}, next=next)


    def add_logic_trigger(self, logic):
        self.__logics_to_trigger.append(logic)

    def remove_logic_trigger(self, logic):
        self.__logics_to_trigger.remove(logic)

    def get_logic_triggers(self):
        return self.__logics_to_trigger

    def add_method_trigger(self, method):
        self.__methods_to_trigger.append(method)

    def remove_method_trigger(self, method):
        self.__methods_to_trigger.remove(method)

    def get_method_triggers(self):
        return self.__methods_to_trigger

    def age(self):
        delta = self.shtime.now() - self.__last_change
        return delta.total_seconds()

    def update_age(self):
        delta = self.shtime.now() - self.__last_update
        return delta.total_seconds()

    def autotimer(self, time=None, value=None, compat=ATTRIB_COMPAT_V12):
        if time is not None and value is not None:
            self._autotimer = [(time, value), compat, None, None]
        else:
            self._autotimer = False

    def changed_by(self):
        return self.__changed_by

    def updated_by(self):
        return self.__updated_by

    def fade(self, dest, step=1, delta=1):
        dest = float(dest)
        self._sh.trigger(self._path, _fadejob, value={'item': self, 'dest': dest, 'step': step, 'delta': delta})

    def id(self):
        return self._path

    def last_change(self):
        return self.__last_change

    def last_update(self):
        return self.__last_update

    def prev_age(self):
        delta = self.__last_change - self.__prev_change
        return delta.total_seconds()

    def prev_update_age(self):
        delta = self.__last_update - self.__prev_update
        return delta.total_seconds()

    def prev_change(self):
        return self.__prev_change

    def prev_update(self):
        return self.__prev_update

    def prev_value(self):
        return self.__prev_value

    def remove_timer(self):
        self._sh.scheduler.remove(self._itemname_prefix+self.id() + '-Timer')

    def return_children(self):
        for child in self.__children:
            yield child

    def return_parent(self):
        return self.__parent

    def set(self, value, caller='Logic', source=None, dest=None, prev_change=None, last_change=None):
        try:
            value = self.cast(value)
        except:
            try:
                logger.warning("Item {}: value {} does not match type {}. Via {} {}".format(self._path, value, self._type, caller, source))
            except:
                pass
            return
        self._lock.acquire()
        self._value = value
        if prev_change is None:
            self.__prev_change = self.__last_change
        else:
            self.__prev_change = prev_change
        if last_change is None:
            self.__last_change = self.shtime.now()
        else:
            self.__last_change = last_change
        self.__changed_by = "{0}:{1}".format(caller, None)
        self.__updated_by = "{0}:{1}".format(caller, None)
        self._lock.release()
        self._change_logger("Item {} = {} via {} {} {}".format(self._path, value, caller, source, dest))

    def timer(self, time, value, auto=False, compat=ATTRIB_COMPAT_DEFAULT):
        time = self._cast_duration(time)
        value = self._castvalue_to_itemtype(value, compat)
        if auto:
            caller = 'Autotimer'
            self._autotimer = [(time, value), compat, None, None]
        else:
            caller = 'Timer'
        next = self.shtime.now() + datetime.timedelta(seconds=time)
        self._sh.scheduler.add(self._itemname_prefix+self.id() + '-Timer', self.__call__, value={'value': value, 'caller': caller}, next=next)

    def type(self):
        return self._type

    def get_children_path(self):
        return [item._path
                for item in self.__children]

    def jsonvars(self):
        """
        Translation method from object members to json
        :return: Key / Value pairs from object members
        """
        return { "id": self._path,
                 "name": self._name,
                 "value" : self._value,
                 "type": self._type,
                 "attributes": self.conf,
                 "children": self.get_children_path() }
                 
# alternative method to get all class members
#    @staticmethod
#    def get_members(instance):
#        return {k: v
#                for k, v in vars(instance).items()
#                if str(k) in ["_value", "conf"] }
#                #if not str(k).startswith('_')}

    def to_json(self):
       return json.dumps(self.jsonvars(), sort_keys=True, indent=2)



#####################################################################
# Cast Methods
#####################################################################

def _cast_str(value):
    if isinstance(value, str):
        return value
    else:
        raise ValueError


def _cast_list(value):
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except Exception as e:
            value = value.replace("'",'"')
            value = json.loads(value)
    if isinstance(value, list):
        return value
    else:
        raise ValueError


def _cast_dict(value):
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except Exception as e:
            value = value.replace("'",'"')
            value = json.loads(value)
    if isinstance(value, dict):
        return value
    else:
        raise ValueError


def _cast_foo(value):
    return value


# TODO: Candidate for Utils.to_bool()
# write testcase and replace
# -> should castng be restricted like this or handled exactly like Utils.to_bool()?
#    Example: _cast_bool(2) is False, Utils.to_bool(2) is True

def _cast_bool(value):
    if type(value) in [bool, int, float]:
        if value in [False, 0]:
            return False
        elif value in [True, 1]:
            return True
        else:
            raise ValueError
    elif type(value) in [str, str]:
        if value.lower() in ['0', 'false', 'no', 'off', '']:
            return False
        elif value.lower() in ['1', 'true', 'yes', 'on']:
            return True
        else:
            raise ValueError
    else:
        raise TypeError


def _cast_scene(value):
    return int(value)


def _cast_num(value):
    """
    cast a passed value to int or float

    :param value: numeric value to be casted, passed as str, float or int
    :return: numeric value, passed as int or float
    """
    if isinstance(value, str):
        value = value.strip()
    if value == '':
        return 0
    if isinstance(value, float):
        return value
    try:
        return int(value)
    except:
        pass
    try:
        return float(value)
    except:
        pass
    raise ValueError


#####################################################################
# Methods for handling of duration_value strings
#####################################################################

def _split_duration_value_string(value): 
    """
    splits a duration value string into its thre components
    
    components are:
    - time
    - value
    - compat

    :param value: raw attribute string containing duration, value (and compatibility)
    :return: three strings, representing time, value and compatibility attribute
    """
    time, __, value = value.partition('=')
    value, __, compat = value.partition('=')
    time = time.strip()
    value = value.strip()
    # remove quotes, if present
    if value != '' and ((value[0] == "'" and value[-1] == "'") or (value[0] == '"' and value[-1] == '"')):
        value = value[1:-1]
    compat = compat.strip().lower()
    if compat == '':
        compat = ATTRIB_COMPAT_DEFAULT
    return (time, value, compat)


def _join_duration_value_string(time, value, compat=''): 
    """
    joins a duration value string from its thre components
    
    components are:
    - time
    - value
    - compat

    :param time: time (duration) parrt for the duration_value_string
    :param value: value (duration) parrt for the duration_value_string
    """
    result = str(time)
    if value != '' or compat != '':
        result = result + ' ='
        if value != '':
            result = result + ' ' + value
        if compat != '':
           result = result + ' = ' + compat
    return result
    
    
#####################################################################
# Cache Methods
#####################################################################

def json_serialize(obj):
    """helper method to convert values to json serializable formats"""
    import datetime
    if isinstance(obj, datetime.datetime):
        return obj.isoformat()
    if isinstance(obj, datetime.date):
        return obj.isoformat()
    raise TypeError("Type not serializable")

def json_obj_hook(json_dict):
    """helper method for json deserialization"""
    import dateutil
    for (key, value) in json_dict.items():
        try:
            json_dict[key] = dateutil.parser.parse(value)
        except Exception as e :
            pass
    return json_dict


def _cache_read(filename, tz, cformat=CACHE_FORMAT):
    ts = os.path.getmtime(filename)
    dt = datetime.datetime.fromtimestamp(ts, tz)
    value = None

    if cformat == CACHE_PICKLE:
        with open(filename, 'rb') as f:
            value = pickle.load(f)

    elif cformat == CACHE_JSON:
        with open(filename, 'r') as f:
            value = json.load(f, object_hook=json_obj_hook)

    return (dt, value)

def _cache_write(filename, value, cformat=CACHE_FORMAT):
    try:
        if cformat == CACHE_PICKLE:
            with open(filename, 'wb') as f:
                pickle.dump(value,f)

        elif cformat == CACHE_JSON:
            with open(filename, 'w') as f:
                json.dump(value,f, default=json_serialize)
    except IOError:
        logger.warning("Could not write to {}".format(filename))


#####################################################################
# Fade Method
#####################################################################
def _fadejob(item, dest, step, delta):
    if item._fading:
        return
    else:
        item._fading = True
    if item._value < dest:
        while (item._value + step) < dest and item._fading:
            item(item._value + step, 'fader')
            item._lock.acquire()
            item._lock.wait(delta)
            item._lock.release()
    else:
        while (item._value - step) > dest and item._fading:
            item(item._value - step, 'fader')
            item._lock.acquire()
            item._lock.wait(delta)
            item._lock.release()
    if item._fading:
        item._fading = False
        item(dest, 'Fader')


