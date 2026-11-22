"""Placeholder lesion inference: waits about 10 seconds and passes. Nothing is computed."""
import argparse
import time

SECONDS = 10


def run(seconds: float = SECONDS) -> str:
    time.sleep(seconds)
    return "lesion inference finished"


if __name__ == "__main__":
    argparse.ArgumentParser(description=__doc__).parse_known_args()
    print(run())
