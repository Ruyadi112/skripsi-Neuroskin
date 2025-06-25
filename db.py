import mysql.connector

def get_connection():
    return mysql.connector.connect(
        host="sql12.freesqldatabase.com",
        user="sql12786702", 
        password="1VmzvnIlgu",
        database="sql12786702" 
    )
