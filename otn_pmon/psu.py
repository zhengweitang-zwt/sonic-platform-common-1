##
#   Copyright (c) 2021 Alibaba Group and Accelink Technologies
#
#   Licensed under the Apache License, Version 2.0 (the "License"); you may
#   not use this file except in compliance with the License. You may obtain
#   a copy of the License at http://www.apache.org/licenses/LICENSE-2.0
#   THIS CODE IS PROVIDED ON AN *AS IS* BASIS, WITHOUT WARRANTIES OR
#   CONDITIONS OF ANY KIND, EITHER EXPRESS OR IMPLIED, INCLUDING WITHOUT
#   LIMITATION ANY IMPLIED WARRANTIES OR CONDITIONS OF TITLE, FITNESS
#   FOR A PARTICULAR PURPOSE, MERCHANTABILITY OR NON-INFRINGEMENT.
#
#   See the Apache Version 2.0 License for specific language governing
#   permissions and limitations under the License.
##

import otn_pmon.utils as utils
from otn_pmon.base import Alarm, slot_status
import otn_pmon.periph as periph
from functools import lru_cache
from otn_pmon.device.ttypes import led_color, periph_type
from otn_pmon.thrift_client import thrift_try
from swsscommon import swsscommon

@lru_cache()
class Psu(periph.Periph):
    def __init__(self, id):
        super().__init__(periph_type.PSU, id)

    def __get_psu_info(self):
        def inner(client):
            return client.get_psu_info(self.id)
        return thrift_try(inner)
    
    def __expected_psu(self, pn) :
        expected_pn = utils.get_expected_pn(self.type)
        if pn in expected_pn :
            return True
        return False

    def initialize_state(self):
        Alarm.clearAll(self.name)
        eeprom = self.get_periph_eeprom()
        psu_info = self.__get_psu_info()

        data = [
            ('part-no', eeprom.pn),
            ('serial-no', eeprom.sn),
            ('mfg-date', eeprom.mfg_date),
            ('hardware-version', eeprom.hw_ver),
            ("model_name", eeprom.model_name),
            ("parent", "CHASSIS-1"),
            ("empty", "false"),
            ('removable', "true"),
            ("mfg-name", "alibaba"),
            ("oper-status", utils.slot_status_to_oper_status(slot_status.INIT)),
            ("slot-status", slot_status._VALUES_TO_NAMES[slot_status.INIT]),
            ("ambient-temp",   str(psu_info.ambient_temp)),
            ("primary-temp",   str(psu_info.primary_temp)),
            ("secondary-temp", str(psu_info.secondary_temp)),
            ("pin",        str(psu_info.pin)),
            ("pout",       str(psu_info.pout)),
            ("fan-speed",  str(psu_info.fan)),
            ("capacity",   str(psu_info.capacity)),
        ]

        self.dbs[swsscommon.STATE_DB].set(self.table_name, self.name, data)

    def update_pm(self):
        temp = self.get_temperature()
        super().update_pm("Temperature", temp)

        psu_info = self.__get_psu_info()
        super().update_pm("InputCurrent",  psu_info.iin)
        super().update_pm("InputVoltage",  psu_info.vin)
        super().update_pm("InputPower",    psu_info.pin)
        super().update_pm("OutputCurrent", psu_info.iout)
        super().update_pm("OutputPower",   psu_info.pout)
        super().update_pm("OutputVoltage", psu_info.vout)
        pass

    def update_alarm(self):
        psu_unknown = Alarm(self.name, "CRD_UNKNOWN")
        # psu_fail = Alarm(self.name, "PSU_FAIL")
        psu_mismatch = Alarm(self.name, "PSU_MISMATCH")

        state_db = self.dbs[swsscommon.STATE_DB]
        eeprom = self.get_periph_eeprom()
        if not self.__expected_psu(eeprom.pn) :
            psu_unknown.createAndClear("PSU")
            state_db.set_field(self.table_name, self.name, "oper-status", utils.slot_status_to_oper_status(slot_status.UNKNOWN))
            state_db.set_field(self.table_name, self.name, "slot-status", slot_status._VALUES_TO_NAMES[slot_status.UNKNOWN])

        psu_info = self.__get_psu_info()
        cpc = utils.get_chassis_power_capacity()
        if cpc != psu_info.capacity :
            psu_mismatch.createAndClear("PSU")
            psu_mismatch.clearByPattern("CRD_UNKNOWN")
            state_db.set_field(self.table_name, self.name, "oper-status", utils.slot_status_to_oper_status(slot_status.MISMATCH))
            state_db.set_field(self.table_name, self.name, "slot-status", slot_status._VALUES_TO_NAMES[slot_status.MISMATCH])