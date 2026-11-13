"""
Spike: Access Database Reading
CRITICAL - P0 Risk #1

Test reading .mdb files with available tools:
1. mdbtools (CLI) - most reliable, Linux-friendly
2. access_parser (Python) - pure Python, may have limitations

This spike proves we can read Access databases before proceeding to P1.
"""
import importlib.util
import subprocess
import sys
from pathlib import Path


def test_mdbtools():
    """Test mdbtools CLI availability and basic usage"""
    print("Testing mdbtools (CLI)...")
    
    try:
        # Check if mdb-tables is available
        result = subprocess.run(
            ["mdb-tables", "--help"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            print("✓ mdbtools is available")
            return True
        else:
            print("✗ mdbtools not found")
            return False
    except FileNotFoundError:
        print("✗ mdbtools not installed")
        print("  Install: apt-get install mdbtools (Linux)")
        print("  Install: brew install mdbtools (macOS)")
        return False


def test_access_parser():
    """Test access_parser Python library"""
    print("\nTesting access_parser (Python)...")
    
    if importlib.util.find_spec("access_parser") is not None:
        print("✓ access_parser is available")
        return True

    print("✗ access_parser not installed")
    print("  Install: pip install access-parser")
    return False


def read_with_mdbtools(mdb_path: Path):
    """Read .mdb file using mdbtools CLI"""
    print(f"\n--- Reading {mdb_path} with mdbtools ---")
    
    # List tables
    result = subprocess.run(
        ["mdb-tables", str(mdb_path)],
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        print(f"✗ Failed to read tables: {result.stderr}")
        return False
    
    tables = result.stdout.strip().split()
    print(f"✓ Tables found: {', '.join(tables)}")
    
    # Read first table (Articles)
    if "Articles" in tables:
        result = subprocess.run(
            ["mdb-export", str(mdb_path), "Articles"],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            print(f"✓ Articles table: {len(lines)-1} rows")
            print(f"  Header: {lines[0]}")
            if len(lines) > 1:
                print(f"  Sample: {lines[1]}")
            return True
        else:
            print(f"✗ Failed to read Articles table: {result.stderr}")
            return False
    
    return False


def read_with_access_parser(mdb_path: Path):
    """Read .mdb file using access_parser library"""
    print(f"\n--- Reading {mdb_path} with access_parser ---")
    
    try:
        import access_parser as ap
        
        db = ap.AccessDatabase(str(mdb_path))
        tables = db.list_tables()
        print(f"✓ Tables found: {', '.join(tables)}")
        
        if "Articles" in tables:
            articles = db.read_table("Articles")
            print(f"✓ Articles table: {len(articles)} rows")
            if articles:
                print(f"  Columns: {', '.join(articles[0].keys())}")
                print(f"  Sample: {articles[0]}")
            return True
        
        return False
        
    except Exception as e:
        print(f"✗ Failed with access_parser: {e}")
        return False


def main():
    """Run spike test"""
    print("=" * 60)
    print("ChimeraFlow - Access Database Spike (P0)")
    print("=" * 60)
    
    # Check available tools
    has_mdbtools = test_mdbtools()
    has_access_parser = test_access_parser()
    
    if not has_mdbtools and not has_access_parser:
        print("\n✗ SPIKE FAILED: No Access reading tools available")
        print("\nAction required:")
        print("  1. Install mdbtools OR access_parser")
        print("  2. Generate STOCK_ZOBO.mdb with scripts/generate_access.py")
        print("  3. Re-run this spike")
        print("\n  Documented in: docs/decisions/TECH_DEBT.md")
        return False
    
    # Test with sample file if it exists
    mdb_path = Path("../data/STOCK_ZOBO.mdb")
    
    if not mdb_path.exists():
        print(f"\n⚠ Sample file not found: {mdb_path}")
        print("  Run: python scripts/generate_access.py")
        print("\n✓ SPIKE PARTIAL: Tools available, need sample file")
        return True
    
    # Try reading
    success = False
    if has_mdbtools:
        success = read_with_mdbtools(mdb_path)
    
    if not success and has_access_parser:
        success = read_with_access_parser(mdb_path)
    
    if success:
        print("\n" + "=" * 60)
        print("✓ SPIKE SUCCESS: Can read Access databases")
        print("=" * 60)
        return True
    else:
        print("\n" + "=" * 60)
        print("✗ SPIKE FAILED: Cannot read Access databases")
        print("=" * 60)
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
