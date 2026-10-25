cd /tmp/v; export PYTHONPATH=/home/user/MemoryBioRAG PYTHONHASHSEED=1 BIORAG_NEURONA=0 LIMPIO=1
/home/user/.biorag-venv/bin/python crecer.py tema 3000 /tmp/v/T3000_raw.db > /tmp/v/build_T3000.txt 2>&1
python3 dims_nn.py /tmp/v/T3000_raw.db /tmp/v/T3000r.db >> /tmp/v/build_T3000.txt 2>&1
rm -f /tmp/v/T3000_raw.db*; echo BUILD_3K_FIN >> /tmp/v/build_T3000.txt
