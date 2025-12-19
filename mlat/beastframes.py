# -*- mode: python; indent-tabs-mode: nil -*-

# Part of mlat-server: a Mode S multilateration server
# Copyright (C) 2015  Oliver Jowett <oliver@mutability.co.uk>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Helpers to synthesize Beast-format Mode S frames from MLAT solutions."""

from bisect import bisect_left
import math

from modes import crc as modes_crc

DF18 = 'DF18'
DF18ANON = 'DF18ANON'
DF18TRACK = 'DF18TRACK'

# Lookup table for the CPR NL() function (latitude breakpoints -> number of zones)
_NL_TABLE = (
    (10.47047130, 59),
    (14.82817437, 58),
    (18.18626357, 57),
    (21.02939493, 56),
    (23.54504487, 55),
    (25.82924707, 54),
    (27.93898710, 53),
    (29.91135686, 52),
    (31.77209708, 51),
    (33.53993436, 50),
    (35.22899598, 49),
    (36.85025108, 48),
    (38.41241892, 47),
    (39.92256684, 46),
    (41.38651832, 45),
    (42.80914012, 44),
    (44.19454951, 43),
    (45.54626723, 42),
    (46.86733252, 41),
    (48.16039128, 40),
    (49.42776439, 39),
    (50.67150166, 38),
    (51.89342469, 37),
    (53.09516153, 36),
    (54.27817472, 35),
    (55.44378444, 34),
    (56.59318756, 33),
    (57.72747354, 32),
    (58.84763776, 31),
    (59.95459277, 30),
    (61.04917774, 29),
    (62.13216659, 28),
    (63.20427479, 27),
    (64.26616523, 26),
    (65.31845310, 25),
    (66.36171008, 24),
    (67.39646774, 23),
    (68.42322022, 22),
    (69.44242631, 21),
    (70.45451075, 20),
    (71.45986473, 19),
    (72.45884545, 18),
    (73.45177442, 17),
    (74.43893416, 16),
    (75.42056257, 15),
    (76.39684391, 14),
    (77.36789461, 13),
    (78.33374083, 12),
    (79.29428225, 11),
    (80.24923213, 10),
    (81.19801349, 9),
    (82.13956981, 8),
    (83.07199445, 7),
    (83.99173563, 6),
    (84.89166191, 5),
    (85.75541621, 4),
    (86.53536998, 3),
    (87.00000000, 2),
    (90.00000000, 1),
)

_NL_LATS = [row[0] for row in _NL_TABLE]
_NL_VALS = [row[1] for row in _NL_TABLE]


def _cpr_nl(lat):
    lat = abs(lat)
    idx = bisect_left(_NL_LATS, lat)
    if idx >= len(_NL_VALS):
        return 1
    return _NL_VALS[idx]


def _cpr_n(lat, odd):
    nl = _cpr_nl(lat) - odd
    return 1 if nl < 1 else nl


def _cpr_mod(value, modulus):
    remainder = math.fmod(value, modulus)
    if remainder < 0:
        remainder += modulus
    return remainder


def _cpr_encode(lat, lon, odd):
    nb = 1 << 17
    dlat = 360.0 / (59 if odd else 60)
    yz = int(math.floor(nb * (_cpr_mod(lat, dlat) / dlat) + 0.5))

    rlat = dlat * (yz / nb + math.floor(lat / dlat))
    dlon = 360.0 / _cpr_n(rlat, odd)
    xz = int(math.floor(nb * (_cpr_mod(lon, dlon) / dlon) + 0.5))

    return yz & 0x1FFFF, xz & 0x1FFFF


def _encode_altitude(feet):
    if feet is None:
        return 0

    index = int((feet + 1012.5) / 25)
    if index < 0:
        index = 0
    elif index > 0x7FF:
        index = 0x7FF

    return ((index & 0x7F0) << 1) | 0x010 | (index & 0x00F)


def _encode_velocity(knots, supersonic):
    if knots is None:
        return 0

    sign = 0
    if knots < 0:
        sign = 0x400
        knots = -knots

    if supersonic:
        knots /= 4

    value = int(knots + 1.5)
    if value > 1023:
        value = 1023
    return value | sign


def _encode_vrate(fpm):
    if fpm is None:
        return 0

    sign = 0
    if fpm < 0:
        sign = 0x200
        fpm = -fpm

    value = int(fpm / 64 + 1.5)
    if value > 511:
        value = 511
    return value | sign


def _apply_crc(frame):
    parity = modes_crc.parity(frame[:11])
    frame[11] = (parity >> 16) & 0xFF
    frame[12] = (parity >> 8) & 0xFF
    frame[13] = parity & 0xFF
    return frame


def _make_frame_prefix(df, anonymous=False, track=False):
    if df == DF18:
        return ((18 << 3) | 2, 0)
    if df == DF18ANON:
        return ((18 << 3) | 5, 0)
    if df == DF18TRACK:
        return ((18 << 3) | 2, 1)
    raise ValueError('Unsupported DF {0}'.format(df))


def make_position_frame_pair(addr, lat, lon, altitude_ft, df=DF18):
    ealt = _encode_altitude(altitude_ft)
    even_lat, even_lon = _cpr_encode(lat, lon, False)
    odd_lat, odd_lon = _cpr_encode(lat, lon, True)

    return (
        _make_position_frame(18, addr, even_lat, even_lon, ealt, False, df),
        _make_position_frame(18, addr, odd_lat, odd_lon, ealt, True, df)
    )


def make_altitude_only_frame(addr, altitude_ft, df=DF18):
    return _make_position_frame(0, addr, 0, 0, _encode_altitude(altitude_ft), False, df)


def _make_position_frame(metype, addr, elat, elon, ealt, oddflag, df):
    prefix, imf = _make_frame_prefix(df)
    frame = bytearray(14)
    frame[0] = prefix
    frame[1] = (addr >> 16) & 0xFF
    frame[2] = (addr >> 8) & 0xFF
    frame[3] = addr & 0xFF
    frame[4] = (metype << 3) | imf
    frame[5] = (ealt >> 4) & 0xFF
    frame[6] = (ealt & 0x0F) << 4
    if oddflag:
        frame[6] |= 0x04
    frame[6] |= (elat >> 15) & 0x03
    frame[7] = (elat >> 7) & 0xFF
    frame[8] = (elat & 0x7F) << 1
    frame[8] |= (elon >> 16) & 0x01
    frame[9] = (elon >> 8) & 0xFF
    frame[10] = elon & 0xFF
    return _apply_crc(frame)


def make_velocity_frame(addr, nsvel_knots, ewvel_knots, vrate_fpm, df=DF18):
    velocities = []
    if nsvel_knots is not None:
        velocities.append(abs(nsvel_knots))
    if ewvel_knots is not None:
        velocities.append(abs(ewvel_knots))
    supersonic = any(v > 1000 for v in velocities)
    e_ns = _encode_velocity(nsvel_knots, supersonic)
    e_ew = _encode_velocity(ewvel_knots, supersonic)
    e_vr = _encode_vrate(vrate_fpm)

    prefix, imf = _make_frame_prefix(df)
    frame = bytearray(14)
    frame[0] = prefix
    frame[1] = (addr >> 16) & 0xFF
    frame[2] = (addr >> 8) & 0xFF
    frame[3] = addr & 0xFF
    frame[4] = (19 << 3) | (2 if supersonic else 1)
    frame[5] = (imf << 7) | ((e_ew >> 8) & 0x07)
    frame[6] = e_ew & 0xFF
    frame[7] = (e_ns >> 3) & 0xFF
    frame[8] = ((e_ns & 0x07) << 5) | 0x10 | ((e_vr >> 6) & 0x0F)
    frame[9] = (e_vr & 0x3F) << 2
    frame[10] = 0
    return _apply_crc(frame)
