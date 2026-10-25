while pgrep -f "tanda[1][.]sh" >/dev/null; do sleep 15; done
ESC=1 bash /tmp/v/qa.sh S0_v4 /tmp/v/S0.db
ESC=1 bash /tmp/v/qa.sh T1000r_v4 /tmp/v/T1000r.db
ESC=1 bash /tmp/v/qa.sh A640_v4 /tmp/v/A640.db
echo TANDA2_FIN
