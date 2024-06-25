from contextlib import contextmanager as _contextmanager
from typing import Literal as _Literal
from threading import Thread, Event
import sqlite3 as _sqlite3
import random as _random
import shutil as _shutil
import time as _time
import os as _os
import re as _re

from faker import Faker as _Faker
import bcrypt as _bcrypt

from .search_engine import SearchEngine
from common.db_obj import Person as _Person, Case as _Case, Document as _Document


CWD = _os.path.abspath('./data')
WRITE_LOCK_FILE = _os.path.join(CWD, './write.lock')
READ_LOCK_FILE = _os.path.join(CWD, './read.lock')
CHANGES_LOG_FILE = _os.path.join(CWD, './changes_log.json')
DB_PATH = _os.path.join(CWD, './primary.db')


@_contextmanager
def acquire_write_lock():
    """Ensures two people don't write to or read from the database at the same time."""
    while _os.path.exists(WRITE_LOCK_FILE):
        _time.sleep(0.1)  # Wait for the lock to be released
    open(WRITE_LOCK_FILE, 'w').close()  # Create the lock file
    try:
        yield
    finally:
        if _os.path.exists(WRITE_LOCK_FILE):  # Sometimes this just isn't there, edge cases
            _os.remove(WRITE_LOCK_FILE)  # Release the lock file


@_contextmanager
def acquire_read_lock():
    """Ensures two people don't write to or read from the database at the same time."""
    while _os.path.exists(WRITE_LOCK_FILE):
        _time.sleep(0.1)  # Wait for the lock to be released
    with open(READ_LOCK_FILE, 'a') as f:
        f.write(" ")
    try:
        yield
    finally:
        with open(READ_LOCK_FILE, 'a') as f:
            f.write(" ")


class EditLockManager:
    """Ensures no two clients are editing the same row in one table"""
    def __init__(self, lock_dir='./edit_locks'):
        self.lock_dir = lock_dir
        self.cancel_event = Event()
        self.lock_thread = None

    def stage_changes(self, where: int, table: _Literal["Cases", "CasePeople", "CaseDocuments", "Persons", "Documents"],
                      callback):
        """
        Write to edit lock file which rows are affected (don't allow one row to be edited by two people at once,
        wait till it isn't being edited anymore, check every second.).
        the changes.log file is for the current changes. We also have a lock file for that called changes.lock
        that means someone is writing if it exists.
        """
        self.cancel_event = Event()
        lock_file_path = _os.path.join("./edit_locks", f'edit_lock_{table}_{where}.lock')

        # Reset the cancel event
        self.cancel_event.clear()

        # Thread target function
        def _lock_row():
            try:
                # Check if the row is already being edited
                while _os.path.exists(lock_file_path):
                    if self.cancel_event.is_set():
                        print("Edit operation canceled.")
                        return
                    print(f"Row {where} is currently being edited. Waiting...")
                    _time.sleep(1)  # Wait for 1 second before checking again

                # Create a lock file to indicate this row is being edited
                with open(lock_file_path, 'w') as lock_file:
                    lock_file.write(f'Editing {table} where ID is {where}\n')

                print(f"Row {where} is now locked for editing.")
                callback()

            finally:
                if self.cancel_event.is_set() and _os.path.exists(lock_file_path):
                    _os.remove(lock_file_path)
                    print(f"Released lock for row {where} due to cancellation.")

        # Start the thread
        self.lock_thread = Thread(target=_lock_row)
        self.lock_thread.start()

    def release_edit_lock(self, where: int,
                          table: _Literal["Cases", "CasePeople", "CaseDocuments", "Persons", "Documents"]):
        """Release the edit lock file"""
        lock_file_path = _os.path.join(self.lock_dir, f'edit_lock_{table}_{where}.lock')
        if _os.path.exists(lock_file_path):
            _os.remove(lock_file_path)
            print(f"Released lock for row {where} on {table}.")
        else:
            print(f"No lock found for row {where} on {table}.")

    def cancel_edit(self):
        """Stop waiting for a specific edit lock"""
        self.cancel_event.set()
        if self.lock_thread.is_alive():
            self.lock_thread.join()
            print("Edit operation canceled and thread joined.")


def _regexp(pattern: str, value):
    try:
        if value is None:
            return False
        if not isinstance(value, str):
            value = str(value)
        if pattern.startswith(".*") and pattern.endswith(".*"):
            new_pattern = pattern.removeprefix(".*").removesuffix(".*")
            if new_pattern.startswith("'") and new_pattern.endswith("'"):
                return _re.fullmatch(new_pattern.removeprefix("'").removesuffix("'"), value) is not None
            return _re.search(new_pattern, value, _re.IGNORECASE) is not None
        elif pattern.startswith("'") and pattern.endswith("'"):
            return _re.fullmatch(pattern.removeprefix("'").removesuffix("'"), value) is not None
        return _re.search(pattern, value) is not None
    except Exception as e:
        print(f"Error in regexp function: {e}")
        return False


class DatabaseAccess:
    """A layer between the database and app to ensure multiuser access and other features."""
    def __init__(self, db_path: str):
        self._db_path = db_path
        self._conn = _sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.create_function("REGEXP", 2, _regexp)
        self._search_engine = SearchEngine()
        self.edit_lock_manager = EditLockManager()

        if (not _os.path.exists(db_path)) or _os.path.getsize(db_path) == 0:
            self._setup_database()

    def _query(self, sql, params=()):
        with acquire_write_lock():  # Don't want to read incomplete data.
            cursor = self._conn.cursor()
            cursor.execute(sql, params)
            return cursor.fetchall()

    def _execute(self, sql, params=(), return_id: bool = False):
        with acquire_write_lock():
            cursor = self._conn.cursor()
            cursor.execute(sql, params)
            self._conn.commit()
            self._log_changes(sql, params)

            if return_id:
                return cursor.lastrowid

    def _execute_many(self, sql, params=((),)):
        with acquire_write_lock():
            cursor = self._conn.cursor()
            for param in params:
                cursor.execute(sql, param)
                self._log_changes(sql, param)
            self._conn.commit()

    @staticmethod
    def _get_affected_tables(query):
        # Patterns to match INSERT, UPDATE, DELETE statements
        insert_pattern = _re.compile(r"INSERT\s+INTO\s+([^\s(]+)", _re.IGNORECASE)
        update_pattern = _re.compile(r"UPDATE\s+(\S+)", _re.IGNORECASE)
        delete_pattern = _re.compile(r"DELETE\s+FROM\s+(\S+)", _re.IGNORECASE)

        tables = set()

        # Check for INSERT statement
        match = insert_pattern.search(query)
        if match:
            tables.add(match.group(1))

        # Check for UPDATE statement
        match = update_pattern.search(query)
        if match:
            tables.add(match.group(1))

        # Check for DELETE statement
        match = delete_pattern.search(query)
        if match:
            tables.add(match.group(1))

        return tables

    @classmethod
    def _log_changes(cls, sql, params):
        try:
            tables = set(cls._get_affected_tables(sql))
            with open(CHANGES_LOG_FILE, 'a') as log_file:
                # Tabs: Cases; People: NewLine; Document: Space
                for entry, table in zip(("\t", "\n", " "), ({"Cases", "CasePeople", "CaseDocuments"},
                                                            {"Persons"}, {"Documents"})):
                    if tables.intersection(set(table)):
                        log_file.write(entry)
        except PermissionError as e:
            print(f"PermissionError: {e}")
            cls._log_changes(sql, params)

    def _setup_database(self):
        sql_statements = [
            """
            CREATE TABLE IF NOT EXISTS Users (
                nb INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT CHECK(role IN ('Admin', 'Manager', 'Viewer')) NOT NULL
            );""",
            """
            CREATE TABLE IF NOT EXISTS Persons (
                nb INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                last_name STRING NOT NULL,
                first_name STRING NOT NULL,
                address STRING NOT NULL,
                birth_date STRING NOT NULL,
                contact_info STRING NOT NULL,
                gender STRING CHECK(gender IN ("Male", "Female", "Other")) NOT NULL,
                description TEXT NOT NULL,
                notes TEXT NOT NULL,
                can_be_lawyer INTEGER NOT NULL
            );""",
            """
            CREATE TABLE IF NOT EXISTS Cases (
                nb INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                name STRING NOT NULL UNIQUE,
                description TEXT NOT NULL,
                notes TEXT NOT NULL
            );""",
            """
            CREATE TABLE IF NOT EXISTS CasePeople (
                case_nb INTEGER NOT NULL,
                person_nb INTEGER NOT NULL,
                lawyer_nb INTEGER,
                side INTEGER CHECK(side IN (0, 1)) NOT NULL,
                has_external_lawyer INTEGER NOT NULL DEFAULT 0,
                self_represented INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (case_nb) REFERENCES Cases(nb),
                FOREIGN KEY (person_nb) REFERENCES Persons(nb),
                FOREIGN KEY (lawyer_nb) REFERENCES Persons(nb),
                PRIMARY KEY (case_nb, person_nb, lawyer_nb)
            );""",
            """
            CREATE TABLE IF NOT EXISTS Documents (
                nb INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                name STRING NOT NULL,
                description TEXT NOT NULL,
                notes TEXT NOT NULL,
                path STRING NOT NULL,
                archived INTEGER NOT NULL
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS CaseDocuments (
                case_nb INTEGER NOT NULL,
                document_nb INTEGER NOT NULL,
                FOREIGN KEY (case_nb) REFERENCES Cases(nb),
                FOREIGN KEY (document_nb) REFERENCES Documents(nb),
                PRIMARY KEY (case_nb, document_nb)
            );"""]

        for statement in sql_statements:
            self._execute(statement)
        self._insert_test_data()

    def _insert_test_data(self):
        fake = _Faker("de_DE")

        lawyers, persons = [], []
        for nb in range(1, 101):
            is_lawyer = _random.choice([0, 0, 0, 0, 0, 1])
            persons.append((fake.last_name(), fake.name(), fake.address(), fake.date_of_birth(), fake.email(),
                            _random.choice(["Male", "Female", "Other"]), fake.text(), '.\n'.join(fake.texts()), is_lawyer))
            if is_lawyer:
                lawyers.append(nb)
        self._execute_many('INSERT INTO Persons (last_name, first_name, address, birth_date, contact_info, gender, description, notes, can_be_lawyer) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)', persons)

        for case_nb in range(1, 21):
            case_name = f"Case {case_nb}"
            self._execute("INSERT INTO Cases (name, description, notes) VALUES (?, ?, ?)", (case_name, fake.text(), '\n'.join(fake.texts())))
            person_nbs = _random.sample(range(1, 101), _random.choice([2] * 10 + [3] * 8 + [4] * 4 + [5, 6]))

            a_side_num = _random.randint(1, len(person_nbs) - 1)
            a_side, b_side = person_nbs[:a_side_num], person_nbs[a_side_num:]

            document_nb = case_nb
            self._execute("INSERT INTO Documents (name, description, notes, path, archived) VALUES (?, ?, ?, ?, ?)",
                                (f"Document {document_nb}", fake.text(), '\n'.join(fake.texts()), f"./documents/case_{case_nb}.pdf", 1))
            self._execute("INSERT INTO CaseDocuments (case_nb, document_nb) VALUES (?, ?)",
                                (case_nb, document_nb))

            for aff, side in enumerate((a_side, b_side)):
                shared_lawyer_nb = _random.choice(lawyers)

                for person_nb in side:
                    self_represented = 0
                    if _random.choice([0, 1]):
                        lawyer_nb = _random.choice(lawyers)
                        if lawyer_nb == person_nb:
                            self_represented = 1
                    elif _random.choice([0, 0, 0, 0, 1]):  # Pretty foolish to self represent if you
                        self_represented = 1  # aren't a lawyer
                        lawyer_nb = person_nb
                    else:
                        lawyer_nb = shared_lawyer_nb
                    self._execute("INSERT INTO CasePeople (case_nb, person_nb, lawyer_nb, side, has_external_lawyer, self_represented) VALUES (?, ?, ?, ?, ?, ?)",
                                        (case_nb, person_nb, lawyer_nb, aff, 0, self_represented))

    def get_persons(self, number: int, *_: _Literal["last_name", "first_name", "address", "birth_date", "contact_info", "gender", "description", "notes", "can_be_lawyer", "cases"]):
        _, index = list(_), None

        if "cases" in _:
            index = _.index("cases")
            del _[index]

        if _:
            query = f"SELECT {', '.join(['p.' + attr for attr in _])} FROM Persons p WHERE p.nb = {number}"
            # print(query)
            returns = [(x,) for x in self._query(query)[0]]
        else:
            returns = []

        if index is not None:
            cases_query = f"SELECT cp.case_nb FROM CasePeople cp WHERE cp.person_nb = {number}"
            returns.insert(index, ([x[0] for x in self._query(cases_query)],))

        return returns

    def update_persons(self, number: int, **kwargs):
        allowed_columns = {"last_name", "first_name", "address", "birth_date", "contact_info", "gender", "description",
                           "notes", "can_be_lawyer"}
        updates = []
        params = []
        for key, value in kwargs.items():
            if key in allowed_columns:
                updates.append(f"{key} = ?")
                params.append(value)
            elif key == "cases":
                # Remove existing cases
                self._execute("DELETE FROM CasePeople WHERE person_nb = ?", (number,))
                # Add new cases
                for case_nb in value:
                    self._execute("INSERT INTO CasePeople (case_nb, person_nb) VALUES (?, ?)", (case_nb, number))
            else:
                raise ValueError(f"Attribute {key} is not allowed")

        if updates:
            query = f"UPDATE Persons SET {', '.join(updates)} WHERE nb = ?"
            params.append(number)
            self._execute(query, params)

    def add_person(self, last_name: str, first_name: str, address: str, birth_date: str, contact_info: str,
                   gender: _Literal["Male", "Female", "Other"], description: str = "", notes: str = "",
                   can_be_lawyer: bool = False) -> int:
        return self._execute("INSERT INTO Persons "
                          "(last_name, first_name, address, birth_date, contact_info, gender, description, notes, can_be_lawyer) "
                          "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                          (last_name, first_name, address, birth_date, contact_info, gender, description, notes,
                           1 if can_be_lawyer else 0), return_id=True)

    def delete_person(self, number: int):
        self._execute(f"DELETE FROM Persons WHERE nb = {number}")

    def get_all_person_objs(self) -> dict[int, _Person]:
        person_nbs = self._query("SELECT nb FROM Persons")
        return {nb: _Person(nb, self) for (nb,) in person_nbs}

    def get_cases(self, number: int, *_: _Literal["name", "description", "notes", "persons", "documents"]):
        returns = []
        for attr in _:
            if attr in ("name", "description", "notes"):
                query = f"SELECT c.{attr} FROM Cases c WHERE c.nb = {number}"
                returns.append(self._query(query)[0])
            elif attr == "persons":
                query = f"SELECT cp.person_nb FROM CasePeople cp WHERE cp.case_nb = {number}"
                query2 = f"SELECT cp.lawyer_nb, cp.side FROM CasePeople cp WHERE cp.case_nb = {number}"

                results_query1 = self._query(query)
                results_query2 = self._query(query2)

                # Ensure both results lists have the same length
                if len(results_query1) == len(results_query2):
                    returns.append(tuple((x[0], y[0], y[1]) for x, y in zip(results_query1, results_query2)))
                else:
                    print("Error: Query results have different lengths")
                    returns.append(())
            elif attr == "documents":
                query = f"SELECT cd.document_nb FROM CaseDocuments cd WHERE cd.case_nb = {number}"
                returns.append(tuple(x[0] for x in self._query(query)))
            else:
                raise ValueError(f"Attribute {attr} is not allowed")
        return returns

    def update_cases(self, number: int, **kwargs):
        allowed_columns = {"name", "description", "notes"}
        updates = []
        params = []
        for key, value in kwargs.items():
            if key in allowed_columns:
                updates.append(f"{key} = ?")
                params.append(value)
            elif key == "persons":
                # Remove existing persons
                self._execute("DELETE FROM CasePeople WHERE case_nb = ?", (number,))
                # Add new persons
                for person_nb in value:
                    self._execute("INSERT INTO CasePeople (case_nb, person_nb, lawyer_nb, side) VALUES (?, ?, ?, ?)", (number, *person_nb))
            elif key == "documents":
                # Remove existing documents
                self._execute("DELETE FROM CaseDocuments WHERE case_nb = ?", (number,))
                # Add new documents
                value = value if isinstance(value, (tuple, list)) else (value,)
                for document_nb in value:
                    self._execute("INSERT INTO CaseDocuments (case_nb, document_nb) VALUES (?, ?)", (number, document_nb))
            else:
                raise ValueError(f"Attribute {key} is not allowed")

        if updates:
            query = f"UPDATE Cases SET {', '.join(updates)} WHERE nb = ?"
            params.append(number)
            self._execute(query, params)

    def add_case(self, name: str, description: str = "", notes: str = "", persons: list[tuple[int, int, int]] = None,
                 documents: list = None) -> int:
        if persons is None:
            persons = []
        if documents is None:
            documents = []
        case_nb = self._execute("INSERT INTO Cases (name, description, notes) VALUES (?, ?, ?)",
                           (name, description, notes), return_id=True)
        for (person_nb, lawyer_nb, side) in persons:
            self._execute("INSERT INTO CasePeople (case_nb, person_nb, lawyer_nb, side, has_external_lawyer, self_represented) "
                          "VALUES (?, ?, ?, ?, ?, ?)",
                          (case_nb, person_nb, lawyer_nb, 1 if side else 0, 0, 1 if person_nb == lawyer_nb else 0))
        for document_nb in documents:
            self._execute("INSERT INTO CaseDocuments (case_nb, document_nb) VALUES (?, ?)",
                          (case_nb, document_nb))

        return case_nb

    def delete_case(self, number: int):
        self._execute(f"DELETE FROM Cases WHERE nb = {number}")

    def get_all_case_objs(self) -> dict[int, _Case]:
        case_nbs = self._query("SELECT nb FROM Cases")
        return {nb: _Case(nb, self) for (nb,) in case_nbs}

    def get_documents(self, number: int, *_: _Literal["name", "description", "notes", "path", "cases"]):
        returns = []
        for attr in _:
            if attr in ("name", "description", "notes", "path"):
                query = f"SELECT d.{attr} FROM Documents d WHERE d.nb = {number}"
                returns.append(self._query(query)[0])
            elif attr == "cases":
                query = f"SELECT cd.case_nb FROM CaseDocuments cd WHERE cd.document_nb = {number}"
                returns.append(tuple(x[0] for x in self._query(query)))
            else:
                raise ValueError(f"Attribute {attr} is not allowed")
        return returns

    def update_documents(self, number: int, **kwargs):
        allowed_columns = {"name", "description", "notes", "path"}
        updates = []
        params = []
        for key, value in kwargs.items():
            if key in allowed_columns:
                updates.append(f"{key} = ?")
                params.append(value)
            elif key == "cases":
                # Remove existing cases
                self._execute("DELETE FROM CaseDocuments WHERE document_nb = ?", (number,))
                # Add new cases
                for case_nb in value:
                    self._execute("INSERT INTO CaseDocuments (case_nb, document_nb) VALUES (?, ?)", (case_nb, number))
            else:
                raise ValueError(f"Attribute {key} is not allowed")

        if updates:
            query = f"UPDATE Documents SET {', '.join(updates)} WHERE nb = ?"
            params.append(number)
            self._execute(query, params)

    def add_document(self, name: str, description: str = "", notes: str = "", current_path: str = "") -> int:
        new_path = f"./documents/{_os.path.basename(current_path)}"
        _shutil.copy(current_path, new_path)

        return self._execute("INSERT INTO Documents (name, description, notes, path, archived) VALUES (?, ?, ?, ?, ?)",
                      (name, description, notes, new_path, 1), return_id=True)

    def delete_document(self, number: int):
        self._execute(f"DELETE FROM Documents WHERE nb = {number}")

    def get_all_document_objs(self) -> dict[int, _Document]:
        document_nbs = self._query("SELECT nb FROM Documents")
        return {nb: _Document(nb, self) for (nb,) in document_nbs}

    def search(self, query) -> tuple[tuple[str, tuple[int, ...], tuple[str, ...]]]:
        returns = []
        for tables, sql, params, all_ret_vals in self._search_engine.get_sql_query_from_user_input(query):
            results = self._query(sql, params)

            if not results:
                continue

            transposed_results = list(zip(*results))

            for i, (table, ret_vals) in enumerate(zip(tables, all_ret_vals)):
                if table == "Documents":
                    continue
                inter = tuple(set(transposed_results[i]))
                returns.append((table, inter, ret_vals))

        return tuple(returns)

    def restricted_search(self, query, where) -> tuple[list, tuple]:
        sql, params, ret_vals = self._search_engine.get_sql_query_from_user_input_restricted(query, where)
        results = self._query(sql, params)
        if not results:
            return [], ()
        transposed_results = list(zip(*results))
        return list(set(transposed_results[0])), ret_vals

    def register_user(self, username: str, password: str, role: _Literal["Admin", "Manager", "Viewer"]):
        password_hash = _bcrypt.hashpw(password.encode('utf-8'), _bcrypt.gensalt())
        try:
            self._execute('''
            INSERT INTO users (username, password_hash, role)
            VALUES (?, ?, ?);
            ''', (username, password_hash, role))
            print(f"User {username} registered successfully as {role}.")
        except _sqlite3.IntegrityError:
            print("Error: Username already exists.")

    def authenticate_user(self, username: str, password: str):
        result = self._query('''
        SELECT password_hash, role FROM users WHERE username = ?;
        ''', (username,))[0]
        if result:
            password_hash, role = result
            if _bcrypt.checkpw(password.encode('utf-8'), password_hash):
                print(f"Authentication successful. Role: {role}")
                return role
            else:
                print("Authentication failed. Incorrect password.")
                return None
        else:
            print("Authentication failed. User not found.")
            return None

    def cleanup(self):
        self.__del__()

    def __del__(self):
        self._conn.close()
