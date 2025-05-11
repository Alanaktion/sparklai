import sqlite3


class SerializableRow(sqlite3.Row):
    def asdict(self):
        return {key: self[key] for key in self.keys()}


con = sqlite3.connect("db.sqlite3", check_same_thread=False, autocommit=True)
con.row_factory = SerializableRow

with open('schema.sql') as file:
    con.executescript(file.read())


def fetch_post(id) -> SerializableRow:
    return con.execute(f"SELECT p.*, COUNT(c.id) AS comment_count FROM posts AS p LEFT JOIN comments AS c ON c.post_id = p.id WHERE p.id = ?", (id,)).fetchone()


class Model:
    table_name: str

    @classmethod
    def insert(cls, **kwargs) -> int:
        column_names = ", ".join(kwargs.keys())
        placeholders = ", ".join(["?" for _ in kwargs])
        sql_command = f"INSERT INTO {cls.table_name} ({column_names}) VALUES ({placeholders})"

        return con.execute(sql_command, tuple(kwargs.values())).lastrowid # type: ignore

    @classmethod
    def select(cls, **kwargs):
        if kwargs:
            where_clause = " AND ".join([f"{key} = ?" for key in kwargs])
            sql_command = f"SELECT * FROM {cls.table_name} WHERE {where_clause}"
        else:
            sql_command = f"SELECT * FROM {cls.table_name}"

        return con.execute(sql_command, tuple(kwargs.values()))

    @classmethod
    def find(cls, **kwargs) -> SerializableRow:
        return cls.select(**kwargs).fetchone()

    @classmethod
    def find_all(cls, **kwargs) -> list[SerializableRow]:
        return cls.select(**kwargs).fetchall()

    @classmethod
    def update(cls, record_id, **kwargs):
        set_clause = ", ".join([f"{key} = ?" for key in kwargs])
        sql_command = f"UPDATE {cls.table_name} SET {set_clause} WHERE id = ?"

        values = tuple(kwargs.values()) + (record_id,)
        con.execute(sql_command, values)

    @classmethod
    def delete(cls, record_id):
        sql_command = f"DELETE FROM {cls.table_name} WHERE id = ?"
        con.execute(sql_command, (record_id,))
