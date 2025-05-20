import sqlite3
import time

phones = ['+381628231797', '+34617108387']
conn = sqlite3.connect('joins_history.db')
c = conn.cursor()
now = time.time()
for phone in phones:
    c.execute('SELECT COUNT(*) FROM joins_history WHERE account_phone=? AND timestamp > ? AND success=1', (phone, now-86400))
    print(f'{phone}: вступлений за сутки:', c.fetchone()[0])
    c.execute('SELECT COUNT(*) FROM joins_history WHERE account_phone=? AND timestamp > ? AND success=1', (phone, now-3600))
    print(f'{phone}: вступлений за час:', c.fetchone()[0])
conn.close() 