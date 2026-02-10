#!/bin/bash
set -e

# Create a minimal Kedro project structure
mkdir -p kedro-test
cd kedro-test

# Initialize DataLad dataset
echo "=== Initializing DataLad dataset ==="
datalad create -c yoda . || true
cd .

# Create minimal Kedro project structure
echo "=== Creating minimal Kedro project structure ==="
mkdir -p src/kedro_test
touch src/kedro_test/__init__.py

cat > pyproject.toml << 'EOF'
[build-system]
requires = ["setuptools"]
build-backend = "setuptools.build_meta"

[project]
name = "kedro_test"
version = "0.1.0"

[tool.kedro]
package_name = "kedro_test"
project_name = "kedro_test"
kedro_init_version = "1.2.0"
source_dir = "src"
EOF

cat > src/kedro_test/settings.py << 'EOF'
# Kedro settings
EOF

cat > src/kedro_test/pipeline_registry.py << 'EOF'
from kedro.pipeline import Pipeline, node

def greet(name: str) -> str:
    message = f"Hello, {name}!"
    # Write to file so we can see output
    with open("output.txt", "w") as f:
        f.write(message)
    return message

def register_pipelines():
    return {
        "__default__": Pipeline([
            node(greet, inputs="params:name", outputs="greeting")
        ])
    }
EOF

mkdir -p conf/base conf/local
cat > conf/base/parameters.yml << 'EOF'
name: DataLad
EOF

cat > conf/base/catalog.yml << 'EOF'
# Empty catalog (required by Kedro 1.x)
EOF

# Add Python cache to .gitignore
cat >> .gitignore << 'EOF'
__pycache__/
*.pyc
EOF

echo "=== Saving Kedro project structure to DataLad ==="
datalad save -m "Initialize minimal Kedro project"

echo ""
echo "==========================================="
echo "TEST 1: Kedro with telemetry ENABLED"
echo "==========================================="
echo ""

# Make sure telemetry is enabled (unset the disable variable)
unset KEDRO_DISABLE_TELEMETRY
unset DO_NOT_TRACK

# Run kedro with telemetry enabled
echo "Running: kedro run"
kedro run 2>&1

echo ""
echo "Output file created:"
cat output.txt 2>/dev/null || echo "No output file"

echo ""
echo "==========================================="
echo "TEST 2: Kedro with datalad run (telemetry still enabled)"
echo "==========================================="
echo ""

# Clean up output and save
rm -f output.txt
datalad save -m "Clean up for test 2"

# Run with datalad run
echo "Running: datalad run --output output.txt kedro run"
datalad run \
    --message "Execute Kedro demo pipeline with DataLad" \
    --output "output.txt" \
    kedro run 2>&1

echo ""
echo "Output file created:"
cat output.txt 2>/dev/null || echo "No output file"

echo ""
echo "==========================================="
echo "TEST 3: Kedro with con-duct (telemetry still enabled)"
echo "==========================================="
echo ""

# Clean up output and save
rm -f output.txt
datalad save -m "Clean up for test 3"

# Run with con-duct
echo "Running: duct --output-prefix /tmp/duct-kedro- kedro run"
duct --output-prefix /tmp/duct-kedro- kedro run 2>&1

echo ""
echo "Output file created:"
cat output.txt 2>/dev/null || echo "No output file"

echo ""
echo "Con-duct telemetry files:"
ls -lh /tmp/duct-kedro-* 2>/dev/null || echo "No duct files"

echo ""
echo "==========================================="
echo "TEST 4: Kedro with BOTH datalad run AND con-duct (telemetry enabled)"
echo "==========================================="
echo ""

# Clean up output and save
rm -f output.txt
rm -f /tmp/duct-kedro-*
datalad save -m "Clean up for test 4"

# Run with both datalad run and con-duct
echo "Running: datalad run --output output.txt duct --output-prefix /tmp/duct-kedro2- kedro run"
datalad run \
    --message "Execute Kedro with con-duct inside datalad run" \
    --output "output.txt" \
    duct --output-prefix /tmp/duct-kedro2- kedro run 2>&1

echo ""
echo "Output file created:"
cat output.txt 2>/dev/null || echo "No output file"

echo ""
echo "Con-duct telemetry files:"
ls -lh /tmp/duct-kedro2-* 2>/dev/null || echo "No duct files"

echo ""
echo "Git log (showing provenance):"
git log --oneline -5

echo ""
echo "========================================="
echo "SUMMARY"
echo "========================================="
echo ""
echo "All tests completed successfully!"
