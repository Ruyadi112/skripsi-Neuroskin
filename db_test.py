from db import get_connection

try:
    conn = get_connection()
    print("✅ Koneksi ke sqlfreedatabase berhasil!")
    conn.close()
except Exception as e:
    print("❌ Gagal konek:", e)
