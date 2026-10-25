cd /tmp/v; export PYTHONPATH=/home/user/MemoryBioRAG PYTHONHASHSEED=1 BIORAG_NEURONA=0 LIMPIO=1
/home/user/.biorag-venv/bin/python crecer.py tema 1000 /tmp/v/T1000c_raw.db > /tmp/v/build_T1000c.txt 2>&1
python3 dims.py /tmp/v/T1000c_raw.db /tmp/v/T1000c.db >> /tmp/v/build_T1000c.txt 2>&1
rm -f /tmp/v/T1000c_raw.db*; echo BUILD_C_FIN >> /tmp/v/build_T1000c.txt
