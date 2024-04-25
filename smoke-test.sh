rm -rf .duct/*
duct --report-interval 2 --sample-interval 0.5 ./test_script.py -- --duration 6 --cpu-load 50000 --memory-size 50000
find .duct/ -name '*.json' -exec sh -c 'echo "File: $1)"; cat "$1" | jq' _ {} \;
