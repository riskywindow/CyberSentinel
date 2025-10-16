#!/usr/bin/env python3
"""Compile protobuf schema to Python bindings."""

import subprocess
import sys
from pathlib import Path

def main():
    proto_dir = Path(__file__).parent
    proto_file = proto_dir / "cybersentinel.proto"
    output_dir = proto_dir
    
    if not proto_file.exists():
        print(f"Proto file not found: {proto_file}")
        return 1
    
    # Compile with protoc
    cmd = [
        "python", "-m", "grpc_tools.protoc",
        f"--proto_path={proto_dir}",
        f"--python_out={output_dir}",
        f"--pyi_out={output_dir}",
        str(proto_file)
    ]
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("Proto compilation successful")
        return 0
    except subprocess.CalledProcessError as e:
        print(f"Proto compilation failed: {e}")
        print(f"stdout: {e.stdout}")
        print(f"stderr: {e.stderr}")
        return 1
    except FileNotFoundError:
        print("grpcio-tools not installed. Run: pip install grpcio-tools")
        return 1

if __name__ == "__main__":
    sys.exit(main())