import paramiko
HOST="192.168.100.10"; USER="root"; PWD="rydhflsf.123"
c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PWD, timeout=10)
def run(cmd, t=60):
    sin,sout,serr=c.exec_command(cmd, timeout=t)
    return (sout.read().decode(errors="replace").strip()+"\n"+serr.read().decode(errors="replace").strip()).strip()[:7000]
print(run("pct exec 100 -- bash -lc 'cd /opt/japanese-study-v2 && docker compose exec -T db psql -U japanese_study -d japanese_study -c \"SELECT (SELECT count(*) FROM content_kanji) k,(SELECT count(*) FROM content_vocabulary) v,(SELECT count(*) FROM content_grammar) g,(SELECT count(*) FROM content_sentences) s,(SELECT count(*) FROM content_phrases) p,(SELECT count(*) FROM content_culture) cu,(SELECT count(*) FROM content_readings) r,(SELECT count(*) FROM vocabularies) vo;\"' 2>&1", t=60))
print(run("pct exec 100 -- ss -tlnp 2>&1 | grep -E '8081|443|3000|5432'", t=30))
print(run("pct exec 100 -- ls /opt/japanese-study 2>&1 | head; pct exec 100 -- docker ps -a --format '{{.Names}} {{.Status}}' 2>&1 | head -20", t=30))
c.close()
