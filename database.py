import mysql.connector
from config import Config
import json

class Database:
    def __init__(self):
        self.config = Config()
        self.connection = None
        self.connect()

    def connect(self):
        try:
            self.connection = mysql.connector.connect(
                host=self.config.MYSQL_HOST,
                user=self.config.MYSQL_USER,
                password=self.config.MYSQL_PASSWORD,
                database=self.config.MYSQL_DATABASE,
                port=self.config.MYSQL_PORT
            )
            print("Connected to MySQL database")
        except mysql.connector.Error as e:
            print(f"Error connecting to MySQL: {e}")

    def execute_query(self, query, params=None, fetch=False):
        try:
            cursor = self.connection.cursor(dictionary=True)
            cursor.execute(query, params or ())
            
            if fetch:
                result = cursor.fetchall()
            else:
                self.connection.commit()
                result = cursor.lastrowid
            
            cursor.close()
            return result
        except mysql.connector.Error as e:
            print(f"Database error: {e}")
            return None

    def insert_faq(self, question, answer, category=None):
        query = "INSERT INTO faqs (question, answer, category) VALUES (%s, %s, %s)"
        return self.execute_query(query, (question, answer, category))

    def get_all_faqs(self):
        query = "SELECT * FROM faqs ORDER BY category, id"
        return self.execute_query(query, fetch=True)

    def search_faqs_by_keyword(self, keyword):
        query = """
        SELECT * FROM faqs 
        WHERE question LIKE %s OR answer LIKE %s
        ORDER BY category
        """
        params = (f'%{keyword}%', f'%{keyword}%')
        return self.execute_query(query, params, fetch=True)

    def save_chat_history(self, user_message, bot_response, confidence_score=None):
        query = """
        INSERT INTO chat_history (user_message, bot_response, confidence_score)
        VALUES (%s, %s, %s)
        """
        return self.execute_query(query, (user_message, bot_response, confidence_score))

    def get_chat_history(self, limit=50):
        query = "SELECT * FROM chat_history ORDER BY created_at DESC LIMIT %s"
        return self.execute_query(query, (limit,), fetch=True)