from aplustools.io.environment import auto_repr_with_privates as _auto_repr_with_privates
# from .db import DatabaseAccess as _DatabaseAccess  # Circular import
from typing import Literal as _Literal
import time as _time


class BaseDBObj:
    """A object for the Document table."""
    def __init__(self, nb: int, table: str, excludes: list, _snap_shot: dict, _main_contact):
        self.nb = nb
        self._main_contact = _main_contact
        self._table = table
        self._excludes = excludes
        self._snap_shot = _snap_shot
        self._edit_mode_engaged = False
        self._edit_lock_acquired = False

    def _get_value(self, key):
        if self._snap_shot[key] == "":
            self.update()
        return self._snap_shot[key]

    def _edit_value(self, key, value):
        if not self._edit_mode_engaged:
            raise ValueError("Please engage edit mode first before trying to change any values.")

        self._snap_shot[key] = value

    def update(self):
        raise NotImplementedError("This method needs to be implemented individually")

    def _callback(self):
        self._edit_lock_acquired = True

    def edit(self):
        self._edit_mode_engaged = True
        self._main_contact.edit_lock_manager.stage_changes(self.nb, self._table, self._callback)

        while not self._edit_lock_acquired:
            _time.sleep(0.1)


@_auto_repr_with_privates
class Document(BaseDBObj):
    """A object for the Document table."""
    def __init__(self, nb: int, _main_contact):
        super().__init__(nb, "Documents", ["cases"], {
            "name": "",
            "description": "",
            "notes": [""],
            "path": "",
            "cases": []
        }, _main_contact)

    @property
    def name(self):
        return self._get_value("name")

    @name.setter
    def name(self, value: str):
        self._edit_value("name", value)  # Change value

    @property
    def description(self):
        return self._get_value("description")

    @description.setter
    def description(self, value: str):
        self._edit_value("description", value)  # Change value

    @property
    def notes(self):
        return self._get_value("notes")

    @notes.setter
    def notes(self, value: str):
        self._edit_value("notes", value)  # Change value

    @property
    def path(self):
        return self._get_value("path")

    @path.setter
    def path(self, value: str):
        self._edit_value("path", value)  # Change value

    @property
    def cases(self):
        return self._get_value("cases")

    def update(self):  # Refresh snapshot
        self._snap_shot = {k: v[0] if len(v) == 1 else v for k, v in
                           zip(
                               self._snap_shot.keys(),
                               self._main_contact.get_documents(
                                   self.nb, *self._snap_shot.keys()))
                           }

    def finalize_edit(self):
        self._edit_mode_engaged = False
        self._main_contact.edit_lock_manager.release_edit_lock(self.nb, self._table)
        snap_copy = self._snap_shot.copy()

        for exc in self._excludes:
            del snap_copy[exc]
        snap_copy["notes"] = '\n'.join(snap_copy["notes"])
        self._main_contact.update_documents(self.nb, **snap_copy)
        self._edit_lock_acquired = False

    def delete(self):
        self._main_contact.delete_document(self.nb)

    @classmethod
    def new(cls, _main_access, name: str, description: str = "", notes: list = None,
            current_path: str = ""):
        nb = _main_access.add_document(name, description, '\n'.join(notes), current_path)
        return cls(nb, _main_access)


@_auto_repr_with_privates
class Case(BaseDBObj):
    def __init__(self, nb: int, _main_contact):
        super().__init__(nb, "Cases", [], {
            "name": "",
            "description": "",
            "notes": [""],
            "persons": [],
            "documents": []
        }, _main_contact)

    @property
    def name(self):
        return self._get_value("name")

    @name.setter
    def name(self, value: str):
        self._edit_value("name", value)

    @property
    def description(self):
        return self._get_value("description")

    @description.setter
    def description(self, value: str):
        self._edit_value("description", value)

    @property
    def notes(self):
        return self._get_value("notes")

    @notes.setter
    def notes(self, values: list):
        self._edit_value("notes", values)

    @property
    def persons(self):
        return self._get_value("persons")

    @persons.setter
    def persons(self, values: list):
        self._edit_value("persons", values)

    @property
    def documents(self):
        return self._get_value("documents")

    @documents.setter
    def documents(self, values: list):
        self._edit_value("documents", values)

    def update(self):  # Refresh snapshot
        self._snap_shot = {k: v[0] if len(v) == 1 else v for k, v in
                           zip(
                               self._snap_shot.keys(),
                               self._main_contact.get_cases(
                                   self.nb, *self._snap_shot.keys()))
                           }

    def finalize_edit(self):
        self._edit_mode_engaged = False
        self._main_contact.edit_lock_manager.release_edit_lock(self.nb, self._table)
        snap_copy = self._snap_shot.copy()

        for exc in self._excludes:
            del snap_copy[exc]
        snap_copy["notes"] = '\n'.join(snap_copy["notes"])
        self._main_contact.update_cases(self.nb, **snap_copy)
        self._edit_lock_acquired = False

    def delete(self):
        self._main_contact.delete_case(self.nb)

    @classmethod
    def new(cls, _main_access, name: str, description: str = "", notes: str = "",
            persons: list[tuple[int, int, int]] = None, documents: list = None):
        nb = _main_access.add_case(name, description, '\n'.join(notes), persons, documents)
        return cls(nb, _main_access)


@_auto_repr_with_privates
class Person(BaseDBObj):
    def __init__(self, nb: int, _main_contact):
        super().__init__(nb, "Persons", ["cases"], {"first_name": "",
                                                    "last_name": "",
                                                    "address": "",
                                                    "birth_date": "",
                                                    "contact_info": "",
                                                    "gender": "",
                                                    "description": "",
                                                    "notes": [],
                                                    "can_be_lawyer": 0,
                                                    "cases": []}, _main_contact)

    @property
    def first_name(self):
        return self._get_value("first_name")

    @first_name.setter
    def first_name(self, value: str):
        self._edit_value("first_name", value)

    @property
    def last_name(self):
        return self._get_value("last_name")

    @last_name.setter
    def last_name(self, value: str):
        self._edit_value("last_name", value)

    @property
    def address(self):
        return self._get_value("address")

    @address.setter
    def address(self, value: str):
        self._edit_value("address", value)

    @property
    def birth_date(self):
        return self._get_value("birth_date")

    @birth_date.setter
    def birth_date(self, value: str):
        self._edit_value("birth_date", value)

    @property
    def contact_info(self):
        return self._get_value("contact_info")

    @contact_info.setter
    def contact_info(self, value: str):
        self._edit_value("contact_info", value)

    @property
    def gender(self):
        return self._get_value("gender")

    @gender.setter
    def gender(self, value: _Literal["Male", "Female", "Other"]):
        self._edit_value("gender", value)

    @property
    def description(self):
        return self._get_value("description")

    @description.setter
    def description(self, value: str):
        self._edit_value("description", value)

    @property
    def notes(self):
        return self._get_value("notes")

    @notes.setter
    def notes(self, values: list):
        self._edit_value("notes", values)

    @property
    def can_be_lawyer(self):
        return self._get_value("can_be_lawyer") == 1

    @can_be_lawyer.setter
    def can_be_lawyer(self, value: bool):
        self._edit_value("can_be_lawyer", 1 if value else 0)

    @property
    def cases(self):
        return self._get_value("cases")

    @cases.setter
    def cases(self, values: list):
        self._edit_value("cases", values)

    def update(self):  # Refresh snapshot
        self._snap_shot = {k: v[0] if len(v) == 1 else v for k, v in
                           zip(
                               self._snap_shot.keys(),
                               self._main_contact.get_persons(
                                   self.nb, *self._snap_shot.keys()))
                           }

    def finalize_edit(self):
        self._edit_mode_engaged = False
        self._main_contact.edit_lock_manager.release_edit_lock(self.nb, self._table)
        snap_copy = self._snap_shot.copy()

        for exc in self._excludes:
            del snap_copy[exc]
        snap_copy["notes"] = '\n'.join(snap_copy["notes"])
        self._main_contact.update_persons(self.nb, **snap_copy)
        self._edit_lock_acquired = False

    def delete(self):
        self._main_contact.delete_person(self.nb)

    @classmethod
    def new(cls, _main_access, last_name: str, first_name: str, address: str, birth_date: str,
            contact_info: str, gender: _Literal["Male", "Female", "Other"], description: str = "", notes: list = None,
            can_be_lawyer: bool = False):
        nb = _main_access.add_person(last_name, first_name, address, birth_date, contact_info, gender, description,
                                     '\n'.join(notes), can_be_lawyer)
        return cls(nb, _main_access)
