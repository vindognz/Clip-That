import sqlite3

class Database:
    """ Stores who has opted in.
        A  row in 'consent' = opted in
        No row in 'consent' = opted out (default)
    """

    def __init__(self, path: str):
        self.connection = sqlite3.connect(path)
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS consent (
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                PRIMARY KEY (guild_id, user_id)
            )
            """
        )

        self.connection.commit()

    def opt_in(self, guild_id: int, user_id: int) -> bool:
        """ Returns True if they are newly opted in;
            returns False if they already were.
        """

        cur = self.connection.execute("INSERT OR IGNORE INTO consent (guild_id, user_id) VALUES (?, ?)", (guild_id, user_id))
        self.connection.commit()

        return cur.rowcount == 1

    def opt_out(self, guild_id: int, user_id: int) -> bool:
        """ Returns True if they just opted out;
            returns False if they already were.
        """

        cur = self.connection.execute("DELETE FROM consent WHERE guild_id = ? AND user_id = ?", (guild_id, user_id))
        self.connection.commit()

        return cur.rowcount == 1

    def is_opted_in(self, guild_id: int, user_id: int) -> bool:
        cur = self.connection.execute("SELECT 1 FROM consent WHERE guild_id = ? AND user_id = ?", (guild_id, user_id))

        return cur.fetchone() is not None

    def opted_in_users(self, guild_id: int) -> bool:
        cur = self.connection.execute("SELECT user_id FROM consent WHERE guild_id = ?", (guild_id,))

        return {row[0] for row in cur.fetchall()}