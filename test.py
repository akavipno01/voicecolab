import sqlite3
conn = sqlite3.connect(r'D:\Thang\voiceclone\voicecolab\backend\data\voice-clone.sqlite3')
res = conn.execute("SELECT id, name FROM voice_profiles WHERE id LIKE '%osaka%' OR name LIKE '%osaka%'").fetchall()
print(res)
