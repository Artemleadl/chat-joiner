import sqlite3
import pandas as pd

# Путь к базе данных и имя выходного файла
DB_FILE = 'chats.db'
EXCEL_FILE = 'chats_export.xlsx'

# Подключение к базе и чтение данных
conn = sqlite3.connect(DB_FILE)
df = pd.read_sql_query('SELECT * FROM chats', conn)
conn.close()

# Экспорт в Excel
with pd.ExcelWriter(EXCEL_FILE, engine='xlsxwriter') as writer:
    df.to_excel(writer, index=False, sheet_name='Chats')

print(f'✅ Данные успешно экспортированы в {EXCEL_FILE}') 