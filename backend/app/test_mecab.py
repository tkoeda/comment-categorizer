import os
import subprocess
import sys


def check_mecab_installation():
    """
    Simplified function to check if MeCab is properly installed and configured.
    """
    print("=== MeCab Installation Diagnostic ===")

    # Check if mecab command exists
    print("\nChecking MeCab command...")
    try:
        mecab_version = subprocess.check_output(
            ["mecab", "--version"], stderr=subprocess.STDOUT, text=True
        )
        print(f"MeCab command: {mecab_version.strip()}")
    except (subprocess.SubprocessError, FileNotFoundError) as e:
        print(f"MeCab command error: {str(e)}")

    # Check for mecabrc file
    print("\nChecking for mecabrc file...")
    mecabrc_paths = [
        "/usr/local/etc/mecabrc",
        "/etc/mecabrc",
        "/usr/lib/x86_64-linux-gnu/mecab/etc/mecabrc",
    ]

    for path in mecabrc_paths:
        if os.path.exists(path):
            print(f"Found mecabrc at: {path}")
        else:
            print(f"No mecabrc at: {path}")

    # Check if fugashi can be imported
    print("\nChecking if fugashi can be imported...")
    try:
        import fugashi

        print("Fugashi import: Success")
    except ImportError as e:
        print(f"Fugashi import error: {str(e)}")

    # Check for MeCab dictionary path
    print("\nChecking for MeCab dictionary...")
    ipadic_paths = [
        "/usr/lib/x86_64-linux-gnu/mecab/dic/mecab-ipadic-utf8",
        "/usr/share/mecab/dic/ipadic",
        "/usr/local/lib/mecab/dic/ipadic",
    ]

    for path in ipadic_paths:
        if os.path.exists(path):
            print(f"Found dictionary at: {path}")
        else:
            print(f"No dictionary at: {path}")

    # Check relevant environment variables
    print("\nChecking environment variables...")
    env_vars_to_check = ["MECABRC", "LD_LIBRARY_PATH", "PATH"]
    for var in env_vars_to_check:
        print(f"{var}: {os.environ.get(var, 'Not set')}")

    # Try initializing GenericTagger
    print("\nAttempting to initialize GenericTagger...")
    try:
        from fugashi import GenericTagger

        # Try with explicit dictionary path
        print("Trying with explicit dictionary path...")
        tagger = GenericTagger(
            "-d /usr/lib/x86_64-linux-gnu/mecab/dic/mecab-ipadic-utf8"
        )
        print("Successfully initialized tagger with explicit path")
    except Exception as e:
        print(f"Error initializing tagger with explicit path: {e}")

        # Try with no arguments
        try:
            print("Trying with default settings...")
            tagger = GenericTagger("")
            print("Successfully initialized tagger with default settings")
        except Exception as e:
            print(f"Error initializing tagger with default settings: {e}")

    print("\n=== Diagnostic Complete ===")


# Run the diagnostic function
try:
    check_mecab_installation()
except Exception as e:
    print(f"Diagnostic failed with error: {e}")
