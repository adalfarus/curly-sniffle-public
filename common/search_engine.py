from typing import Literal, List, Tuple, Optional
import re


class SearchEngine:
    """Gets a user generated query and converts it into sql commands for searching purposes."""
    _table_pattern = (r"(?:([a-zA-Z_]+)(?:\[((?:\w*\;?)*)])?(?:\{(\w+)})?([:=])\s?)?('[^']*'|(?:[\w\.]+\s?)+)"
                      r"((?:\s?[|&]\s?{\w*}[:=]\s?(?:'[^']*'|(?:\w+\s?)+))*(?:\s?[|&]\s?|$))")
    _search_term_pattern = r"\s?([&|])\s?\{(\w*)}([:=])\s?((?:[\w\.]+\s?|'[^']*')*)|\s?([|&])\s?"
    _map = {
        "user": ("Persons", "CasePeople"),
        "case": ("Cases",),
        "docu": ("Documents",)
    }
    _full_map = {
        ("Persons", "CasePeople"): (("last_name", "first_name", "address",
                                     "birth_date", "contact_info", "gender",
                                     "description", "notes", "can_be_lawyer"),
                                    ("self_represented", "has_external_lawyer",
                                     "side")),
        ("Cases",): (("name", "description", "notes"),),
        ("Documents", ): (("name", "description", "notes", "path"),)
    }
    _returns_map = {
        ("Persons", "CasePeople"): ("first_name", "last_name", "can_be_lawyer"),
        ("Cases",): ("name",),
        ("Documents",): ("name",)
    }
    _join_table_map = {
        "Cases": {
            "Persons": "INNER JOIN CasePeople ON Cases.nb = CasePeople.case_nb INNER JOIN Persons ON CasePeople.person_nb = Persons.nb",
            "Documents": "INNER JOIN CaseDocuments ON Cases.nb = CaseDocuments.case_nb INNER JOIN Documents ON CaseDocuments.document_nb = Documents.nb"
        },
        "Persons": {
            "Cases": "INNER JOIN Cases ON CasePeople.case_nb = Cases.nb",  # INNER JOIN CasePeople ON CasePeople.person_nb = Persons.nb
            "Documents": "INNER JOIN CaseDocuments ON CasePeople.case_nb = CaseDocuments.case_nb JOIN Documents ON CaseDocuments.document_nb = Documents.nb"  # INNER JOIN CasePeople ON CasePeople.person_nb = Persons.nb
        },
        "Documents": {
            "Cases": "INNER JOIN CaseDocuments ON Documents.nb = CaseDocuments.document_nb INNER JOIN Cases ON CaseDocuments.case_nb = Cases.nb",
            "Persons": "INNER JOIN CaseDocuments ON Documents.nb = CaseDocuments.document_nb INNER JOIN CasePeople ON CaseDocuments.case_nb = CasePeople.case_nb JOIN Persons ON CasePeople.person_nb = Persons.nb"
        }
    }

    def __init__(self):
        self._table_rejects = re.compile(self._table_pattern)
        self._search_term_rejects = re.compile(self._search_term_pattern)

    @staticmethod
    def _check_consumed_string(input_string: str, rejects) -> tuple[list[str], bool]:
        matches = list(rejects.finditer(input_string))
        all_matches = [match.group() for match in matches]

        if not matches:
            return [], False

        # Check if the entire string is consumed
        last_end = 0
        for match in matches:
            if match.start() != last_end:
                return all_matches, False
            last_end = match.end()

        entire_string_consumed = last_end == len(input_string)
        return all_matches, entire_string_consumed

    @staticmethod
    def _check_consumed_substring(input_string: str, rejects) -> tuple[list[tuple[str, Optional[str], Optional[str], Optional[str], Optional[str]]], bool]:
        matches = list(rejects.finditer(input_string))
        all_matches = [match.groups() for match in matches]

        if not matches and input_string == "":
            return [], True
        elif not matches:
            return [], False

        # Check if the entire string is consumed
        last_end = 0
        for match in matches:
            if match.start() != last_end:
                return all_matches, False
            last_end = match.end()

        entire_string_consumed = last_end == len(input_string)
        return all_matches, entire_string_consumed

    def _parse_user_input(self, user_input: str) -> Optional[list[tuple[tuple, list[tuple]]]]:
        main_matches, entire_string_consumed = self._check_consumed_string(user_input, self._table_rejects)

        if not entire_string_consumed:
            return None

        parsed_results = []
        for main_match in main_matches:
            match = self._table_rejects.match(main_match)
            if not match:
                continue

            groups = match.groups()
            sub_string = groups[-1]

            if not (len(sub_string) <= 3 and "|" in sub_string):
                search_terms, sub_string_consumed = self._check_consumed_substring(sub_string, self._search_term_rejects)

                if not sub_string_consumed:
                    return None
            else:
                search_terms = []

            parsed_results.append((groups[:-1], search_terms))

        return parsed_results

    def _join_query(self, query, join_table, join_parameters):
        # Find the main table in the FROM clause
        from_clause_match = re.search(r"FROM (\w+)", query, re.IGNORECASE)
        if from_clause_match:
            query_table = from_clause_match.group(1)
        else:
            raise ValueError("Unable to find the FROM clause in the query")

        # Append the join_table to the SELECT clause
        select_clause_match = re.search(r"SELECT (.+?) FROM", query, re.IGNORECASE | re.DOTALL)
        if select_clause_match:
            select_clause = select_clause_match.group(1)

            # Handle insertion before ", NULL AS relevance, CASE"
            relevance_case_match = re.search(r", NULL AS relevance, CASE", select_clause, re.IGNORECASE)
            if relevance_case_match:
                new_select_clause = select_clause[:relevance_case_match.start()] + f", {join_table}.nb" + select_clause[
                                                                                                          relevance_case_match.start():]
            else:
                new_select_clause = f"{select_clause}, {join_table}.nb"

            query = query.replace(select_clause, new_select_clause, 1)
        else:
            raise ValueError("Unable to find the SELECT clause in the query")

        # Insert the JOIN condition before the WHERE clause
        where_clause_match = re.search(r"WHERE", query, re.IGNORECASE)
        if where_clause_match:
            where_clause_index = where_clause_match.start()
            query = query[:where_clause_index] + f"{self._join_table_map[query_table][join_table]} " + query[where_clause_index:]
        else:
            # If there's no WHERE clause, just add the join condition at the end
            query += f" {self._join_table_map[query_table][join_table]}"

        # Isolate all other conditions using parentheses && Append join parameters to the end of the query
        query = re.sub(r"WHERE (.+?)(?= ORDER BY relevance|$)", rf"WHERE (\1) {' '.join(join_parameters) if join_parameters else ''}", query, flags=re.IGNORECASE | re.DOTALL)

        return query

    def _generate_query(self, input_tuple: tuple[str], search_terms) -> tuple[str, tuple]:
        table_names = self._map[input_tuple[0]]
        table_columns = self._full_map[table_names]
        initial_column = input_tuple[2]
        initial_bool = input_tuple[3]
        initial_value = input_tuple[4].strip()

        # Build the FROM clause with JOINS
        from_clause = f" FROM {table_names[0]}"
        if len(table_names) > 1:
            for i in range(1, len(table_names)):
                from_clause += (f" LEFT JOIN {table_names[i]} ON {table_names[0]}.nb = {table_names[i]}"
                                f".{table_names[0].lower().removesuffix('s')}_nb")

        query = f"SELECT {table_names[0]}.nb{from_clause} WHERE "

        conditions = []
        params = []

        # Handle the initial search term
        table = ""
        for curr_table, columns in zip(table_names, table_columns):
            if initial_column in columns:
                table = curr_table

        if initial_bool == ":":
            conditions.append(f"{table}.{initial_column} REGEXP ?")
            params.append(initial_value)
        else:
            conditions.append(f"{table}.{initial_column} = ?")
            params.append(initial_value)

        # Handle additional search terms
        for term in search_terms:
            if term[-1]:
                break

            combinator = term[0]
            column = term[1]
            search_bool = term[2]
            search_value = term[3].strip()

            table = ""
            for curr_table, columns in zip(table_names, table_columns):
                if column in columns:
                    table = curr_table

            if search_bool == ":":
                condition = f"{table}.{column} REGEXP ?"
            else:
                condition = f"{table}.{column} = ?"

            if combinator == "&":
                conditions.append(f"AND {condition}")
            elif combinator == "|":
                conditions.append(f"OR {condition}")
            else:
                conditions.append(condition)

            params.append(search_value)

        # Build the final query
        query += " ".join(conditions)

        return query, tuple(params)

    @staticmethod
    def _generate_full_query(tables_and_columns, vague_search_term, additional_search_terms: dict) -> tuple[str, tuple]:
        # Handling multiple tables and building the FROM clause with JOINS
        main_table = next(iter(tables_and_columns))
        from_clause = f"FROM {main_table}"
        if len(tables_and_columns) > 1:
            for k, _ in tables_and_columns.items():
                if k != main_table:
                    from_clause += (f" LEFT JOIN {k} ON {main_table}.nb = {k}"
                                    f".{main_table.lower().removesuffix('s')}_nb")

        # Start building the SELECT clause
        select_clause = f"SELECT {main_table}.nb, NULL AS relevance, CASE"

        # Building the CASE statement for relevance
        case_conditions = []

        length = sum(len(cols) for cols in tables_and_columns.values())
        case_index = 0
        for table, table_columns in tables_and_columns.items():
            for i, column in enumerate(table_columns):
                case_conditions.append(f"WHEN {table}.{column} = ? THEN {length + 2 - case_index}")
                case_conditions.append(f"WHEN {table}.{column} REGEXP ? THEN {length - case_index}")
                case_index += 1

        case_statement = " ".join(case_conditions)

        # Closing the CASE statement
        case_statement += " ELSE 0 END AS relevance"

        # Building the WHERE clause for the vague search term
        where_clause_conditions = []
        for table, table_columns in tables_and_columns.items():
            for column in table_columns:
                where_clause_conditions.append(f"{table}.{column} REGEXP ?")
        where_clause = " OR ".join(where_clause_conditions)

        # Add additional search terms to the WHERE clause
        additional_conditions = []
        additional_search_termini = []
        for column, (logic, operator, value) in additional_search_terms.items():
            table = ""
            for curr_table, columns in tables_and_columns.items():
                if column in columns:
                    table = curr_table
            if operator:
                additional_conditions.append(f"{logic} {table}.{column} REGEXP ?")
            else:
                additional_conditions.append(f"{logic} {table}.{column} = ?")
            additional_search_termini.append(value)

        additional_where_clause = " ".join(additional_conditions)

        if additional_where_clause:
            where_clause = f"({where_clause}) {additional_where_clause}"

        # Construct the final query
        query = select_clause + f" {case_statement} {from_clause} WHERE {where_clause} ORDER BY relevance DESC"

        return query, tuple([f".*{vague_search_term}.*"] * ((length * 2) + length) + additional_search_termini)

    def get_sql_query_from_user_input(self, user_input) -> tuple[tuple[tuple, str, tuple, tuple[tuple, ...]]]:
        parsed_input = self._parse_user_input(user_input)
        returns = []

        if parsed_input is None:
            if user_input == "":
                return (
                        (
                            ("Persons", "Cases", "Documents"),
                            "SELECT Persons.nb, Cases.nb, Documents.nb FROM Persons FULL OUTER JOIN Cases FULL OUTER JOIN Documents",
                            (),
                            (
                                self._returns_map[("Persons", "CasePeople")],
                                self._returns_map[("Cases",)],
                                self._returns_map[("Documents",)]
                            )
                        ),
                    )
            else:
                return ((("Persons", "Cases", "Documents"), "", (), ((), (), ()),),)

        concatenate_tables = False
        for main, search_terms in parsed_input:
            table = self._map.get(main[0])
            last_term = search_terms[-1][-1] if len(search_terms) > 0 else None
            ret_val = tuple(main[1].split(";")) if main[1] is not None else self._returns_map.get(table)
            normalized_extra = {
                k: ("OR" if op == "|" else "AND", reg == ":", val)
                for op, k, reg, val, flag in search_terms if not flag
            }

            if table is None:  # Means no table specified
                for table in self._map.values():
                    ret_val = tuple(main[0].split(";")) if main[1] else self._returns_map.get(table)
                    if main[2] is None:
                        table_map = {k: v for k, v in zip(table, self._full_map[table])}
                        query = self._generate_full_query(table_map, main[4], additional_search_terms=normalized_extra)
                    else:
                        query = self._generate_query(main, search_terms)
                    returns.append(((table[0],), *query, (ret_val,)))
            else:
                if main[2] is None:
                    table_map = {k: v for k, v in zip(table, self._full_map[table])}
                    query = self._generate_full_query(table_map, main[4], additional_search_terms=normalized_extra)
                else:
                    query = self._generate_query(main, search_terms)

                if concatenate_tables:
                    concatenate_tables = False

                    where_lst = []
                    value_lst = []
                    for (operator, column, regex_flag, value, table_flag) in [("&", *main[2:], None)] + search_terms:
                        if not table_flag:
                            found_table = ""
                            for curr_table, columns in zip(table, self._full_map[table]):
                                if column in columns:
                                    found_table = curr_table
                            where = f"{found_table}.{column}"
                            if regex_flag:
                                where += " REGEXP ?"
                            else:
                                where += " = ?"
                            where_lst.append(("OR " if operator == "|" else "AND ") + where)
                            value_lst.append(value)

                    where_tup = tuple(where_lst)
                    value_tup = tuple(value_lst)

                    returns[-1] = (
                        returns[-1][0] + (table[0],),
                        self._join_query(
                            returns[-1][1],
                            table[0],
                            where_tup
                        ),
                        returns[-1][2] + value_tup,
                        returns[-1][3] + (self._returns_map.get(table, ()),)
                    )
                else:
                    returns.append(((table[0],), *query, (ret_val,)))

            if last_term == "&":
                concatenate_tables = True

        return tuple(returns)

    def get_sql_query_from_user_input_restricted(self, user_input, restricted_table: Literal["user", "case", "docu"]
                                                 ) -> tuple[str, tuple, tuple]:
        parsed_input = self._parse_user_input(user_input)
        table = self._map[restricted_table]

        if parsed_input is None:
            if user_input == "":
                return f"SELECT nb FROM {table[0]}", (), self._returns_map[table]
            return "", (), ()
        if len(parsed_input) > 1:
            return "", (), ()

        main, search_terms = parsed_input[0]
        if main[0] is None or self._map[main[0]] == table:
            ret_val = tuple(main[1].split(";")) if main[1] is not None else self._returns_map[table]
            if main[2] is None:
                table_map = {k: v for k, v in zip(table, self._full_map[table])}
                normalized_extra = {k: ("OR" if op == "|" else "AND", True if reg == ":" else False, val)
                                    for (op, k, reg, val, flag) in search_terms if not flag}
                query: tuple[str, tuple] = self._generate_full_query(table_map, main[4],
                                                                     additional_search_terms=normalized_extra)
            else:
                query: tuple[str, tuple] = self._generate_query(main, search_terms)
            return *query, ret_val
        else:
            return "", (), ()
