# -*- coding: utf8 -*-

import struct
import time


class TZInfo:
    BASEDIR = "/usr/share/zoneinfo"
    HEADER_LEN = 44
    HEADER_UNPACK_FMT = "!4sc15xIIIIII"

    def __init__(self, tz):
        self.tz = tz
        self.basedir = TZInfo.BASEDIR
        self.version = 0
        self.isutcnt = 0
        self.isstdcnt = 0
        self.leapcnt = 0
        self.timecnt = 0
        self.typecnt = 0
        self.charcnt = 0
        self.transition_times = None
        self.transition_types = None
        self.local_time_type_records = None
        self.time_zone_designations = None
        self.leap_seconds_records = None
        self.standard_wall_indicators = None
        self.ut_local_indicators = None
        self.tz_strings = None

    def __str__(self):
        return "time zone: {}\n" \
               "version: {}, isutcnt: {}, isstdcnt: {}, leapcnt: {}, timecnt: {}, typecnt: {}, charcnt: {}\n" \
               "transition times: {}\n" \
               "transition types: {}\n" \
               "local time type records: {}\n" \
               "time zone designations: {}\n" \
               "leap-second records: {}\n" \
               "standard/wall indicators: {}\n" \
               "UT/local indicators: {}\n" \
               "tz_strings: {}".format(
            self.tz,
            self.version,
            self.isutcnt,
            self.isstdcnt,
            self.leapcnt,
            self.timecnt,
            self.typecnt,
            self.charcnt,
            self.transition_times,
            self.transition_types,
            self.local_time_type_records,
            self.time_zone_designations,
            self.leap_seconds_records,
            self.standard_wall_indicators,
            self.ut_local_indicators,
            self.tz_strings
        )

    def read_header(self, mem):
        magic, ver, isutcnt, isstdcnt, leapcnt, timecnt, typecnt, charcnt \
            = struct.unpack(TZInfo.HEADER_UNPACK_FMT, mem)

        assert magic == b'TZif'
        assert ver == 0 or ver == b'2' or ver == b'3'
        assert isutcnt == 0 or isutcnt == typecnt
        assert isstdcnt == 0 or isstdcnt == typecnt

        self.version = ver
        self.isutcnt = isutcnt
        self.isstdcnt = isstdcnt
        self.leapcnt = leapcnt
        self.timecnt = timecnt
        self.typecnt = typecnt
        self.charcnt = charcnt

    def get_data_block_len(self, data_block_ver=1):
        if data_block_ver == 1:
            TIME_SIZE = 4
        else:
            TIME_SIZE = 8

        data_block_len = self.timecnt * TIME_SIZE  # transition times
        data_block_len += self.timecnt  # transition types
        data_block_len += self.typecnt * 6  # local time type records
        data_block_len += self.charcnt  # time zone designations
        data_block_len += self.leapcnt * (TIME_SIZE + 4)  # leap-second records
        data_block_len += self.isstdcnt  # standard/wall indicators
        data_block_len += self.isutcnt  # UT/local indicators

        return data_block_len

    def read_data_block(self, mem):
        if self.version == 0:
            TIME_SIZE = 4
        else:
            TIME_SIZE = 8

        mem_idx = 0

        if self.timecnt:
            if self.version == 0:
                fmt = "!{}l".format(self.timecnt)
            else:
                fmt = "!{}q".format(self.timecnt)
            self.transition_times = struct.unpack(fmt, mem[0:self.timecnt * TIME_SIZE])

            mem_idx += self.timecnt * TIME_SIZE
            self.transition_types = struct.unpack("{}B".format(self.timecnt),
                                                  mem[mem_idx:mem_idx + self.timecnt])
            mem_idx += self.timecnt

        if self.typecnt:
            _records = []
            local_time_type_records = mem[mem_idx:mem_idx + (self.typecnt * 6)]
            mem_idx += self.typecnt * 6

            for i in range(0, self.typecnt):
                record_idx = i * 6
                _records.append(struct.unpack("!lBB", local_time_type_records[record_idx:record_idx + 6]))

            self.local_time_type_records = tuple(_records)

        if self.charcnt:
            self.time_zone_designations = mem[mem_idx:mem_idx + self.charcnt]
            mem_idx += self.charcnt

        if self.leapcnt:
            _records = []
            leap_seconds_records = mem[mem_idx:mem_idx + (self.leapcnt * (TIME_SIZE + 4))]
            for i in range(0, self.leapcnt):
                record_idx = i * (TIME_SIZE + 4)
                if self.version == 0:
                    fmt = "!ll"
                else:
                    fmt = "!ql"
                _records.append(struct.unpack(fmt, leap_seconds_records[record_idx:record_idx + (TIME_SIZE + 4)]))
            self.leap_seconds_records = tuple(_records)
            mem_idx += self.leapcnt * (TIME_SIZE + 4)

        if self.isstdcnt:
            fmt = "{}B".format(self.isstdcnt)
            self.standard_wall_indicators = struct.unpack(fmt, mem[mem_idx:mem_idx + self.isstdcnt])
            mem_idx += self.isstdcnt

        if self.isutcnt:
            fmt = "{}B".format(self.isutcnt)
            self.ut_local_indicators = struct.unpack(fmt, mem[mem_idx:mem_idx + self.isutcnt])

    def read_footer(self, buf):
        self.tz_strings = buf[:]

    def read(self):
        with open(self.basedir + "/" + self.tz, "rb") as f:
            buf = f.read()

        assert len(buf) > TZInfo.HEADER_LEN

        begin = 0
        end = TZInfo.HEADER_LEN

        self.read_header(buf[begin:end])
        begin = end
        end += self.get_data_block_len()

        if self.version == 0:
            self.read_data_block(buf[begin:end])
        else:
            begin = end
            end += TZInfo.HEADER_LEN
            self.read_header(buf[begin:end])
            begin = end
            end += self.get_data_block_len(self.version)
            self.read_data_block(buf[begin:end])
            begin = end
            self.read_footer(buf[begin:])

    def __search_transition_index(self, timestamp: int, begin: int, end: int):
        if timestamp >= self.transition_times[self.timecnt - 1]:
            return self.timecnt - 1

        if timestamp < self.transition_times[0]:
            return -1

        if (begin + 1) == end:
            if timestamp < self.transition_times[end]:
                return begin
            else:
                return end

        if begin == end:
            return begin

        mid = int((begin + end) / 2)

        if timestamp < self.transition_times[mid]:
            return self.__search_transition_index(timestamp, begin, mid - 1)
        elif timestamp > self.transition_times[mid]:
            return self.__search_transition_index(timestamp, mid, end)
        else:
            return mid

    def get_transition_index(self, timestamp: int):
        if self.timecnt == 0:
            return -1

        return self.__search_transition_index(timestamp, 0, self.timecnt - 1)

    def get_local_time_type(self, trans_idx: int):
        if self.timecnt == 0:
            return None

        assert 0 <= trans_idx <= (self.timecnt - 1)
        type_index = self.transition_types[trans_idx]
        assert 0 <= type_index <= (self.typecnt - 1)
        return self.local_time_type_records[type_index]

    LOCAL_TIME_TYPE_FIELD_UTOFF = 0
    LOCAL_TIME_TYPE_FIELD_ISDST = 1
    LOCAL_TIME_TYPE_FIELD_DESIG_IDX = 2

    def get_local_time_type_field(self, trans_idx: int, column: int = 0):
        assert TZInfo.LOCAL_TIME_TYPE_FIELD_UTOFF <= column <= TZInfo.LOCAL_TIME_TYPE_FIELD_DESIG_IDX
        local_time_type = self.get_local_time_type(trans_idx)
        if local_time_type is None:
            return 0
        else:
            return local_time_type[column]

    def get_transition_offset(self, trans_idx: int):
        return self.get_local_time_type_field(trans_idx, TZInfo.LOCAL_TIME_TYPE_FIELD_UTOFF)

    def get_transition_isdst(self, trans_idx: int):
        return self.get_local_time_type_field(trans_idx, TZInfo.LOCAL_TIME_TYPE_FIELD_ISDST)

    def get_transition_desig_index(self, trans_idx: int):
        return self.get_local_time_type_field(trans_idx, TZInfo.LOCAL_TIME_TYPE_FIELD_DESIG_IDX)

    @staticmethod
    def utoff_strftime(utoff: int):
        return "{}{}".format("-" if utoff < 0 else "+", time.strftime("%H:%M:%S", time.gmtime(utoff)))

