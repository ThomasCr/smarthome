#!/usr/bin/env python3
#
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
# Copyright 2011-2014 Marcus Popp                          marcus@popp.mx
#########################################################################
#  This file is part of SmartHomeNG.    https://github.com/smarthomeNG//
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
#  along with SmartHomeNG.  If not, see <http://www.gnu.org/licenses/>.
##########################################################################

import logging
import datetime
import math

logger = logging.getLogger(__name__)

try:
    import ephem
except ImportError as e:
    ephem = None  # noqa


import dateutil.relativedelta
from dateutil.tz import tzutc


class Orb():

    def __init__(self, orb, lon, lat, elev=False):
        if ephem is None:
            logger.warning("Could not find/use ephem!")
            return
        self._obs = ephem.Observer()
        self._obs.long = str(lon)
        self._obs.lat = str(lat)
        if elev:
            self._obs.elevation = int(elev)
        if orb == 'sun':
            self._orb = ephem.Sun()
        elif orb == 'moon':
            self._orb = ephem.Moon()
            self.phase = self._phase
            self.light = self._light

    def _avoid_neverup(self, dt, date_utc, doff):
        # avoid NeverUp Error if degree offset is too high
        # Get times for noon and midnight
        originaldoff = doff
        midnight = self.midnight(0, 0, dt=dt)
        noon = self.noon(0, 0, dt=dt)
        # If the altitudes are calculated from previous or next day, set the correct day for the obeserver query
        noon = noon if noon >= date_utc else \
            self.noon(0, 0, dt=date_utc + dateutil.relativedelta.relativedelta(days=1))
        midnight = midnight if midnight >= date_utc else \
            self.midnight(0, 0, dt=date_utc - dateutil.relativedelta.relativedelta(days=1))
        # Get lowest and highest altitudes of the relevant day/night
        max_altitude = self.pos(offset=None, degree=True, dt=midnight)[1] if doff <= 0 else \
                                self.pos(offset=None, degree=True, dt=noon)[1]
        # Set observation date back to original queried date
        self._obs.date = date_utc
        # Limit degree offset to the highest or lowest possible for the given date
        doff = max(doff, max_altitude + 0.00001) if doff < 0 else min(doff, max_altitude - 0.00001) if doff > 0 else doff
        if not originaldoff == doff:
            logger.warning("Had to truncate the degree offset to {} as the sun never goes "
                           "below/above the given value {}.".format(doff, originaldoff))
        return doff

    def noon(self, doff=0, moff=0, dt=None):
        if dt is not None:
            self._obs.date = dt - dt.utcoffset()
        else:
            self._obs.date = datetime.datetime.utcnow() - dateutil.relativedelta.relativedelta(minutes=moff) + dateutil.relativedelta.relativedelta(seconds=2)
        self._obs.horizon = str(doff)
        next_transit = self._obs.next_transit(self._orb).datetime()
        next_transit = next_transit + dateutil.relativedelta.relativedelta(minutes=moff)
        return next_transit.replace(tzinfo=tzutc())

    def midnight(self, doff=0, moff=0, dt=None):
        if dt is not None:
            self._obs.date = dt - dt.utcoffset()
        else:
            self._obs.date = datetime.datetime.utcnow() - dateutil.relativedelta.relativedelta(minutes=moff) + dateutil.relativedelta.relativedelta(seconds=2)
        self._obs.horizon = str(doff)
        next_antitransit = self._obs.next_antitransit(self._orb).datetime()
        next_antitransit = next_antitransit + dateutil.relativedelta.relativedelta(minutes=moff)
        return next_antitransit.replace(tzinfo=tzutc())

    def rise(self, doff=0, moff=0, center=True, dt=None):
        # workaround if rise is 0.001 seconds in the past
        if dt is not None:
            self._obs.date = dt - dt.utcoffset()
            date_utc = (self._obs.date.datetime()).replace(tzinfo=tzutc())
        else:
            self._obs.date = datetime.datetime.utcnow() - dateutil.relativedelta.relativedelta(minutes=moff) + dateutil.relativedelta.relativedelta(seconds=2)
            date_utc = (self._obs.date.datetime()).replace(tzinfo=tzutc())
        if not doff == 0:
            doff = self._avoid_neverup(dt, date_utc, doff)
        self._obs.horizon = str(doff)
        if doff != 0:
            next_rising = self._obs.next_rising(self._orb, use_center=center).datetime()
        else:
            next_rising = self._obs.next_rising(self._orb).datetime()
        next_rising = next_rising + dateutil.relativedelta.relativedelta(minutes=moff)
        return next_rising.replace(tzinfo=tzutc())

    def set(self, doff=0, moff=0, center=True, dt=None):
        # workaround if set is 0.001 seconds in the past
        if dt is not None:
            self._obs.date = dt - dt.utcoffset()
            date_utc = (self._obs.date.datetime()).replace(tzinfo=tzutc())
        else:
            self._obs.date = datetime.datetime.utcnow() - dateutil.relativedelta.relativedelta(minutes=moff) + dateutil.relativedelta.relativedelta(seconds=2)
            date_utc = (self._obs.date.datetime()).replace(tzinfo=tzutc())
        # avoid NeverUp error
        if not doff == 0:
            doff = self._avoid_neverup(dt, date_utc, doff)
        self._obs.horizon = str(doff)
        if doff != 0:
            next_setting = self._obs.next_setting(self._orb, use_center=center).datetime()
        else:
            next_setting = self._obs.next_setting(self._orb).datetime()
        next_setting = next_setting + dateutil.relativedelta.relativedelta(minutes=moff)
        return next_setting.replace(tzinfo=tzutc())

    def pos(self, offset=None, degree=False, dt=None):  # offset in minutesA
        if dt is None:
            date = datetime.datetime.utcnow()
        else:
            date = dt.replace(tzinfo=tzutc())
        if offset:
            date += dateutil.relativedelta.relativedelta(minutes=offset)
        self._obs.date = date
        self._orb.compute(self._obs)
        if degree:
            return (math.degrees(self._orb.az), math.degrees(self._orb.alt))
        else:
            return (self._orb.az, self._orb.alt)

    def _light(self, offset=None):  # offset in minutes
        date = datetime.datetime.utcnow()
        if offset:
            date += dateutil.relativedelta.relativedelta(minutes=offset)
        self._obs.date = date
        self._orb.compute(self._obs)
        return int(round(self._orb.moon_phase * 100))

    def _phase(self, offset=None):  # offset in minutes
        date = datetime.datetime.utcnow()
        cycle = 29.530588861
        if offset:
            date += dateutil.relativedelta.relativedelta(minutes=offset)
        self._obs.date = date
        self._orb.compute(self._obs)
        last = ephem.previous_new_moon(self._obs.date)
        frac = (self._obs.date - last) / cycle
        return int(round(frac * 8))
