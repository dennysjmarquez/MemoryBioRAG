while pgrep -f "tanda[2][.]sh" >/dev/null; do sleep 20; done
for j in "S0_fin /tmp/v/S0.db 1" "T1000r_fin /tmp/v/T1000r.db 1" "A640_fin /tmp/v/A640.db 1" "T3000r_off /tmp/v/T3000r.db 0" "T3000r_fin /tmp/v/T3000r.db 1"; do
  set -- $j; ESC=$3 bash /tmp/v/qa.sh $1 $2
done
echo TANDA3_FIN
