"""Mock point cloud generation: waits about 10 seconds and passes. Nothing is computed."""
import argparse
import time

SECONDS = 10


def run(seconds: float = SECONDS) -> str:
    time.sleep(seconds)
    return "point cloud generation finished (mock)"


if __name__ == "__main__":
    argparse.ArgumentParser(description=__doc__).parse_known_args()
    print(run())
